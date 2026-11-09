"""Persistent anonymous item events and staff-only maintenance notes."""
import os, uuid, sqlite3, json
from pathlib import Path
from datetime import datetime, timezone

BLOB_ENABLED = bool(os.environ.get("BLOB_READ_WRITE_TOKEN"))
if os.environ.get("VERCEL") and not BLOB_ENABLED:
    raise RuntimeError("BLOB_READ_WRITE_TOKEN required for durable checkouts")
DB = Path(os.environ.get("DATABASE_PATH", "data/reserve.db"))

ACTIONS = {"in":"checked_in", "out":"checked_out", "reset":"stats_reset", "maint":"maintenance"}

def parse_path(path):
    try:
        name = path.split("/")[-1].removesuffix(".json")
        timestamp, unique, item_id, action = name.split("-", 3)
        if action not in ACTIONS or (item_id != "stats_reset" and not item_id.startswith("item_")):
            return None
        moment = datetime.strptime(timestamp, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)
        return {"item_id":item_id.replace("_","-"), "action":ACTIONS[action], "at":moment.isoformat()}
    except (ValueError, IndexError):
        return None

def _local_connection():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS actions (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT, action TEXT, at TEXT, payload TEXT)")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(actions)")}
    if "payload" not in cols:
        conn.execute("ALTER TABLE actions ADD COLUMN payload TEXT")
    return conn

def list_events():
    if not BLOB_ENABLED:
        with _local_connection() as db:
            rows = db.execute("SELECT item_id,action,at,payload FROM actions ORDER BY id").fetchall()
        return [{**dict(item_id=r[0],action=r[1],at=r[2]),
                 **({"payload":json.loads(r[3])} if r[3] else {})} for r in rows]
    from vercel.blob import sync as blob
    records = []
    for item in blob.query_blobs(prefix="events/", page_size=1000):
        event = parse_path(item.pathname)
        if event:
            if event["action"] == "maintenance":
                body = blob.get_blob(item.pathname, access="private").body
                event["payload"] = json.loads(body)
            records.append(event)
    return sorted(records, key=lambda e:e["at"])

def write_event(item_id, action, when, payload=None):
    if action not in ("checked_in","checked_out","stats_reset","maintenance"):
        raise ValueError("Invalid action")
    if action == "maintenance" and (not isinstance(payload, dict) or
            not isinstance(payload.get("out_of_service"), bool) or
            not isinstance(payload.get("note"), str)):
        raise ValueError("Invalid maintenance data")
    if not BLOB_ENABLED:
        with _local_connection() as db:
            db.execute("INSERT INTO actions(item_id,action,at,payload) VALUES(?,?,?,?)",
                       (item_id,action,when.isoformat(),json.dumps(payload) if payload is not None else None))
        return
    from vercel.blob import sync as blob
    action_short = {"checked_out":"out","checked_in":"in","stats_reset":"reset","maintenance":"maint"}[action]
    stamp = when.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe_id = "stats_reset" if action=="stats_reset" else item_id.replace("-","_")
    pathname = f"events/{stamp}-{uuid.uuid4().hex}-{safe_id}-{action_short}.json"
    blob.put_blob(pathname, json.dumps(payload or {}).encode("utf-8"),
                  access="private", content_type="application/json")
