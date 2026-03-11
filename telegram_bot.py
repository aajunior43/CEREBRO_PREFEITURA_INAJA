"""
telegram_bot.py — Bot do Telegram para o Sistema da Prefeitura de Inajá
=======================================================================

Funcionalidades nesta versão:
  - /start       → Menu principal com botões
  - /tarefa      → Adicionar tarefa no Kanban (conversa guiada passo a passo)
  - /tarefas     → Listar tarefas abertas no Kanban
  - /cancelar    → Cancela qualquer operação em andamento

Para rodar:
  1. Instale: pip install python-telegram-bot requests
  2. Configure o .env com TELEGRAM_TOKEN e TELEGRAM_CHAT_ID
  3. Execute: python telegram_bot.py
  Ou use: bot.bat
"""

import os
import json
import uuid
import logging
import sqlite3
import requests
import threading
from datetime import datetime
from pathlib import Path

# ── Carrega .env simples sem depender de python-dotenv ──────────────────────
_ENV_FILE = Path(__file__).resolve().parent / '.env'
if _ENV_FILE.exists():
    with open(_ENV_FILE, encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# ── Configurações ────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_TOKEN', '').strip()
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '').strip()   # seu chat_id (segurança)

# Caminho do banco SQLite (mesmo diretório do projet)
DB_PATH = str(Path(__file__).resolve().parent / 'empenhos.db')

# URL base da API local (o server.py deve estar rodando)
SERVER_URL = os.environ.get('SERVER_URL', 'http://localhost:5000').rstrip('/')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger('telegram_bot')

# ── Verificação inicial ──────────────────────────────────────────────────────
if not TELEGRAM_TOKEN:
    print("=" * 60)
    print("ERRO: TELEGRAM_TOKEN não configurado!")
    print("Crie o arquivo .env com:")
    print("  TELEGRAM_TOKEN=seu_token_aqui")
    print("  TELEGRAM_CHAT_ID=seu_chat_id_aqui")
    print("=" * 60)
    raise SystemExit(1)

TELEGRAM_API = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}'

# ── Estado de conversas ──────────────────────────────────────────────────────
# Armazena o contexto de cada usuário durante uma conversa multi-etapa
_conversation_state: dict[int, dict] = {}
_state_lock = threading.Lock()

STEP_TITLE       = 'aguardando_titulo'
STEP_DESC        = 'aguardando_descricao'
STEP_STATUS      = 'aguardando_status'
STEP_PRIORITY    = 'aguardando_prioridade'


# ════════════════════════════════════════════════════════════════════════════
# Helpers de DB (leitura direta, sem precisar que o server.py esteja no ar)
# ════════════════════════════════════════════════════════════════════════════

def _db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def db_listar_tarefas(status_filter: str | None = None) -> list[dict]:
    """Retorna tarefas do Kanban. Filtra por status se informado."""
    conn = _db_connect()
    try:
        if status_filter:
            rows = conn.execute(
                "SELECT id, title, description, status, priority, criado_em "
                "FROM kanban_tasks WHERE status=? ORDER BY criado_em DESC LIMIT 30",
                (status_filter,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, description, status, priority, criado_em "
                "FROM kanban_tasks ORDER BY criado_em DESC LIMIT 30"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def db_criar_tarefa(title: str, description: str, status: str, priority: str) -> dict:
    """Cria tarefa diretamente no banco (não depende do server.py)."""
    task_id = str(uuid.uuid4())
    conn = _db_connect()
    try:
        conn.execute(
            "INSERT INTO kanban_tasks (id, title, description, status, priority, "
            "criado_em, atualizado_em) VALUES (?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))",
            (task_id, title, description, status, priority)
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, title, description, status, priority, criado_em FROM kanban_tasks WHERE id=?",
            (task_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════════
# Helpers do Telegram API (HTTP polling simples, sem biblioteca externa)
# ════════════════════════════════════════════════════════════════════════════

def tg_request(method: str, payload: dict = None, timeout: int = 30) -> dict:
    """Faz requisição à Telegram Bot API."""
    url = f'{TELEGRAM_API}/{method}'
    try:
        r = requests.post(url, json=payload or {}, timeout=timeout)
        return r.json()
    except Exception as e:
        log.error('Erro na chamada Telegram API %s: %s', method, e)
        return {'ok': False}


def send_message(chat_id: int, text: str, reply_markup: dict = None,
                 parse_mode: str = 'HTML') -> dict:
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode,
    }
    if reply_markup:
        payload['reply_markup'] = reply_markup
    return tg_request('sendMessage', payload)


def edit_message(chat_id: int, message_id: int, text: str,
                 reply_markup: dict = None, parse_mode: str = 'HTML') -> dict:
    payload = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text,
        'parse_mode': parse_mode,
    }
    if reply_markup:
        payload['reply_markup'] = reply_markup
    return tg_request('editMessageText', payload)


def answer_callback(callback_query_id: str, text: str = '', show_alert: bool = False):
    tg_request('answerCallbackQuery', {
        'callback_query_id': callback_query_id,
        'text': text,
        'show_alert': show_alert
    })


# ════════════════════════════════════════════════════════════════════════════
# Teclados e menus
# ════════════════════════════════════════════════════════════════════════════

def keyboard_main():
    """Teclado inline do menu principal."""
    return {
        'inline_keyboard': [
            [
                {'text': '➕ Nova Tarefa', 'callback_data': 'cmd_nova_tarefa'},
                {'text': '📋 Ver Tarefas', 'callback_data': 'cmd_ver_tarefas'},
            ],
            [
                {'text': '⚡ Em Progresso', 'callback_data': 'cmd_ver_progresso'},
                {'text': '✅ Concluídas',   'callback_data': 'cmd_ver_concluidas'},
            ],
            [
                {'text': '🔄 Atualizar',   'callback_data': 'cmd_menu'},
            ],
        ]
    }


def keyboard_status():
    return {
        'inline_keyboard': [
            [
                {'text': '📋 A Fazer',      'callback_data': 'status_todo'},
                {'text': '⚡ Em Progresso', 'callback_data': 'status_in-progress'},
            ],
            [
                {'text': '✅ Concluído',   'callback_data': 'status_done'},
            ],
            [{'text': '❌ Cancelar',       'callback_data': 'cmd_cancelar'}],
        ]
    }


def keyboard_priority():
    return {
        'inline_keyboard': [
            [
                {'text': '🔴 Alta',   'callback_data': 'prio_high'},
                {'text': '🟡 Média',  'callback_data': 'prio_medium'},
                {'text': '🟢 Baixa',  'callback_data': 'prio_low'},
            ],
            [{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}],
        ]
    }


def keyboard_skip_or_cancel():
    return {
        'inline_keyboard': [
            [
                {'text': '⏭ Pular descrição', 'callback_data': 'desc_skip'},
                {'text': '❌ Cancelar',        'callback_data': 'cmd_cancelar'},
            ]
        ]
    }


# ════════════════════════════════════════════════════════════════════════════
# Formatação de respostas
# ════════════════════════════════════════════════════════════════════════════

STATUS_EMOJI  = {'todo': '📋', 'in-progress': '⚡', 'done': '✅'}
STATUS_LABEL  = {'todo': 'A Fazer', 'in-progress': 'Em Progresso', 'done': 'Concluído'}
PRIO_EMOJI    = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}
PRIO_LABEL    = {'high': 'Alta', 'medium': 'Média', 'low': 'Baixa'}


def format_task_list(tasks: list[dict], title: str) -> str:
    if not tasks:
        return f'<b>{title}</b>\n\n<i>Nenhuma tarefa encontrada.</i>'
    lines = [f'<b>{title}</b>\n']
    for t in tasks[:20]:
        s = t.get('status', 'todo')
        p = t.get('priority', 'medium')
        emoji_s = STATUS_EMOJI.get(s, '📋')
        emoji_p = PRIO_EMOJI.get(p, '🟡')
        title_t = t.get('title', '(sem título)')
        desc = t.get('description', '')
        desc_preview = f'\n     <i>{desc[:60]}{"…" if len(desc) > 60 else ""}</i>' if desc else ''
        lines.append(f'{emoji_s} {emoji_p} <b>{title_t}</b>{desc_preview}')
    if len(tasks) > 20:
        lines.append(f'\n<i>… e mais {len(tasks) - 20} tarefas</i>')
    return '\n'.join(lines)


def format_task_created(task: dict) -> str:
    s  = task.get('status', 'todo')
    p  = task.get('priority', 'medium')
    return (
        f'✅ <b>Tarefa criada com sucesso!</b>\n\n'
        f'📝 <b>Título:</b> {task.get("title")}\n'
        f'{("📄 <b>Descrição:</b> " + task.get("description") + chr(10)) if task.get("description") else ""}'
        f'{STATUS_EMOJI.get(s, "📋")} <b>Status:</b> {STATUS_LABEL.get(s, s)}\n'
        f'{PRIO_EMOJI.get(p, "🟡")} <b>Prioridade:</b> {PRIO_LABEL.get(p, p)}\n\n'
        f'<i>Acesse o sistema para ver no Kanban.</i>'
    )


def menu_text() -> str:
    """Texto do menu principal com resumo das tarefas."""
    try:
        todo  = len(db_listar_tarefas('todo'))
        prog  = len(db_listar_tarefas('in-progress'))
        done  = len(db_listar_tarefas('done'))
    except Exception:
        todo = prog = done = '?'

    return (
        f'🏛 <b>Prefeitura de Inajá — Kanban</b>\n\n'
        f'📋 A Fazer: <b>{todo}</b>  ⚡ Em Progresso: <b>{prog}</b>  ✅ Concluídas: <b>{done}</b>\n\n'
        f'Escolha uma opção:'
    )


# ════════════════════════════════════════════════════════════════════════════
# Controle de estado de conversa
# ════════════════════════════════════════════════════════════════════════════

def get_state(chat_id: int) -> dict | None:
    with _state_lock:
        return _conversation_state.get(chat_id)


def set_state(chat_id: int, state: dict):
    with _state_lock:
        _conversation_state[chat_id] = state


def clear_state(chat_id: int):
    with _state_lock:
        _conversation_state.pop(chat_id, None)


# ════════════════════════════════════════════════════════════════════════════
# Verificação de acesso
# ════════════════════════════════════════════════════════════════════════════

def is_authorized(chat_id: int) -> bool:
    """Permite acesso se TELEGRAM_CHAT_ID não estiver configurado (modo aberto)
    ou se o chat_id bater com o configurado."""
    if not TELEGRAM_CHAT_ID:
        return True
    # suporta múltiplos IDs separados por vírgula
    allowed = {cid.strip() for cid in TELEGRAM_CHAT_ID.split(',') if cid.strip()}
    return str(chat_id) in allowed


# ════════════════════════════════════════════════════════════════════════════
# Handlers de mensagens e callbacks
# ════════════════════════════════════════════════════════════════════════════

def handle_message(msg: dict):
    """Processa mensagens de texto recebidas."""
    chat_id = msg['chat']['id']
    text    = (msg.get('text') or '').strip()

    if not is_authorized(chat_id):
        send_message(chat_id, '⛔ Acesso negado.')
        return

    # Comandos
    if text.startswith('/start') or text.startswith('/menu'):
        clear_state(chat_id)
        send_message(chat_id, menu_text(), reply_markup=keyboard_main())
        return

    if text.startswith('/tarefa') or text.lower() in {'nova tarefa', 'nova', 'criar tarefa'}:
        start_new_task_flow(chat_id)
        return

    if text.startswith('/tarefas'):
        tasks = db_listar_tarefas()
        send_message(chat_id, format_task_list(tasks, '📋 Todas as Tarefas'),
                     reply_markup={'inline_keyboard': [[
                         {'text': '🔙 Menu', 'callback_data': 'cmd_menu'}
                     ]]})
        return

    if text.startswith('/cancelar') or text.lower() == 'cancelar':
        clear_state(chat_id)
        send_message(chat_id, '❌ Operação cancelada.', reply_markup=keyboard_main())
        return

    # Verificar se estamos no meio de um fluxo de criação de tarefa
    state = get_state(chat_id)
    if state:
        handle_conversation_step(chat_id, text, state)
    else:
        # Sem contexto — mostrar menu
        send_message(chat_id, menu_text(), reply_markup=keyboard_main())


def handle_callback(callback_query: dict):
    """Processa botões inline (callback_data)."""
    query_id = callback_query['id']
    chat_id  = callback_query['from']['id']
    msg_id   = callback_query['message']['message_id']
    data     = callback_query.get('data', '')

    if not is_authorized(chat_id):
        answer_callback(query_id, '⛔ Acesso negado.', show_alert=True)
        return

    answer_callback(query_id)  # fecha o "carregando..." do botão

    # Menu principal
    if data == 'cmd_menu':
        clear_state(chat_id)
        edit_message(chat_id, msg_id, menu_text(), reply_markup=keyboard_main())
        return

    if data == 'cmd_nova_tarefa':
        start_new_task_flow(chat_id, edit_msg=(chat_id, msg_id))
        return

    if data == 'cmd_cancelar':
        clear_state(chat_id)
        edit_message(chat_id, msg_id, '❌ Operação cancelada.\n\n' + menu_text(),
                     reply_markup=keyboard_main())
        return

    if data == 'cmd_ver_tarefas':
        tasks = db_listar_tarefas()
        edit_message(chat_id, msg_id, format_task_list(tasks, '📋 Todas as Tarefas'),
                     reply_markup={'inline_keyboard': [[
                         {'text': '🔙 Menu', 'callback_data': 'cmd_menu'}
                     ]]})
        return

    if data == 'cmd_ver_progresso':
        tasks = db_listar_tarefas('in-progress')
        edit_message(chat_id, msg_id, format_task_list(tasks, '⚡ Em Progresso'),
                     reply_markup={'inline_keyboard': [[
                         {'text': '🔙 Menu', 'callback_data': 'cmd_menu'}
                     ]]})
        return

    if data == 'cmd_ver_concluidas':
        tasks = db_listar_tarefas('done')
        edit_message(chat_id, msg_id, format_task_list(tasks, '✅ Concluídas'),
                     reply_markup={'inline_keyboard': [[
                         {'text': '🔙 Menu', 'callback_data': 'cmd_menu'}
                     ]]})
        return

    # Dentro do fluxo de criação de tarefa
    state = get_state(chat_id)
    if not state:
        edit_message(chat_id, msg_id, '⚠️ Sessão expirada. Recomeçando...')
        start_new_task_flow(chat_id)
        return

    # Pular descrição
    if data == 'desc_skip' and state.get('step') == STEP_DESC:
        state['description'] = ''
        state['step'] = STEP_STATUS
        set_state(chat_id, state)
        send_message(
            chat_id,
            '3️⃣ <b>Status da tarefa?</b>',
            reply_markup=keyboard_status()
        )
        return

    # Selecionar status
    if data.startswith('status_') and state.get('step') == STEP_STATUS:
        status_val = data[len('status_'):]
        if status_val not in {'todo', 'in-progress', 'done'}:
            status_val = 'todo'
        state['status'] = status_val
        state['step']   = STEP_PRIORITY
        set_state(chat_id, state)
        send_message(
            chat_id,
            '4️⃣ <b>Prioridade da tarefa?</b>',
            reply_markup=keyboard_priority()
        )
        return

    # Selecionar prioridade → criar tarefa
    if data.startswith('prio_') and state.get('step') == STEP_PRIORITY:
        prio_val = data[len('prio_'):]
        if prio_val not in {'high', 'medium', 'low'}:
            prio_val = 'medium'
        state['priority'] = prio_val
        clear_state(chat_id)

        try:
            task = db_criar_tarefa(
                title=state.get('title', 'Sem título'),
                description=state.get('description', ''),
                status=state.get('status', 'todo'),
                priority=prio_val
            )
            send_message(
                chat_id,
                format_task_created(task),
                reply_markup={'inline_keyboard': [[
                    {'text': '➕ Nova Tarefa', 'callback_data': 'cmd_nova_tarefa'},
                    {'text': '🔙 Menu',        'callback_data': 'cmd_menu'},
                ]]}
            )
            log.info('Tarefa criada via Telegram: [%s] %s', task.get('id'), task.get('title'))
        except Exception as e:
            log.error('Erro ao criar tarefa: %s', e)
            send_message(chat_id, f'❌ Erro ao criar tarefa: {e}\n\nTente novamente.',
                         reply_markup=keyboard_main())
        return


def start_new_task_flow(chat_id: int, edit_msg: tuple = None):
    """Inicia o fluxo guiado de criação de tarefa."""
    state = {'step': STEP_TITLE, 'title': '', 'description': '', 'status': 'todo', 'priority': 'medium'}
    set_state(chat_id, state)

    text = (
        '➕ <b>Nova Tarefa no Kanban</b>\n\n'
        '1️⃣ <b>Qual é o título da tarefa?</b>\n'
        '<i>Digite o nome/título abaixo:</i>'
    )
    kb = {'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]}

    if edit_msg:
        edit_message(edit_msg[0], edit_msg[1], text, reply_markup=kb)
    else:
        send_message(chat_id, text, reply_markup=kb)


def handle_conversation_step(chat_id: int, text: str, state: dict):
    """Avança a conversa de criação de tarefa com base na etapa atual."""
    step = state.get('step')

    if step == STEP_TITLE:
        if len(text) < 2:
            send_message(chat_id, '⚠️ Título muito curto. Por favor, digite um título com pelo menos 2 caracteres.')
            return
        if len(text) > 200:
            send_message(chat_id, '⚠️ Título muito longo (máx. 200 caracteres). Tente resumir.')
            return
        state['title'] = text
        state['step']  = STEP_DESC
        set_state(chat_id, state)
        send_message(
            chat_id,
            f'✅ Título: <b>{text}</b>\n\n'
            '2️⃣ <b>Descrição</b> (opcional):\n'
            '<i>Digite uma descrição ou clique em "Pular" para deixar em branco.</i>',
            reply_markup=keyboard_skip_or_cancel()
        )

    elif step == STEP_DESC:
        state['description'] = text[:500]  # limita a 500 chars
        state['step']        = STEP_STATUS
        set_state(chat_id, state)
        send_message(
            chat_id,
            '3️⃣ <b>Status da tarefa?</b>',
            reply_markup=keyboard_status()
        )

    elif step in (STEP_STATUS, STEP_PRIORITY):
        # Usuário digitou texto em vez de usar os botões
        send_message(
            chat_id,
            '👆 Por favor, use os botões acima para selecionar.'
        )


# ════════════════════════════════════════════════════════════════════════════
# Polling loop
# ════════════════════════════════════════════════════════════════════════════

def run_polling():
    log.info('🤖 Bot do Telegram iniciado! Aguardando mensagens...')
    if TELEGRAM_CHAT_ID:
        log.info('🔒 Acesso restrito ao(s) chat_id(s): %s', TELEGRAM_CHAT_ID)
    else:
        log.warning('⚠️  TELEGRAM_CHAT_ID não configurado — bot aceita qualquer usuário!')

    offset = None
    while True:
        try:
            params: dict = {'timeout': 30, 'allowed_updates': ['message', 'callback_query']}
            if offset is not None:
                params['offset'] = offset

            resp = requests.post(
                f'{TELEGRAM_API}/getUpdates',
                json=params,
                timeout=40
            )
            data = resp.json()

            if not data.get('ok'):
                log.error('getUpdates retornou erro: %s', data)
                import time; time.sleep(5)
                continue

            for update in data.get('result', []):
                offset = update['update_id'] + 1
                try:
                    if 'message' in update:
                        handle_message(update['message'])
                    elif 'callback_query' in update:
                        handle_callback(update['callback_query'])
                except Exception as e:
                    log.error('Erro ao processar update %s: %s', update.get('update_id'), e)

        except requests.exceptions.Timeout:
            pass  # normal — long polling
        except requests.exceptions.ConnectionError as e:
            log.warning('Sem conexão com o Telegram: %s — tentando novamente em 10s', e)
            import time; time.sleep(10)
        except Exception as e:
            log.error('Erro inesperado no loop de polling: %s', e)
            import time; time.sleep(5)


if __name__ == '__main__':
    run_polling()
