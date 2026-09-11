import asyncio
import time
import uuid
from datetime import date
from pathlib import Path
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from app.config import BASE_DIR, settings
from app.core.exception import BusinessException
from app.db.database import db_get_latest_task_by_date, db_get_task, db_save_task
from app.services.ai_service import ai_service
from app.services.parser_service import parse_file_content

router = APIRouter(prefix="/tasks", tags=["Tasks"])

ALLOWED_EXTENSIONS = {"txt", "pdf", "html", "htm", "doc", "docx", "log", "md"}


def _process_task_async(task_id: str, filename: str, content_bytes: bytes, report_date: str) -> None:
    async def run() -> None:
        task = db_get_task(task_id)
        if not task:
            return

        task.update(stage_index=1, progress=35, message="正在解析聊天内容文件...")
        db_save_task(task)
        await asyncio.sleep(0.3)

        extracted_text = parse_file_content(filename, content_bytes)

        start_time = time.time()
        provider_label = "火山引擎云端 API" if settings.AI_PROVIDER == "cloud" else "本地 MiniCPM-V GGUF 模型"
        task.update(stage_index=2, progress=72, message=f"{provider_label} 正在整理生成日报...")
        db_save_task(task)
        await asyncio.sleep(0.3)

        try:
            report_data = await asyncio.to_thread(ai_service.generate_report, extracted_text, report_date)
            elapsed_sec = round(time.time() - start_time, 2)
            task.update(
                stage_index=3,
                progress=100,
                status="completed",
                status_label="已完成",
                message=f"日报生成完成（耗时 {elapsed_sec} 秒），可导出图片",
                report=report_data,
                refine_history=task.get("refine_history", []),
            )
        except Exception as e:
            task.update(
                stage_index=3,
                progress=100,
                status="failed",
                status_label="生成失败",
                message=f"模型处理失败: {e}",
            )

        db_save_task(task)

    asyncio.create_task(run())


@router.post("/upload", summary="上传聊天文件并创建分析任务")
async def upload(file: UploadFile = File(...), report_date: str = Form(...)) -> dict:
    suffix = Path(file.filename or "").suffix.lower().lstrip(".")
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, "仅支持 TXT、PDF、HTML、DOC、DOCX 文件")

    content = await file.read(settings.MAX_UPLOAD_SIZE_BYTES + 1)
    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(413, f"文件不能超过 {settings.MAX_UPLOAD_SIZE_MB}MB")

    try:
        date.fromisoformat(report_date)
    except ValueError as exc:
        raise HTTPException(422, "日报日期格式必须为 YYYY-MM-DD") from exc

    task_id = uuid.uuid4().hex
    filename = file.filename or "chat.txt"

    # 持久化保存原始上传文件到 backend/uploads/{report_date}/
    date_upload_dir = settings.UPLOAD_DIR / report_date
    date_upload_dir.mkdir(parents=True, exist_ok=True)
    saved_file_path = date_upload_dir / f"{task_id}_{filename}"
    saved_file_path.write_bytes(content)

    try:
        relative_file_path = str(saved_file_path.relative_to(BASE_DIR))
    except ValueError:
        relative_file_path = str(saved_file_path)

    task = {
        "id": task_id,
        "filename": filename,
        "report_date": report_date,
        "status": "processing",
        "status_label": "处理中",
        "stage_index": 1,
        "progress": 20,
        "message": "文件已上传并保存，准备解析",
        "report": None,
        "file_path": relative_file_path,
    }
    db_save_task(task)
    _process_task_async(task_id, filename, content, report_date)
    return task


@router.get("/latest/{report_date}", summary="获取指定日期的最新任务")
def get_latest_task_by_date(report_date: str) -> dict:
    task = db_get_latest_task_by_date(report_date)
    if not task:
        raise BusinessException(code=4040, message="该日期暂无任务")
    return task


@router.get("/{task_id}", summary="获取指定任务 ID 状态")
def get_task(task_id: str) -> dict:
    task = db_get_task(task_id)
    if not task:
        raise BusinessException(code=4040, message="任务不存在")
    return task


from pydantic import BaseModel, Field
from typing import Optional


class SectionFeedbackModel(BaseModel):
    section_key: str = Field(..., description="待修改板块 key")
    rating: Optional[int] = Field(default=None, description="评分 1-5")
    instruction: str = Field(..., description="用户具体修改意见")


class RefineTaskRequest(BaseModel):
    section_feedback: SectionFeedbackModel


@router.post("/{task_id}/refine", summary="对已完成任务的特定板块进行 AI 增量微调")
async def refine_task_section(task_id: str, req: RefineTaskRequest) -> dict:
    task = db_get_task(task_id)
    if not task:
        raise BusinessException(code=4040, message="任务不存在")

    report = task.get("report")
    if not report or not isinstance(report, dict):
        raise BusinessException(code=4001, message="该任务尚未生成完成日报，无法微调")

    feedback = req.section_feedback
    section_key = feedback.section_key
    instruction = feedback.instruction.strip()

    if not instruction:
        raise BusinessException(code=4002, message="请填写修改意见或补充说明")

    current_section_data = report.get(section_key, "")

    section_names = {
        "summary": "氛围总结",
        "important_notices": "重要提醒/规则提炼",
        "hot_topics": "今日热门话题",
        "funny_quotes": "趣味互动",
        "tools_table_markdown": "工具及观点表格",
        "insights": "核心观点/避坑指南",
        "related_links": "相关链接/参考资源",
        "other_topics": "其他讨论话题",
        "ending_quote": "结语",
    }
    section_name = section_names.get(section_key, section_key)

    # 读取保存的原始文件上下文
    raw_text = ""
    file_path_str = task.get("file_path")
    if file_path_str:
        full_path = BASE_DIR / file_path_str
        if full_path.exists():
            try:
                from app.services.parser_service import parse_file_content

                raw_bytes = full_path.read_bytes()
                raw_text = parse_file_content(full_path.name, raw_bytes)
            except Exception:
                pass

    existing_history = task.get("refine_history", []) or []

    # 调用 AI 局部微调 (带入历史微调轨迹)
    refined_data = await asyncio.to_thread(
        ai_service.refine_section,
        section_key,
        current_section_data,
        instruction,
        raw_text,
        history_records=existing_history,
    )

    import datetime

    new_record = {
        "id": f"refine_{uuid.uuid4().hex[:8]}",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "section_key": section_key,
        "section_name": section_name,
        "rating": feedback.rating,
        "instruction": instruction,
        "previous_content": current_section_data,
        "refined_content": refined_data,
    }
    existing_history.append(new_record)

    # 替换对应板块并更新数据库
    report[section_key] = refined_data
    task["report"] = report
    task["refine_history"] = existing_history
    task["message"] = f"已完成【{section_name}】板块的 AI 增量微调"
    db_save_task(task)

    return task


@router.post("/{task_id}/regenerate", summary="对指定任务使用原数据重新生成完整日报")
async def regenerate_task(task_id: str) -> dict:
    task = db_get_task(task_id)
    if not task:
        task = db_get_latest_task_by_date(task_id)
    if not task:
        raise BusinessException(code=4040, message="当前日期暂无历史分析任务，请上传文件")

    file_path_str = task.get("file_path")
    full_path = None

    if file_path_str:
        p = Path(file_path_str)
        if p.is_absolute() and p.exists():
            full_path = p
        else:
            candidates = [
                (BASE_DIR / p).resolve(),
                (BASE_DIR.parent / p).resolve(),
                (settings.UPLOAD_DIR / p).resolve(),
            ]
            for cand in candidates:
                if cand.exists() and cand.is_file():
                    full_path = cand
                    break

    # 兜底：若文件路径未找到，自动从 uploads/{report_date} 目录中智能匹配最新附件
    if not full_path or not full_path.exists():
        report_date = task.get("report_date", task_id)
        date_dir = settings.UPLOAD_DIR / report_date
        if date_dir.exists():
            files = [
                f for f in date_dir.iterdir() if f.is_file() and f.suffix.lower().lstrip(".") in ALLOWED_EXTENSIONS
            ]
            if files:
                files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                full_path = files[0]

    if not full_path or not full_path.exists():
        raise BusinessException(code=4002, message="原始上传文件在服务器端未找到或已清理，请重新选择文件上传")

    content_bytes = full_path.read_bytes()
    filename = task.get("filename") or full_path.name
    report_date = task.get("report_date", "2026-09-08")

    task["status"] = "processing"
    task["status_label"] = "处理中"
    task["stage_index"] = 1
    task["progress"] = 20
    task["message"] = "已获取原聊天记录文件，重新启动 AI 完整分析..."
    task["report"] = None
    task["refine_history"] = []
    task["file_path"] = str(full_path.relative_to(BASE_DIR)) if full_path.is_relative_to(BASE_DIR) else str(full_path)
    db_save_task(task)

    _process_task_async(task["id"], filename, content_bytes, report_date)
    return task


