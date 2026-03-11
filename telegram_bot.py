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
import uuid
import logging
import sqlite3
import requests
import threading
from datetime import date, timedelta
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


PRIO_ORDER = {'high': 0, 'medium': 1, 'low': 2}


def db_listar_tarefas(status_filter: str | None = None) -> list[dict]:
    """Retorna tarefas do Kanban. Filtra por status se informado."""
    conn = _db_connect()
    try:
        if status_filter:
            rows = conn.execute(
                "SELECT id, title, description, status, priority, criado_em "
                "FROM kanban_tasks WHERE status=? ORDER BY criado_em DESC LIMIT 50",
                (status_filter,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, description, status, priority, criado_em "
                "FROM kanban_tasks ORDER BY criado_em DESC LIMIT 50"
            ).fetchall()
        tasks = [dict(r) for r in rows]
        # Ordena por prioridade (alta primeiro) dentro do resultado
        tasks.sort(key=lambda t: PRIO_ORDER.get(t.get('priority', 'medium'), 1))
        return tasks
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
# Calendário — cálculo de eventos automáticos do mês
# ════════════════════════════════════════════════════════════════════════════

_FERIADOS_FIXOS = [
    (1, 1, 'Confraternização Universal'),
    (21, 4, 'Tiradentes'),
    (1, 5, 'Dia do Trabalho'),
    (7, 9, 'Independência do Brasil'),
    (12, 10, 'Nossa Sr.ª Aparecida'),
    (2, 11, 'Finados'),
    (15, 11, 'Proclamação da República'),
    (20, 11, 'Consciência Negra'),
    (25, 12, 'Natal'),
]
_FERIADOS_MOVEIS = {
    '2025-03-03': 'Carnaval', '2025-03-04': 'Carnaval',
    '2025-04-18': 'Paixão de Cristo', '2025-06-19': 'Corpus Christi',
    '2026-02-16': 'Carnaval', '2026-02-17': 'Carnaval',
    '2026-04-03': 'Paixão de Cristo', '2026-06-04': 'Corpus Christi',
    '2027-02-08': 'Carnaval', '2027-02-09': 'Carnaval',
    '2027-03-26': 'Paixão de Cristo', '2027-05-27': 'Corpus Christi',
}


def _eh_feriado(d: date) -> str | None:
    chave = d.strftime('%Y-%m-%d')
    if chave in _FERIADOS_MOVEIS:
        return _FERIADOS_MOVEIS[chave]
    for dia, mes, nome in _FERIADOS_FIXOS:
        if d.day == dia and d.month == mes:
            return nome
    return None


def _eh_dia_util(d: date) -> bool:
    return d.weekday() < 5 and not _eh_feriado(d)


def _proximo_dia_util(ano: int, mes: int, dia_inicio: int) -> int:
    """Retorna o 1º dia útil a partir de dia_inicio no mês."""
    import calendar as _cal
    ultimo = _cal.monthrange(ano, mes)[1]
    for offset in range(10):
        dia = dia_inicio + offset
        if dia > ultimo:
            break
        d = date(ano, mes, dia)
        if _eh_dia_util(d):
            return d.day
    return dia_inicio


def _ultimos_dias_uteis(ano: int, mes: int, qtd: int = 2) -> list[int]:
    """Retorna os últimos N dias úteis do mês."""
    import calendar as _cal
    ultimo = _cal.monthrange(ano, mes)[1]
    encontrados: list[int] = []
    d = date(ano, mes, ultimo)
    while d.day >= 1 and len(encontrados) < qtd:
        if _eh_dia_util(d):
            encontrados.append(d.day)
        if d.day == 1:
            break
        d -= timedelta(days=1)
    return encontrados


def calcular_eventos_mes(ano: int, mes: int) -> list[dict]:
    """Gera a lista de eventos automáticos do mês (igual à lógica do calendario.html)."""
    import calendar as _cal
    ultimo_dia = _cal.monthrange(ano, mes)[1]
    ultimos    = _ultimos_dias_uteis(ano, mes, 2)
    last_biz   = ultimos[0] if len(ultimos) > 0 else None
    second_biz = ultimos[1] if len(ultimos) > 1 else None
    copel_day  = _proximo_dia_util(ano, mes, 15)
    ofic_day10 = _proximo_dia_util(ano, mes, 10)

    eventos: list[dict] = []
    for dia in range(1, ultimo_dia + 1):
        d = date(ano, mes, dia)
        feriado    = _eh_feriado(d)
        fim_semana = d.weekday() >= 5

        if dia == last_biz and not fim_semana:
            eventos.append({'data': d, 'tipo': 'PAYMENT',    'emoji': '💰', 'texto': 'Pagamento Servidores'})
        if dia == ofic_day10 and dia != last_biz:
            eventos.append({'data': d, 'tipo': 'PAYMENT',    'emoji': '💰', 'texto': 'Pagamento Oficineiros'})
        if dia == second_biz and dia not in (last_biz, ofic_day10):
            eventos.append({'data': d, 'tipo': 'COMMITMENT', 'emoji': '📋', 'texto': 'Empenho – Enfermeiras/Estagiários'})
        if dia == copel_day and dia not in (last_biz, ofic_day10, second_biz):
            eventos.append({'data': d, 'tipo': 'COMMITMENT', 'emoji': '📋', 'texto': 'Empenho – Copel e Sanepar'})
        if 5 <= dia <= 7 and not fim_semana and not feriado:
            if not any(e['data'] == d for e in eventos):
                eventos.append({'data': d, 'tipo': 'COMMITMENT', 'emoji': '📋', 'texto': 'Empenho – Oficineiros'})
        if feriado:
            eventos.append({'data': d, 'tipo': 'HOLIDAY', 'emoji': '🏖', 'texto': feriado})

    eventos.sort(key=lambda e: (e['data'], e['tipo']))
    return eventos


def format_calendario(ano: int, mes: int) -> str:
    """Formata o calendário do mês para o Telegram."""
    MESES_PT = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    DIAS_PT  = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']

    hoje    = date.today()
    eventos = calcular_eventos_mes(ano, mes)

    header = f'📅 <b>{MESES_PT[mes]} {ano}</b>\n'
    if not eventos:
        return header + '\n<i>Nenhum evento encontrado para este mês.</i>'

    lines = [header]
    secoes = {
        'PAYMENT':    ('💰 <b>Pagamentos</b>',  []),
        'COMMITMENT': ('📋 <b>Empenhos</b>',    []),
        'HOLIDAY':    ('🏖 <b>Feriados</b>',    []),
    }
    for ev in eventos:
        d          = ev['data']
        dia_semana = DIAS_PT[d.weekday()]
        data_fmt   = f'{d.day:02d}/{mes:02d} ({dia_semana})'
        marcador   = '👉 ' if d == hoje else ''
        linha      = f'{marcador}<code>{data_fmt}</code>  {ev["emoji"]} {ev["texto"]}'
        secao_key  = ev['tipo']
        if secao_key in secoes:
            secoes[secao_key][1].append(linha)

    for secao_key in ('PAYMENT', 'COMMITMENT', 'HOLIDAY'):
        titulo, itens = secoes[secao_key]
        if itens:
            lines.append(titulo)
            lines.extend(itens)
            lines.append('')

    # Próximo evento a partir de hoje
    proximos = [ev for ev in eventos if ev['data'] >= hoje]
    if proximos:
        p     = proximos[0]
        delta = (p['data'] - hoje).days
        if delta == 0:
            aviso = f'⚠️ <b>Hoje:</b> {p["emoji"]} {p["texto"]}'
        elif delta == 1:
            aviso = f'⏰ <b>Amanhã:</b> {p["emoji"]} {p["texto"]}'
        else:
            aviso = f'⏰ <b>Próximo ({delta}d):</b> {p["emoji"]} {p["texto"]}'
        lines.append(aviso)

    return '\n'.join(lines)


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
                {'text': '📅 Calendário',  'callback_data': 'cmd_calendario'},
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


def _format_task_item(t: dict, show_status: bool = False) -> str:
    """Formata uma tarefa individual para exibição no Telegram."""
    p       = t.get('priority', 'medium')
    title_t = t.get('title', '(sem título)')
    desc    = (t.get('description') or '').strip()
    prio_emoji = PRIO_EMOJI.get(p, '🟡')
    status_tag = ''
    if show_status:
        s = t.get('status', 'todo')
        status_tag = f' <code>{STATUS_LABEL.get(s, s)}</code>'
    desc_line = f'\n     └ <i>{desc[:80]}{"…" if len(desc) > 80 else ""}</i>' if desc else ''
    return f'{prio_emoji} <b>{title_t}</b>{status_tag}{desc_line}'


def format_task_list(tasks: list[dict], title: str, grouped: bool = False) -> str:
    """Formata lista de tarefas. Se grouped=True, agrupa por status."""
    if not tasks:
        return f'<b>{title}</b>\n\n<i>Nenhuma tarefa encontrada.</i>'

    if not grouped:
        # Lista simples (usada quando já filtrada por status)
        lines = [f'<b>{title}</b>  <code>{len(tasks)}</code>\n']
        for t in tasks[:25]:
            lines.append(_format_task_item(t))
        if len(tasks) > 25:
            lines.append(f'\n<i>… e mais {len(tasks) - 25} tarefas</i>')
        return '\n'.join(lines)

    # Agrupa por status
    buckets = {'todo': [], 'in-progress': [], 'done': []}
    for t in tasks:
        s = t.get('status', 'todo')
        buckets.setdefault(s, []).append(t)

    lines = [f'<b>{title}</b>\n']
    sections = [
        ('todo',        '📋 A Fazer'),
        ('in-progress', '⚡ Em Progresso'),
        ('done',        '✅ Concluído'),
    ]
    has_any = False
    for status_key, label in sections:
        group = buckets.get(status_key, [])
        if not group:
            continue
        has_any = True
        lines.append(f'<b>{label}</b>  <code>{len(group)}</code>')
        for t in group[:10]:
            lines.append(_format_task_item(t))
        if len(group) > 10:
            lines.append(f'  <i>… e mais {len(group) - 10}</i>')
        lines.append('')  # linha em branco entre seções

    if not has_any:
        return f'<b>{title}</b>\n\n<i>Nenhuma tarefa encontrada.</i>'

    total = len(tasks)
    lines.append(f'<i>Total: {total} tarefa{"s" if total != 1 else ""}</i>')
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

    if text.startswith('/calendario') or text.lower() in {'calendario', 'calendário', 'cal'}:
        hoje = date.today()
        texto = format_calendario(hoje.year, hoje.month)
        kb = {'inline_keyboard': [
            [
                {'text': '⬅ Mês Anterior', 'callback_data': f'cal_{hoje.year}_{hoje.month - 1 if hoje.month > 1 else 12}_{hoje.year if hoje.month > 1 else hoje.year - 1}'},
                {'text': '➡ Próximo Mês',  'callback_data': f'cal_{hoje.year}_{hoje.month + 1 if hoje.month < 12 else 1}_{hoje.year if hoje.month < 12 else hoje.year + 1}'},
            ],
            [{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}],
        ]}
        send_message(chat_id, texto, reply_markup=kb)
        return

    if text.startswith('/tarefas'):
        tasks = db_listar_tarefas()
        send_message(chat_id,
                     format_task_list(tasks, '📋 Todas as Tarefas', grouped=True),
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

    if data == 'cmd_calendario':
        hoje = date.today()
        texto = format_calendario(hoje.year, hoje.month)
        kb = {'inline_keyboard': [
            [
                {'text': '⬅ Mês Anterior',
                 'callback_data': f'cal_{hoje.year}_{(hoje.month-2)%12+1}_{hoje.year if hoje.month > 1 else hoje.year-1}'},
                {'text': '➡ Próximo Mês',
                 'callback_data': f'cal_{hoje.year}_{hoje.month%12+1}_{hoje.year if hoje.month < 12 else hoje.year+1}'},
            ],
            [{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}],
        ]}
        edit_message(chat_id, msg_id, texto, reply_markup=kb)
        return

    # Navegação do calendário: cal_ANO_MES_ANO_REAL
    if data.startswith('cal_'):
        parts = data.split('_')  # cal_ANO_MES_ANO_NAV
        try:
            # formato: cal_ano_origem_mes_nav_ano_nav
            ano_nav = int(parts[3])
            mes_nav = int(parts[2])
            # garante limites válidos
            if not (1 <= mes_nav <= 12):
                mes_nav = date.today().month
                ano_nav = date.today().year
        except (IndexError, ValueError):
            mes_nav = date.today().month
            ano_nav = date.today().year
        texto = format_calendario(ano_nav, mes_nav)
        mes_ant = mes_nav - 1 if mes_nav > 1 else 12
        ano_ant = ano_nav if mes_nav > 1 else ano_nav - 1
        mes_prox = mes_nav + 1 if mes_nav < 12 else 1
        ano_prox = ano_nav if mes_nav < 12 else ano_nav + 1
        kb = {'inline_keyboard': [
            [
                {'text': '⬅ Mês Anterior', 'callback_data': f'cal_{ano_nav}_{mes_ant}_{ano_ant}'},
                {'text': '➡ Próximo Mês',  'callback_data': f'cal_{ano_nav}_{mes_prox}_{ano_prox}'},
            ],
            [{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}],
        ]}
        edit_message(chat_id, msg_id, texto, reply_markup=kb)
        return

    if data == 'cmd_ver_tarefas':
        tasks = db_listar_tarefas()
        # Todas as tarefas → agrupa por status para melhor leitura
        edit_message(chat_id, msg_id,
                     format_task_list(tasks, '📋 Todas as Tarefas', grouped=True),
                     reply_markup={'inline_keyboard': [[
                         {'text': '🔙 Menu', 'callback_data': 'cmd_menu'}
                     ]]})
        return

    if data == 'cmd_ver_progresso':
        tasks = db_listar_tarefas('in-progress')
        edit_message(chat_id, msg_id,
                     format_task_list(tasks, '⚡ Em Progresso'),
                     reply_markup={'inline_keyboard': [[
                         {'text': '🔙 Menu', 'callback_data': 'cmd_menu'}
                     ]]})
        return

    if data == 'cmd_ver_concluidas':
        tasks = db_listar_tarefas('done')
        edit_message(chat_id, msg_id,
                     format_task_list(tasks, '✅ Concluídas'),
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
