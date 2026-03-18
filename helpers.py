import os
import sys
import time as _time
import threading
from collections import defaultdict

_SERVER_START = _time.time()

_TERM_COLORS = {
    'reset': '\033[0m',
    'dim': '\033[2m',
    'bold': '\033[1m',
    'cyan': '\033[36m',
    'green': '\033[32m',
    'yellow': '\033[33m',
    'red': '\033[31m',
    'magenta': '\033[35m',
}

try:
    if os.name == 'nt':
        os.system('')
except Exception:
    pass


def _term_enabled() -> bool:
    return sys.stdout.isatty()


def _color(text: str, name: str) -> str:
    if not _term_enabled():
        return text
    return f"{_TERM_COLORS.get(name, '')}{text}{_TERM_COLORS['reset']}"


def _fmt_bytes(num: int) -> str:
    if num < 1024:
        return f'{num} B'
    if num < 1024 * 1024:
        return f'{num / 1024:.1f} KB'
    return f'{num / (1024 * 1024):.1f} MB'


def _terminal_log(kind: str, message: str, color_name: str = 'cyan'):
    ts = _time.strftime('%H:%M:%S')
    prefix = _color(f'[{ts}] [{kind}]', color_name)
    print(f'{prefix} {message}')


def _terminal_request_line(method: str, path: str, status_code: int, elapsed_ms: float, client_ip: str = ''):
    if status_code >= 500:
        tone = 'red'
        icon = 'ERR'
    elif status_code >= 400:
        tone = 'yellow'
        icon = 'WARN'
    elif elapsed_ms >= 800:
        tone = 'magenta'
        icon = 'SLOW'
    else:
        tone = 'green'
        icon = 'OK'
    ip_label = client_ip or '-'
    _terminal_log(icon, f'{ip_label:<15} {method:<6} {status_code:<3} {elapsed_ms:>7.1f} ms  {path}', tone)


def _terminal_section(title: str):
    line = '─' * 72
    print(_color(line, 'dim'))
    print(_color(title, 'bold'))


_rate_buckets: dict[str, list[float]] = defaultdict(list)
_RATE_LOCK = threading.Lock()


def _rate_limited(key: str, max_hits: int = 5, window: int = 60) -> bool:
    now = _time.time()
    with _RATE_LOCK:
        hits = _rate_buckets[key]
        _rate_buckets[key] = [t for t in hits if now - t < window]
        if len(_rate_buckets[key]) >= max_hits:
            return True
        _rate_buckets[key].append(now)
        return False


def _parse_bool(value) -> bool:
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'on', 'sim'}
