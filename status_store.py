"""Persistent event log for manual reserve status. Never stores borrower identities.
On Vercel each status change is an immutable, private Vercel Blob object.
The timestamp and item id in its pathname are enough to reconstruct status.
"""
import os, uuid, sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

BLOB_ENABLED = bool(os.environ.get("BLOB_READ_WRITE_TOKEN"))
if os.environ.get("VERCEL") and not BLOB_ENABLED:
    raise RuntimeError("BLOB_READ_WRITE_TOKEN required for durable checkouts")
DB = Path(os.environ.get("DATABASE_PATH","data/reserve.db"))

def parse_path(path):
    try:
        name = path.split("/")[-1].removesuffix(".json")
        timestamp, unique, item_id, action = name.split("-", 3)
        if action not in ("in","out") or not item_id.startswith("item-"):
            return None
        moment = datetime.strptime(timestamp,"%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)
        return {"item_id":item_id,"action":"checked_out" if action=="out" else "checked_in",
                "at":moment.isoformat()}
    except (ValueError, IndexError):
        return None

def _local_connection():
    DB.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS actions (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT, action TEXT, at TEXT)")
    return conn

def list_events():
    if not BLOB_ENABLED:
        with _local_connection() as db:
            rows=db.execute("SELECT item_id,action,at FROM actions ORDER BY id").fetchall()
        return [dict(item_id=x[0],action=x[1],at=x[2]) for x in rows]
    from vercel.blob import list_objects
    records=[]
    cursor=None
    while True:
        page=list_objects(prefix="events/", limit=1000, cursor=cursor)
        for blob in page.blobs:
            event=parse_path(blob.pathname)
            if event:
                records.append(event)
        if not page.has_more:
            break
        cursor=page.cursor
    return sorted(records,key=lambda e:e["at"])

def write_event(item_id,action,when):
    if action not in ("checked_in","checked_out"):
        raise ValueError("Invalid action")
    if not BLOB_ENABLED:
        with _local_connection() as db:
            db.execute("INSERT INTO actions(item_id,action,at) VALUES(?,?,?)",(item_id,action,when.isoformat()))
        return
    from vercel.blob import put
    action_short="out" if action=="checked_out" else "in"
    stamp=when.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe_id=item_id.replace("-","_")
    pathname=f"events/{stamp}-{uuid.uuid4().hex}-{safe_id}-{action_short}.json"
    put(pathname,b"{}",access="private",content_type="application/json")
