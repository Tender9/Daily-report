import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# 环境配置隔离：支持根据 APP_ENV 加载对应的 .env 文件
raw_env = os.getenv("APP_ENV", "development").lower()
env_file_name = f".env.{raw_env}" if (BASE_DIR / f".env.{raw_env}").exists() else ".env"
env_path = BASE_DIR / env_file_name
load_dotenv(dotenv_path=env_path)


class Settings:
    @property
    def APP_ENV(self) -> str:
        return os.getenv("APP_ENV", "development").lower()

    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "2001"))
    CORS_ORIGINS: list[str] = [
        origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:1001").split(",") if origin.strip()
    ]
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20"))
    MAX_UPLOAD_SIZE_BYTES: int = MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # 数据库路径与上传目录环境隔离
    @property
    def DB_PATH(self) -> Path:
        custom_db = os.getenv("DB_PATH")
        if custom_db:
            return Path(custom_db) if Path(custom_db).is_absolute() else (BASE_DIR / custom_db).resolve()
        if self.APP_ENV == "test":
            return BASE_DIR / "tasks_test.db"
        elif self.APP_ENV == "development":
            return BASE_DIR / "tasks_dev.db" if (BASE_DIR / "tasks_dev.db").exists() else BASE_DIR / "tasks.db"
        return BASE_DIR / "tasks.db"

    @property
    def UPLOAD_DIR(self) -> Path:
        if self.APP_ENV == "test":
            return BASE_DIR / "uploads_test"
        return BASE_DIR / "uploads"

    # 定期自动数据备份目录与保留天数配置
    BACKUP_DIR: Path = BASE_DIR / "backups"
    BACKUP_RETENTION_DAYS: int = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))
    AUTO_BACKUP_ENABLED: bool = os.getenv("AUTO_BACKUP_ENABLED", "true").lower() == "true"

    # GGUF Local Model Settings
    MODEL_MODE: str = os.getenv("MODEL_MODE", "local_gguf")

    _raw_model_path: str = os.getenv("MODEL_PATH", "models/MiniCPM-V-4_6-Thinking-Q4_K_M.gguf")
    _raw_mmproj_path: str = os.getenv("MMPROJ_PATH", "models/mmproj-model-f16.gguf")

    @property
    def MODEL_PATH(self) -> Path:
        p = Path(self._raw_model_path)
        return p if p.is_absolute() else (BASE_DIR / p).resolve()

    @property
    def MMPROJ_PATH(self) -> Path:
        p = Path(self._raw_mmproj_path)
        return p if p.is_absolute() else (BASE_DIR / p).resolve()

    N_CTX: int = int(os.getenv("N_CTX", "4096"))
    N_GPU_LAYERS: int = int(os.getenv("N_GPU_LAYERS", "-1"))

    # AI Provider Switch: "local" (GGUF) or "cloud" (Volcengine Ark API)
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "local").lower()

    # Volcengine Ark Cloud API Settings
    CLOUD_API_URL: str = os.getenv("CLOUD_API_URL", "https://ark.cn-beijing.volces.com/api/v3/responses")
    CLOUD_API_KEY: str = os.getenv("CLOUD_API_KEY", "e62aecd8-aaab-4856-9a84-c0feeab1b9e2")
    CLOUD_MODEL: str = os.getenv("CLOUD_MODEL", "doubao-seed-1-6-251015")


settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
