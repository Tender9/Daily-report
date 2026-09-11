import os
import sys
import subprocess
import time

# 确保在 Windows 环境下 stdout 支持 UTF-8 打印
if sys.platform.startswith("win"):
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(root_dir, "backend")
    frontend_dir = os.path.join(root_dir, "frontend")

    is_win = sys.platform.startswith("win")

    print("[1/2] 正在启动后端服务 (FastAPI / Port 2001)...")
    backend_cmd = ["uv", "run", "uvicorn", "app.main:app", "--reload", "--port", "2001"]
    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=backend_dir,
        shell=is_win
    )

    print("[2/2] 正在启动前端服务 (Vue3 + Vite / Port 1001)...")
    frontend_cmd = ["npm", "run", "dev"]
    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=frontend_dir,
        shell=is_win
    )

    print("\n[+] 所有服务已并发启动！")
    print("  - 前端地址: http://localhost:1001")
    print("  - 后端 API: http://localhost:2001\n")
    print("按 Ctrl+C 可一键停止所有服务...\n")

    try:
        while True:
            b_poll = backend_proc.poll()
            f_poll = frontend_proc.poll()
            if b_poll is not None:
                print(f"[-] 后端服务已退出 (Exit code: {b_poll})")
                break
            if f_poll is not None:
                print(f"[-] 前端服务已退出 (Exit code: {f_poll})")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[*] 正在停止所有服务...")
    finally:
        for proc in (backend_proc, frontend_proc):
            if proc and proc.poll() is None:
                try:
                    if is_win:
                        subprocess.run(f"taskkill /F /T /PID {proc.pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        proc.terminate()
                except Exception:
                    pass
        print("[+] 所有服务已全部停止！")

if __name__ == "__main__":
    main()
