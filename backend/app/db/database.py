import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.config import settings


def get_db_path() -> Path:
    return settings.DB_PATH


def init_db() -> None:
    """初始化数据库表及重置中断任务"""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                filename TEXT,
                report_date TEXT,
                status TEXT,
                status_label TEXT,
                stage_index INTEGER,
                progress INTEGER,
                message TEXT,
                report_json TEXT,
                file_path TEXT,
                refine_history_json TEXT
            )
        """)
        cursor = conn.execute("PRAGMA table_info(tasks)")
        columns = [column[1] for column in cursor.fetchall()]
        if "file_path" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN file_path TEXT")
        if "refine_history_json" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN refine_history_json TEXT")

        conn.execute("""
            UPDATE tasks 
            SET status = 'failed', status_label = '已中断', message = '服务重启导致任务中断，请重新选择文件上传'
            WHERE status = 'processing'
        """)
        conn.commit()


init_db()


def db_save_task(task: Dict[str, Any]) -> None:
    report_str = json.dumps(task.get("report"), ensure_ascii=False) if task.get("report") else None
    refine_hist_str = json.dumps(task.get("refine_history", []), ensure_ascii=False) if task.get("refine_history") is not None else "[]"

    with sqlite3.connect(get_db_path()) as conn:
        conn.execute(
            """
            INSERT INTO tasks (id, filename, report_date, status, status_label, stage_index, progress, message, report_json, file_path, refine_history_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                status_label = excluded.status_label,
                stage_index = excluded.stage_index,
                progress = excluded.progress,
                message = excluded.message,
                report_json = excluded.report_json,
                file_path = excluded.file_path,
                refine_history_json = excluded.refine_history_json
        """,
            (
                task["id"],
                task["filename"],
                task["report_date"],
                task["status"],
                task["status_label"],
                task["stage_index"],
                task["progress"],
                task["message"],
                report_str,
                task.get("file_path"),
                refine_hist_str,
            ),
        )
        conn.commit()


def _format_task_row(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    d = dict(row)
    d["report"] = json.loads(d["report_json"]) if d.get("report_json") else None
    d.pop("report_json", None)

    if d.get("refine_history_json"):
        try:
            d["refine_history"] = json.loads(d["refine_history_json"])
        except Exception:
            d["refine_history"] = []
    else:
        d["refine_history"] = []
    d.pop("refine_history_json", None)
    return d


def db_get_task(task_id: str) -> Optional[Dict[str, Any]]:
    with sqlite3.connect(get_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _format_task_row(row)


def db_get_completed_dates() -> List[str]:
    with sqlite3.connect(get_db_path()) as conn:
        rows = conn.execute("SELECT DISTINCT report_date FROM tasks WHERE status = 'completed'").fetchall()
        return sorted([r[0] for r in rows if r[0]])


def db_get_report_by_date(report_date: str) -> Optional[Dict[str, Any]]:
    with sqlite3.connect(get_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM tasks WHERE report_date = ? AND status = 'completed' ORDER BY rowid DESC LIMIT 1",
            (report_date,),
        ).fetchone()
        return _format_task_row(row)


def db_get_latest_task_by_date(report_date: str) -> Optional[Dict[str, Any]]:
    with sqlite3.connect(get_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        completed_row = conn.execute(
            "SELECT * FROM tasks WHERE report_date = ? AND status = 'completed' ORDER BY rowid DESC LIMIT 1",
            (report_date,),
        ).fetchone()

        if completed_row:
            return _format_task_row(completed_row)

        row = conn.execute(
            "SELECT * FROM tasks WHERE report_date = ? ORDER BY rowid DESC LIMIT 1", (report_date,)
        ).fetchone()
        return _format_task_row(row)

