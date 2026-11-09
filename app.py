"""Game On! Eastern Wake Reserve Tracker: staff-managed status, no patron data."""
import os, json, hmac, hashlib, time
from datetime import datetime, timezone, timedelta
from status_store import list_events, write_event
from pathlib import Path
from functools import wraps
from flask import Flask, jsonify, render_template, request, abort, Response
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
    status = {item["id"]: {"checked_out_at": None, "due_at": None, "checked_in_at": None, "out_of_service": False, "condition_note": "", "updated_at": None} for item in ITEMS}
    for event in events:
        state=status.get(event["item_id"])
        if state is None:
            continue
        moment=event["at"]
        state["updated_at"]=moment
        if event["action"] == "checked_out":
            state["checked_out_at"]=moment
            state["due_at"]=(datetime.fromisoformat(moment)+timedelta(hours=3)).isoformat()
        elif event["action"]=="maintenance":
            state["out_of_service"]=event.get("payload",{}).get("out_of_service",False)
            state["condition_note"]=event.get("payload",{}).get("note","")
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
    if request.path == "/api/board" and request.headers.get("Origin") == "https://researchguides.waketech.edu":
        response.headers["Access-Control-Allow-Origin"] = "https://researchguides.waketech.edu"
        response.headers["Vary"] = "Origin"
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
    return jsonify(items=[{**i, **{k:v for k,v in status[i["id"]].items() if k!="condition_note" or staff()}} for i in ITEMS],
                   events=list(reversed(public_events)),server_now=now_utc().isoformat(),
                   last_change_at=max((e["at"] for e in events),default=None))

@app.get("/api/public-board.js")
def public_board_script():
    # Script-based public feed avoids third-party fetch/CORS restrictions inside LibGuides.
    # Do not publish staff activity events or authentication data here.
    state, _ = current_state()
    payload = {"items": [{**item, **{k:v for k,v in state[item["id"]].items() if k!="condition_note"}} for item in ITEMS],
               "server_now": now_utc().isoformat(),
               "last_change_at":max((e["at"] for e in list_events()),default=None)}
    safe_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    return Response("window.GameOnReceive && window.GameOnReceive(" + safe_json + ");",
                    content_type="application/javascript; charset=utf-8")


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
    if state[item_id]["out_of_service"] and not state[item_id]["checked_out_at"]:
        return jsonify(error="Item is out of service; restore it before checkout."), 409
    action="checked_in" if state[item_id]["checked_out_at"] else "checked_out"
    now=now_utc()
    write_event(item_id,action,now)
    return jsonify(action=action,at=now.isoformat())


@app.post("/api/staff/item/<item_id>/maintenance")
@requires_staff
def update_maintenance(item_id):
    if item_id not in IDS:
        abort(404)
    body = request.get_json(silent=True)
    if not isinstance(body,dict) or not isinstance(body.get("out_of_service"),bool):
        return jsonify(error="Invalid maintenance status"),400
    note=body.get("note","")
    if not isinstance(note,str) or len(note)>250:
        return jsonify(error="Condition note must be 250 characters or fewer"),400
    # Never add patron names, identifiers or borrowing histories to staff notes.
    when=now_utc()
    write_event(item_id,"maintenance",when,{"out_of_service":body["out_of_service"],"note":note.strip()})
    return jsonify(ok=True,updated_at=when.isoformat())

@app.get("/staff/stats")
def staff_stats_page():
    # The HTML shell is public; the statistics API requires a valid staff token.
    return render_template("staff_stats.html")

@app.get("/api/staff/stats")
@requires_staff
def staff_stats():
    state, events = current_state()
    reset_events = [e for e in events if e["action"] == "stats_reset"]
    last_reset = reset_events[-1]["at"] if reset_events else None
    if last_reset:
        events = [e for e in events if e["at"] > last_reset]
    now = now_utc()
    thirty = now - timedelta(days=30)
    seven = now - timedelta(days=7)
    item_lookup = {item["id"]:item for item in ITEMS}
    totals = {item["id"]:0 for item in ITEMS}
    recent = []
    checkouts_7d = checkouts_30d = returns_30d = 0
    for event in events:
        item = item_lookup.get(event["item_id"])
        if not item:
            continue
        at = datetime.fromisoformat(event["at"])
        if event["action"] == "checked_out":
            totals[event["item_id"]] += 1
            if at >= seven:
                checkouts_7d += 1
            if at >= thirty:
                checkouts_30d += 1
        elif event["action"] == "checked_in" and at >= thirty:
            returns_30d += 1
        if event["action"] not in ("checked_out","checked_in"):
            continue
        recent.append({
            "title":item["title"],
            "barcode":item["barcode"],
            "action":event["action"],
            "at":event["at"]
        })
    current_out = [
        {"title":item["title"],"barcode":item["barcode"],
         "checked_out_at":state[item["id"]]["checked_out_at"],
         "due_at":state[item["id"]]["due_at"],
         "overdue":datetime.fromisoformat(state[item["id"]]["due_at"]) < now}
        for item in ITEMS if state[item["id"]]["checked_out_at"]
    ]
    ranking = sorted(
        [{"title":item["title"],"barcode":item["barcode"],"checkouts":totals[item["id"]]}
         for item in ITEMS],key=lambda item:(-item["checkouts"],item["title"].lower()))
    return jsonify(
        generated_at=now.isoformat(), stats_reset_at=last_reset,
        total_checkouts=sum(totals.values()),
        checkouts_7d=checkouts_7d,checkouts_30d=checkouts_30d,
        returns_30d=returns_30d,currently_out=len(current_out),
        currently_overdue=sum(1 for item in current_out if item["overdue"]),
        current_out=current_out, by_item=ranking, recent=list(reversed(recent[-100:])),
        note="Game On! activity only; not a SirsiDynix circulation report."
    )

@app.post("/api/staff/stats/reset")
@requires_staff
def reset_staff_stats():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify(error="Invalid request"), 400
    if body.get("confirmation") != "CLEAR STATS":
        return jsonify(error="Type CLEAR STATS to confirm."), 400
    password = body.get("password", "")
    if not isinstance(password, str) or not valid_password(password):
        return jsonify(error="Incorrect staff password; statistics unchanged."), 403
    when = now_utc()
    # Append-only reset marker: preserve prior audit history and current item statuses.
    write_event("__stats__", "stats_reset", when)
    return jsonify(ok=True, reset_at=when.isoformat(),
                   message="Reporting totals reset; item availability unchanged.")


@app.get("/health")
def health():
    return jsonify(ok=True,storage=("blob" if os.getenv("BLOB_READ_WRITE_TOKEN") else "local"))

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
