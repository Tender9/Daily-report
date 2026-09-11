# 群聊日报

个人使用的 AI 群聊日报工具，采用标准 Monorepo 目录结构。

## 技术栈

- 前端：Vue 3 + Vite + TypeScript
- 后端：Python + FastAPI，使用 uv 管理环境
- 数据库：PostgreSQL 连接配置预留；任务状态使用 SQLite 缓存

## 端口

- 前端：`1001`
- 后端：`2001`

## 启动

### ⚡ 一键启动（推荐）

可以通过 Python 或 npm 脚本一键同时启动前端与后端：

```bash
# 方式一：使用 Python 脚本
python start.py

# 方式二：使用 npm 脚本
npm start
```

### 🛠️ 分步手动启动

```bash
# 启动前端 (Port 1001)
cd frontend
npm install
npm run dev

# 启动后端 (Port 2001)
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 2001
```

前端地址：`http://localhost:1001`

## 🎨 代码格式化

项目已对齐 `python_rz` 规范，配置了前端 Prettier 与后端 Ruff 格式化工具：

```bash
# 根目录一键格式化全栈代码
npm run format

# 仅格式化前端 Vue / TS 代码
npm run format:frontend

# 仅格式化后端 Python 代码
npm run format:backend
```

## 🛡️ 环境隔离与数据备份

### 1. 环境隔离 (Environment Isolation)

项目支持通过 `APP_ENV` 环境变量隔离不同运行环境的数据与文件：

- `development` (开发环境，默认): 使用 `tasks_dev.db` (或 `tasks.db`) 与 `uploads/`
- `production` (生产环境): 使用 `tasks.db` 与 `uploads/`
- `test` (测试环境): 使用 `tasks_test.db` 与 `uploads_test/`

通过在 `.env` 或启动命令中设置 `APP_ENV` 即可自动切分环境：
```bash
# 启动生产环境
APP_ENV=production python start.py
```

### 2. 定期数据备份 (Scheduled Backup)

系统支持 SQLite 数据库热快照 (`conn.backup()`) 与 `uploads/` 上传附件打包归档，备份文件压缩保存至 `backend/backups/` 目录，并自动清理超期备份 (默认保留 7 天)。

- **CLI 手动/定时任务备份**：
  ```bash
  # 根目录执行备份
  npm run backup

  # 或在 backend 目录下直接执行
  cd backend && uv run python backup.py
  ```
- **HTTP API 动态触发**：
  - `POST /api/backup/now`：立即触发数据热备份
  - `GET /api/backup/list`：查询历史备份文件列表与占用空间

## 目录

```text
.
├── backend/     FastAPI 后端 (包含 db, backups, uploads)
├── frontend/    Vue 3 前端
├── start.py     Python 一键启动脚本
├── start.js     Node.js 一键启动脚本
├── package.json 根目录脚本配置
└── README.md
```

