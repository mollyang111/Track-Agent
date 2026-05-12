import mysql.connector
from datetime import datetime, timezone

from config import MYSQL_DATABASE, MYSQL_HOST, MYSQL_PASSWORD, MYSQL_PORT, MYSQL_USER

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS drive_changes (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    detected_at   DATETIME     NOT NULL,
    file_id       VARCHAR(255) NOT NULL,
    current_file  VARCHAR(500),
    operation     VARCHAR(20)  NOT NULL,
    modified_file VARCHAR(500),
    modified_time DATETIME,
    mime_type     VARCHAR(255),
    web_link      TEXT,
    summary       TEXT,
    INDEX idx_file_id     (file_id),
    INDEX idx_detected_at (detected_at)
)
"""


def _connect():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
    )


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def init_db() -> None:
    conn = mysql.connector.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
    )
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}`")
    cur.execute(f"USE `{MYSQL_DATABASE}`")
    cur.execute(_CREATE_TABLE)
    # Migrate ENUM column to VARCHAR if needed
    cur.execute(
        "ALTER TABLE drive_changes MODIFY COLUMN operation VARCHAR(20) NOT NULL"
    )
    conn.commit()
    cur.close()
    conn.close()


def is_duplicate(change: dict) -> bool:
    """Return True if this file_id + modified_time is already in the DB."""
    file_info = change.get("file") or {}
    modified_time = _parse_dt(file_info.get("modifiedTime"))
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM drive_changes WHERE file_id = %s AND modified_time = %s LIMIT 1",
        (change.get("fileId"), modified_time),
    )
    found = cur.fetchone() is not None
    cur.close()
    conn.close()
    return found


def get_last_known_name(file_id: str) -> str | None:
    """Return the most recent known file name for a file_id, or None."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT current_file FROM drive_changes WHERE file_id = %s AND current_file IS NOT NULL ORDER BY detected_at DESC LIMIT 1",
        (file_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None


def has_file_history(file_id: str) -> bool:
    """Return True if this file has been seen before (used to distinguish create vs update)."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM drive_changes WHERE file_id = %s LIMIT 1",
        (file_id,),
    )
    found = cur.fetchone() is not None
    cur.close()
    conn.close()
    return found


def insert_change(change: dict, summary: str) -> None:
    """Insert one Drive change record into drive_changes."""
    file_info = change.get("file") or {}
    removed = change.get("removed", False)
    operation = change.get("_operation", "deleted" if removed else "updated")
    file_name = file_info.get("name")
    modified_time = _parse_dt(file_info.get("modifiedTime"))

    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO drive_changes
            (detected_at, file_id, current_file, operation, modified_file,
             modified_time, mime_type, web_link, summary)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            datetime.now(timezone.utc),
            change.get("fileId"),
            file_name,
            operation,
            file_name if not removed else None,
            modified_time,
            file_info.get("mimeType"),
            file_info.get("webViewLink"),
            summary,
        ),
    )
    conn.commit()
    cur.close()
    conn.close()
