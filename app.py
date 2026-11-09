"""Game On! Eastern Wake Reserve Tracker: staff-managed status, no patron data."""
import os, json, sqlite3, hmac, hashlib, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from functools import wraps
from flask import Flask, jsonify, render_template, request, abort
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent
SECRET = os.getenv("APP_SECRET", "")
PASSWORD_HASH = os.getenv("STAFF_PASSWORD_HASH", "")
if len(SECRET) < 32 or not PASSWORD_HASH:
    raise RuntimeError("Configure APP_SECRET and STAFF_PASSWORD_HASH privately before starting.")
app = Flask(__name__)
app.json.sort_keys = False
token_signer = URLSafeTimedSerializer(SECRET, salt="game-on-staff")
DB = Path(os.getenv("DATABASE_PATH", str(ROOT / "data" / "reserve.db")))
if not DB.is_absolute():
    DB = ROOT / DB
DB.parent.mkdir(parents=True, exist_ok=True)
ITEMS = json.loads((ROOT / "items.json").read_text(encoding="utf-8"))
IDS = {item["id"] for item in ITEMS}

def connect():
    conn = sqlite3.connect(DB, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def now_utc():
    return datetime.now(timezone.utc)

def init_db():
    with connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS status (item_id TEXT PRIMARY KEY, checked_out_at TEXT, due_at TEXT, checked_in_at TEXT, updated_at TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT NOT NULL, action TEXT NOT NULL, at TEXT NOT NULL)")
        for item in ITEMS:
            db.execute("INSERT OR IGNORE INTO status(item_id,updated_at) VALUES (?,?)", (item["id"], now_utc().isoformat()))
init_db()

def valid_password(password):
    try:
        algo, count, salt, target = PASSWORD_HASH.split("$")
        if algo != "pbkdf2_sha256" or not isinstance(password, str):
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(count))
        return hmac.compare_digest(actual, bytes.fromhex(target))
    except (ValueError, TypeError):
        return False

def staff():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    try:
        return token_signer.loads(auth[7:], max_age=43200).get("role") == "staff"
    except (BadSignature, SignatureExpired):
        return False

def requires_staff(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not staff():
            return jsonify(error="Staff login required"), 401
        return fn(*args, **kwargs)
    return wrapped

@app.after_request
def secure_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store" if request.path.startswith("/api/") else "public,max-age=300"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'self' https://researchguides.waketech.edu https://*.libguides.com"
    return response

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/api/board")
def board():
    with connect() as db:
        status = {r["item_id"]: dict(r) for r in db.execute("SELECT * FROM status")}
        events = [dict(r) for r in db.execute("SELECT item_id,action,at FROM events ORDER BY id DESC LIMIT 30")]
    return jsonify(items=[{**i, **status.get(i["id"], {})} for i in ITEMS], events=events, server_now=now_utc().isoformat())

ATTEMPTS = {}
@app.post("/api/login")
def login():
    ip = request.remote_addr or "unknown"
    ts = time.monotonic()
    attempts = [t for t in ATTEMPTS.get(ip, []) if ts - t < 900]
    if len(attempts) >= 8:
        return jsonify(error="Too many attempts. Try again in 15 minutes."), 429
    password = (request.get_json(silent=True) or {}).get("password", "")
    if not valid_password(password):
        attempts.append(ts)
        ATTEMPTS[ip] = attempts
        return jsonify(error="Incorrect password"), 401
    ATTEMPTS.pop(ip, None)
    return jsonify(token=token_signer.dumps({"role": "staff"}), expires_hours=12)

@app.post("/api/item/<item_id>/toggle")
@requires_staff
def toggle(item_id):
    if item_id not in IDS:
        abort(404)
    now = now_utc()
    stamp = now.isoformat()
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        state = db.execute("SELECT checked_out_at FROM status WHERE item_id=?", (item_id,)).fetchone()
        if state["checked_out_at"] is None:
            due = (now + timedelta(hours=3)).isoformat()
            db.execute("UPDATE status SET checked_out_at=?,due_at=?,updated_at=? WHERE item_id=?", (stamp, due, stamp, item_id))
            action = "checked_out"
        else:
            db.execute("UPDATE status SET checked_out_at=NULL,due_at=NULL,checked_in_at=?,updated_at=? WHERE item_id=?", (stamp, stamp, item_id))
            action = "checked_in"
        db.execute("INSERT INTO events(item_id, action, at) VALUES (?,?,?)", (item_id, action, stamp))
    return jsonify(action=action, at=stamp)

@app.get("/health")
def health():
    return jsonify(ok=True)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
