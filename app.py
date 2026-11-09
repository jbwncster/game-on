"""Game On! Eastern Wake Reserve Tracker: staff-managed status, no patron data."""
import os, json, hmac, hashlib, time
from datetime import datetime, timezone, timedelta
from status_store import list_events, write_event
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
ITEMS = json.loads((ROOT / "items.json").read_text(encoding="utf-8"))
IDS = {item["id"] for item in ITEMS}

def now_utc():
    return datetime.now(timezone.utc)

def current_state():
    events = list_events()
    status = {item["id"]: {"checked_out_at": None, "due_at": None, "checked_in_at": None} for item in ITEMS}
    for event in events:
        state=status.get(event["item_id"])
        if state is None:
            continue
        moment=event["at"]
        if event["action"] == "checked_out":
            state["checked_out_at"]=moment
            state["due_at"]=(datetime.fromisoformat(moment)+timedelta(hours=3)).isoformat()
        elif event["action"]=="checked_in":
            state["checked_out_at"]=None
            state["due_at"]=None
            state["checked_in_at"]=moment
    return status,events

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
    status,events=current_state()
    public_events=events[-30:] if staff() else []
    return jsonify(items=[{**i, **status[i["id"]]} for i in ITEMS],
                   events=list(reversed(public_events)),server_now=now_utc().isoformat())

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
    state,_=current_state()
    action="checked_in" if state[item_id]["checked_out_at"] else "checked_out"
    now=now_utc()
    write_event(item_id,action,now)
    return jsonify(action=action,at=now.isoformat())

@app.get("/health")
def health():
    return jsonify(ok=True,storage=("blob" if os.getenv("BLOB_READ_WRITE_TOKEN") else "local"))

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
