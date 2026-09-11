import os
import tempfile
from pathlib import Path

# 设置测试环境隔离变量
temp_dir = Path(tempfile.mkdtemp())
os.environ["APP_ENV"] = "test"
os.environ["DB_PATH"] = str(temp_dir / "test_tasks.db")

import app.db.database as database
from app.config import settings

database.init_db()


from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    res = client.get("/api/health").json()
    assert res["status"] == "ok"
    assert "model_path" in res


def test_upload_and_get_task():
    response = client.post(
        "/api/tasks/upload",
        files={"file": ("chat.txt", b"hello", "text/plain")},
        data={"report_date": "2099-01-01"},
    )
    assert response.status_code == 200
    task = response.json()
    assert client.get(f"/api/tasks/{task['id']}").status_code == 200


def test_reject_extension():
    response = client.post(
        "/api/tasks/upload",
        files={"file": ("virus.exe", b"x", "application/octet-stream")},
        data={"report_date": "2099-01-01"},
    )
    assert response.status_code == 415


def test_refine_task_section():
    task_id = "test_refine_123"
    task = {
        "id": task_id,
        "filename": "chat.txt",
        "report_date": "2099-01-01",
        "status": "completed",
        "status_label": "已完成",
        "stage_index": 3,
        "progress": 100,
        "message": "已完成",
        "report": {"summary": "原始氛围总结"},
    }
    database.db_save_task(task)

    res = client.post(
        f"/api/tasks/{task_id}/refine",
        json={
            "section_feedback": {
                "section_key": "summary",
                "rating": 5,
                "instruction": "修改总结，使其更加活泼",
            }
        },
    )
    assert res.status_code == 200
    res_json = res.json()
    assert res_json["id"] == task_id
    assert "report" in res_json
    assert "refine_history" in res_json
    assert len(res_json["refine_history"]) == 1
    assert res_json["refine_history"][0]["instruction"] == "修改总结，使其更加活泼"

    # 第二次增量微调测试，验证历史会话轨迹拼接与累加保存
    res2 = client.post(
        f"/api/tasks/{task_id}/refine",
        json={
            "section_feedback": {
                "section_key": "summary",
                "rating": 4,
                "instruction": "再次补充关于炒股和宝妈的交流案例",
            }
        },
    )
    assert res2.status_code == 200
    res2_json = res2.json()
    assert len(res2_json["refine_history"]) == 2
    assert res2_json["refine_history"][1]["instruction"] == "再次补充关于炒股和宝妈的交流案例"



def test_regenerate_task():
    # 上传一个临时任务文件
    response = client.post(
        "/api/tasks/upload",
        files={"file": ("chat.txt", b"hello chat log", "text/plain")},
        data={"report_date": "2099-01-01"},
    )
    assert response.status_code == 200
    task = response.json()
    task_id = task["id"]

    # 触发重新生成 API
    res_regen = client.post(f"/api/tasks/{task_id}/regenerate")
    assert res_regen.status_code == 200
    regen_data = res_regen.json()
    assert regen_data["id"] == task_id
    assert regen_data["status"] == "processing"

    res_now = client.post("/api/backup/now")
    assert res_now.status_code == 200
    data = res_now.json()
    assert data["status"] == "success"
    assert "filepath" in data

    res_list = client.get("/api/backup/list")
    assert res_list.status_code == 200
    backups = res_list.json()["backups"]
    assert len(backups) > 0

