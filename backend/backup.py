import sys
from pathlib import Path

# Ensure app package is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db.backup import perform_backup, list_backups

if __name__ == "__main__":
    print("[Backup] 正在启动数据安全定期备份...")
    res = perform_backup()
    if res.get("status") == "success":
        print(f"[Success] 备份成功！文件已存至: {res['filepath']}")
        print(f"  - 备份文件名: {res['filename']}")
        print(f"  - 打包大小: {round(res['size_bytes'] / 1024, 2)} KB")
        print(f"  - 打包文件数: {res['file_count']} 个\n")

        print("[List] 现有备份文件列表:")
        for b in list_backups():
            print(f"  - {b['filename']} ({round(b['size_bytes'] / 1024, 2)} KB, 时间: {b['created_at']})")
    else:
        print(f"[Error] 备份失败: {res.get('message')}")

