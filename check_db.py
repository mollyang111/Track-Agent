#!/usr/bin/env python3
"""Print all rows in drive_changes, newest first."""

from db import _connect, init_db


def main():
    init_db()
    conn = _connect()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM drive_changes ORDER BY detected_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        print("No records yet.")
        return

    print(f"{len(rows)} record(s) found:\n")
    for row in rows:
        print(f"  ID          : {row['id']}")
        print(f"  Detected at : {row['detected_at']}")
        print(f"  File ID     : {row['file_id']}")
        print(f"  Current file: {row['current_file']}")
        print(f"  Operation   : {row['operation']}")
        print(f"  Modified file: {row['modified_file']}")
        print(f"  Modified time: {row['modified_time']}")
        print(f"  MIME type   : {row['mime_type']}")
        print(f"  Web link    : {row['web_link']}")
        print(f"  Summary     : {row['summary'] or None}")
        print()


if __name__ == "__main__":
    main()
