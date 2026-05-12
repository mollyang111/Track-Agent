import json
import os
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from auth import get_credentials

PAGE_TOKEN_PATH = "state/page_token.json"


def get_drive_service():
    return build("drive", "v3", credentials=get_credentials())


def _load_page_token() -> Optional[str]:
    if os.path.exists(PAGE_TOKEN_PATH):
        with open(PAGE_TOKEN_PATH) as f:
            return json.load(f).get("token")
    return None


def _save_page_token(token: str) -> None:
    os.makedirs("state", exist_ok=True)
    with open(PAGE_TOKEN_PATH, "w") as f:
        json.dump({"token": token}, f)


def _init_page_token(service) -> str:
    response = service.changes().getStartPageToken().execute()
    token = response["startPageToken"]
    _save_page_token(token)
    return token


def poll_changes(service, folder_id: Optional[str] = None) -> list[dict]:
    """Return new Drive changes since the last poll. On first run, establishes baseline."""
    token = _load_page_token()
    if token is None:
        print("First run: establishing baseline page token. No changes reported yet.")
        _init_page_token(service)
        return []

    changes = []
    page_token = token

    while page_token:
        try:
            response = service.changes().list(
                pageToken=page_token,
                fields=(
                    "nextPageToken,newStartPageToken,"
                    "changes(fileId,removed,"
                    "file(id,name,mimeType,modifiedTime,parents,webViewLink,size,trashed))"
                ),
                includeRemoved=True,
            ).execute()
        except HttpError as e:
            print(f"Drive API error while listing changes: {e}")
            break

        for change in response.get("changes", []):
            if folder_id and not change.get("removed"):
                file_info = change.get("file") or {}
                parents = file_info.get("parents") or []
                if folder_id not in parents:
                    continue
            changes.append(change)

        if "newStartPageToken" in response:
            _save_page_token(response["newStartPageToken"])
        page_token = response.get("nextPageToken")

    return changes
