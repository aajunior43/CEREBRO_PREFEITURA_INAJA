import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    base_dir: Path = BASE_DIR
    db_path: Path = BASE_DIR / 'empenhos.db'
    data_js_path: Path = BASE_DIR / 'data.js'
    log_dir: Path = BASE_DIR / 'logs'
    log_file: Path = BASE_DIR / 'logs' / 'server.log'
    host: str = os.environ.get('APP_HOST', '0.0.0.0')
    port: int = int(os.environ.get('APP_PORT', '5000'))
    debug: bool = os.environ.get('APP_DEBUG', '').strip().lower() in {'1', 'true', 'yes', 'on'}
    admin_password: str = os.environ.get('ADM_PASSWORD', '1999')
    openrouter_default_model: str = os.environ.get('OPENROUTER_DEFAULT_MODEL', 'openai/gpt-4o-mini')
    openrouter_chat_model: str = os.environ.get('OPENROUTER_CHAT_MODEL', 'meta-llama/llama-3.3-70b-instruct:free')
    openrouter_referer: str = os.environ.get('OPENROUTER_REFERER', 'https://localhost')
    openrouter_title: str = os.environ.get('OPENROUTER_TITLE', 'CEREBRO_PREFEITURA')


settings = Settings()
