from fastapi import APIRouter
from app.db.backup import list_backups, perform_backup

router = APIRouter(prefix="/backup", tags=["Backup"])


@router.get("/list", summary="获取历史数据备份列表")
def get_backup_list() -> dict:
    return {"backups": list_backups()}


@router.post("/now", summary="立即触发数据备份")
def trigger_backup_now() -> dict:
    return perform_backup()
