import os
import logging
import json
from pathlib import Path

# Load .env variables manually to avoid dotenv dependency
_ENV_FILE = Path(__file__).resolve().parent.parent / '.env'
if _ENV_FILE.exists():
    with open(_ENV_FILE, encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '').strip()
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
DEFAULT_TELEGRAM_CHAT_ID = '942288759'

DB_PATH = str(Path(__file__).resolve().parent.parent / 'empenhos.db')
SERVER_URL = os.environ.get('SERVER_URL', 'http://localhost:5000').rstrip('/')
CONFIG_FILE = Path(__file__).resolve().parent.parent / 'config.json'
CHAT_TARGETS_FILE = Path(__file__).resolve().parent.parent / 'telegram_chat_ids.txt'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger('telegram_bot')

def get_target_chat_ids() -> list[str]:
    def _clean_ids(raw: str) -> list[str]:
        ids: list[str] = []
        for chunk in str(raw).replace('\n', ',').split(','):
            chunk = chunk.strip()
            if not chunk:
                continue
            if ':' in chunk:
                chunk = chunk.split(':')[-1].strip()
            ids.append(chunk)
        return ids

    env_ids = _clean_ids(TELEGRAM_CHAT_ID)
    if DEFAULT_TELEGRAM_CHAT_ID not in env_ids:
        env_ids.insert(0, DEFAULT_TELEGRAM_CHAT_ID)
    try:
        if CHAT_TARGETS_FILE.exists():
            raw = CHAT_TARGETS_FILE.read_text(encoding='utf-8')
            file_ids = _clean_ids(raw)
            env_ids.extend(file_ids)
    except Exception as e:
        logger.error(f"Erro ao ler destinos do Telegram: {e}")
    unique_ids: list[str] = []
    for cid in env_ids:
        if cid and cid not in unique_ids:
            unique_ids.append(cid)
    return unique_ids[:20]

def remember_chat_id(chat_id) -> None:
    if chat_id is None:
        return
    chat_id = str(chat_id).strip()
    if not chat_id:
        return
    try:
        current = get_target_chat_ids()
        merged = [chat_id] + [cid for cid in current if cid != chat_id]
        CHAT_TARGETS_FILE.write_text('\n'.join(merged[:20]), encoding='utf-8')
    except Exception as e:
        logger.error(f"Erro ao salvar chat_id do Telegram: {e}")

def get_config(key: str, default=''):
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                c = json.load(f)
                return c.get(key, default)
    except Exception:
        pass
    return default
