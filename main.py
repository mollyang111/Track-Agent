#!/usr/bin/env python3
"""Google Drive modification agent — polls for changes, analyzes them with Claude."""

import time

from analyzer import analyze_change
from config import POLL_INTERVAL, WATCH_FOLDER_ID
from db import get_last_known_name, has_file_history, init_db, is_duplicate
from notifier import notify
from watcher import get_drive_service, poll_changes

# In-memory cache: (file_id, modified_time) -> epoch second of last processing
_recent: dict[tuple, float] = {}
_RECENT_TTL = max(POLL_INTERVAL * 2, 120)


def _seen_recently(file_id: str, modified_time: str | None) -> bool:
    key = (file_id, modified_time)
    now = time.time()
    if key in _recent and now - _recent[key] < _RECENT_TTL:
        return True
    _recent[key] = now
    return False


def _crud_operation(change: dict) -> str:
    if change.get("removed") or (change.get("file") or {}).get("trashed"):
        return "deleted"
    file_id = change.get("fileId", "")
    return "updated" if has_file_history(file_id) else "created"


def run() -> None:
    print("Starting Google Drive agent...")
    init_db()
    service = get_drive_service()

    scope = f"folder {WATCH_FOLDER_ID}" if WATCH_FOLDER_ID else "entire Drive"
    print(f"Polling every {POLL_INTERVAL}s — watching: {scope}")
    print("Press Ctrl-C to stop.\n")

    while True:
        try:
            changes = poll_changes(service, folder_id=WATCH_FOLDER_ID)
            new_changes = []
            for change in changes:
                file_info = change.get("file") or {}
                file_id = change.get("fileId", "")
                modified_time = file_info.get("modifiedTime")
                removed = change.get("removed", False) or (change.get("file") or {}).get("trashed", False)
                if not removed and (_seen_recently(file_id, modified_time) or is_duplicate(change)):
                    continue
                new_changes.append(change)

            if new_changes:
                print(f"Detected {len(new_changes)} new change(s).")
                for change in new_changes:
                    file_info = change.get("file") or {}
                    name = file_info.get("name", change.get("fileId", "unknown"))
                    file_id = change.get("fileId", "")
                    removed = change.get("removed", False)

                    if removed and (not name or name == file_id):
                        name = get_last_known_name(file_id) or file_id

                    operation = _crud_operation(change)
                    change["_operation"] = operation
                    change["_display_name"] = name
                    print(f"  [{operation.upper()}] {name}")

                    try:
                        summary = analyze_change(service, change)
                    except Exception as e:
                        print(f"  Analysis error for {name}: {e}")
                        summary = f"[Analysis unavailable: {e}]"
                    try:
                        notify(change, summary)
                    except Exception as e:
                        print(f"  Notify error for {name}: {e}")
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"Poll error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        pass
