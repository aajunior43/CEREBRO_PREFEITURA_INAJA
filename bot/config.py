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

DB_PATH = str(Path(__file__).resolve().parent.parent / 'empenhos.db')
SERVER_URL = os.environ.get('SERVER_URL', 'http://localhost:5000').rstrip('/')
CONFIG_FILE = Path(__file__).resolve().parent.parent / 'config.json'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger('telegram_bot')

def get_config(key: str, default=''):
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                c = json.load(f)
                return c.get(key, default)
    except Exception:
        pass
    return default
