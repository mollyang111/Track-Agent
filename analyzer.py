import io
import re

import ollama
from googleapiclient.http import MediaIoBaseDownload
from pypdf import PdfReader

from config import OLLAMA_HOST, OLLAMA_MODEL

_client = ollama.Client(host=OLLAMA_HOST)

_EXPORTABLE = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}
_DOWNLOADABLE = {
    "text/plain",
    "text/csv",
    "text/markdown",
    "application/json",
}

_SYSTEM_PROMPT = (
    "You are an assistant that analyzes Google Drive files and summarizes their content. "
    "Given file metadata and extracted content, write 3–5 sentences covering: "
    "what the file is about, its main topics or purpose, and any key details worth noting. "
    "Focus on the actual content — not just the filename or timestamps. Be specific and concise."
)

_MAX_CONTENT_CHARS = 8_000


def _extract_pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)[:_MAX_CONTENT_CHARS]
    except Exception:
        return ""


def _fetch_content(service, file_id: str, mime_type: str) -> str | None:
    try:
        if mime_type in _EXPORTABLE:
            request = service.files().export_media(fileId=file_id, mimeType=_EXPORTABLE[mime_type])
        elif mime_type in _DOWNLOADABLE or mime_type == "application/pdf":
            request = service.files().get_media(fileId=file_id)
        else:
            return None

        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        raw = buf.getvalue()
        if mime_type == "application/pdf":
            return _extract_pdf_text(raw) or None
        return raw.decode("utf-8", errors="replace")[:_MAX_CONTENT_CHARS]
    except Exception as e:
        print(f"  Could not fetch content for {file_id}: {e}")
        return None


def analyze_change(service, change: dict) -> str:
    """Use a local Ollama model to summarize a single Drive change."""
    file_info = change.get("file") or {}
    removed = change.get("removed", False)

    if removed:
        file_id = change.get("fileId", "unknown")
        return f"File deleted (ID: {file_id})."

    name = file_info.get("name", "Unknown")
    mime_type = file_info.get("mimeType", "")
    modified_time = file_info.get("modifiedTime", "unknown time")
    web_link = file_info.get("webViewLink", "")
    file_id = file_info.get("id", "")

    content = _fetch_content(service, file_id, mime_type)

    user_parts = [
        "A Google Drive file was modified.",
        f"Name: {name}",
        f"Type: {mime_type}",
        f"Modified: {modified_time}",
    ]
    if web_link:
        user_parts.append(f"Link: {web_link}")
    if content:
        user_parts.append(f"\nFile content (excerpt, up to {_MAX_CONTENT_CHARS} chars):\n{content}")
        user_parts.append("\nSummarize what this file is and what may have changed.")
    else:
        user_parts.append("\nContent unavailable for this file type. Summarize based on metadata only.")

    response = _client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": "\n".join(user_parts)},
        ],
    )
    text = response.message.content
    # Strip DeepSeek-R1 thinking tokens before returning
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return text
