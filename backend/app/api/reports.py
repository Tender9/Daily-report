from fastapi import APIRouter
from app.core.exception import BusinessException
from app.db.database import db_get_completed_dates, db_get_report_by_date

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/dates", summary="获取所有完成日报的日期")
def report_dates() -> dict[str, list[str]]:
    return {"dates": db_get_completed_dates()}


@router.get("/by-date/{report_date}", summary="获取指定日期的已完成日报")
def get_report_by_date(report_date: str) -> dict:
    report = db_get_report_by_date(report_date)
    if not report:
        raise BusinessException(code=4040, message="该日期暂无已完成日报")
    return report
