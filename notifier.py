import json
import os
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone

from config import CUSTOM_SCRIPT, LOG_FILE, WEBHOOK_URL
from db import insert_change


def _log(change: dict, summary: str) -> None:
    os.makedirs(os.path.dirname(LOG_FILE) or ".", exist_ok=True)
    file_info = change.get("file") or {}
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "file_id": change.get("fileId"),
        "file_name": file_info.get("name"),
        "operation": change.get("_operation", "modified"),
        "modified_time": file_info.get("modifiedTime"),
        "web_link": file_info.get("webViewLink"),
        "summary": summary,
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    operation = change.get("_operation", "modified").upper()
    snippet = summary[:400].replace("\n", " ")
    print(f"  [{entry['timestamp']}] [{operation}] {entry['file_name']}: {snippet}")


def _webhook(change: dict, summary: str) -> None:
    if not WEBHOOK_URL:
        return
    file_info = change.get("file") or {}
    payload = json.dumps(
        {
            "file_id": change.get("fileId"),
            "file_name": file_info.get("name"),
            "removed": change.get("removed", False),
            "modified_time": file_info.get("modifiedTime"),
            "web_link": file_info.get("webViewLink"),
            "summary": summary,
        }
    ).encode()
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.URLError as e:
        print(f"  Webhook POST failed: {e}")


def _custom_script(change: dict, summary: str) -> None:
    if not CUSTOM_SCRIPT:
        return
    file_info = change.get("file") or {}
    extra_env = {
        "DRIVE_FILE_ID": change.get("fileId") or "",
        "DRIVE_FILE_NAME": file_info.get("name") or "",
        "DRIVE_SUMMARY": summary,
        "DRIVE_LINK": file_info.get("webViewLink") or "",
    }
    try:
        subprocess.run(
            CUSTOM_SCRIPT,
            shell=True,
            env={**os.environ, **extra_env},
            check=False,
        )
    except Exception as e:
        print(f"  Custom script error: {e}")


def notify(change: dict, summary: str) -> None:
    """Log the change, persist to MySQL, post to webhook, and run the custom script."""
    _log(change, summary)
    try:
        insert_change(change, summary)
    except Exception as e:
        print(f"  DB insert failed: {e}")
    _webhook(change, summary)
    _custom_script(change, summary)
