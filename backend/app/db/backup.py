import logging
import os
import sqlite3
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from app.config import settings
from app.db.database import get_db_path

logger = logging.getLogger(__name__)


def perform_backup() -> Dict[str, Any]:
    """执行安全的数据定期备份：包含 SQLite 数据库在线快照与上传目录打包归档。"""
    backup_dir = settings.BACKUP_DIR
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"backup_{settings.APP_ENV}_{timestamp}.zip"
    zip_path = backup_dir / zip_name

    db_path = get_db_path()
    upload_dir = settings.UPLOAD_DIR

    file_count = 0

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # 1. 安全在线热备份 SQLite 数据库
            if db_path.exists():
                temp_db_path = backup_dir / f"temp_db_{timestamp}.sqlite"
                try:
                    with sqlite3.connect(db_path) as src_conn, sqlite3.connect(temp_db_path) as dst_conn:
                        src_conn.backup(dst_conn)
                    zipf.write(temp_db_path, arcname="tasks.db")
                    file_count += 1
                finally:
                    if temp_db_path.exists():
                        try:
                            temp_db_path.unlink()
                        except Exception:
                            pass

            # 2. 打包归档上传的原始聊天记录
            if upload_dir.exists():
                for root, _, files in os.walk(upload_dir):
                    for f in files:
                        full_f_path = Path(root) / f
                        rel_path = Path("uploads") / full_f_path.relative_to(upload_dir)
                        zipf.write(full_f_path, arcname=str(rel_path))
                        file_count += 1

        size_bytes = zip_path.stat().st_size if zip_path.exists() else 0
        logger.info(f"数据备份成功完成: {zip_name} (大小: {size_bytes} 字节, 包含文件: {file_count} 个)")

        # 3. 自动清理过期备份文件
        clean_expired_backups()

        return {
            "status": "success",
            "filename": zip_name,
            "filepath": str(zip_path),
            "size_bytes": size_bytes,
            "file_count": file_count,
            "timestamp": timestamp,
        }
    except Exception as e:
        logger.error(f"数据备份执行异常: {e}")
        if zip_path.exists():
            try:
                zip_path.unlink()
            except Exception:
                pass
        return {"status": "error", "message": str(e)}


def clean_expired_backups() -> List[str]:
    """根据配置保留天数自动清理过期的备份归档压缩包。"""
    backup_dir = settings.BACKUP_DIR
    if not backup_dir.exists():
        return []

    retention_days = settings.BACKUP_RETENTION_DAYS
    cutoff_time = datetime.now() - timedelta(days=retention_days)
    removed_files = []

    for item in backup_dir.glob("backup_*.zip"):
        try:
            file_mtime = datetime.fromtimestamp(item.stat().st_mtime)
            if file_mtime < cutoff_time:
                item.unlink()
                removed_files.append(item.name)
                logger.info(f"自动清理过期备份文件: {item.name}")
        except Exception as e:
            logger.warning(f"清理文件 {item.name} 失败: {e}")

    return removed_files


def list_backups() -> List[Dict[str, Any]]:
    """获取历史备份列表。"""
    backup_dir = settings.BACKUP_DIR
    if not backup_dir.exists():
        return []

    result = []
    for item in sorted(backup_dir.glob("backup_*.zip"), reverse=True):
        try:
            stat = item.stat()
            result.append(
                {
                    "filename": item.name,
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )
        except Exception:
            pass
    return result
