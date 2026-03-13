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
import io
import json
from datetime import date, timedelta, datetime
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

STEP_AQ_SOLICITANTE = 'aq_aguardando_solicitante'
STEP_AQ_EMPRESA     = 'aq_aguardando_empresa'
STEP_AQ_ITENS       = 'aq_aguardando_itens'
STEP_AQ_OBS         = 'aq_aguardando_obs'

STEP_DI_DATA_PARTIDA = 'di_aguardando_data_partida'
STEP_DI_HORA_PARTIDA = 'di_aguardando_hora_partida'
STEP_DI_DATA_RETORNO = 'di_aguardando_data_retorno'
STEP_DI_HORA_RETORNO = 'di_aguardando_hora_retorno'

STEP_CNPJ_NUM        = 'cnpj_aguardando_num'

STEP_PZ_DATA         = 'pz_aguardando_data'
STEP_PZ_DIAS         = 'pz_aguardando_dias'

STEP_UP_PDF          = 'up_pdf_arquivo'
STEP_UP_RENOMEAR     = 'up_renomear_arquivo'

STEP_UP_EMPENHO      = 'up_empenho'
STEP_RPA_NOME        = 'rpa_nome'
STEP_RPA_VALOR       = 'rpa_valor'

STEP_PROT_BUSCA      = 'prot_busca'
STEP_DESP_BUSCA      = 'desp_busca'

STEP_UP_AUDITOR      = 'up_auditor_arquivo'
STEP_UP_EXTRATO      = 'up_extrato_arquivo'

STEP_UP_RESUMIR      = 'up_resumir_arquivo'
STEP_MINUTA_ASSUNTO  = 'minuta_assunto'
STEP_MINUTA_DEST     = 'minuta_destinatario'
STEP_MINUTA_TIPO     = 'minuta_tipo'

# ════════════════════════════════════════════════════════════════════════════
# Helpers Globais
# ════════════════════════════════════════════════════════════════════════════
CONFIG_FILE = Path(__file__).resolve().parent / 'config.json'

def get_config(key: str, default=''):
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                c = json.load(f)
                return c.get(key, default)
    except Exception:
        pass
    return default

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


def db_buscar_tarefas(termo: str) -> list[dict]:
    """Busca tarefas por título ou descrição (case-insensitive)."""
    conn = _db_connect()
    try:
        like = f'%{termo}%'
        rows = conn.execute(
            "SELECT id, title, description, status, priority, criado_em "
            "FROM kanban_tasks WHERE title LIKE ? OR description LIKE ? "
            "ORDER BY criado_em DESC LIMIT 20",
            (like, like)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def db_atualizar_status_tarefa(task_id: str, novo_status: str) -> dict | None:
    """Atualiza o status de uma tarefa. Retorna a tarefa atualizada ou None."""
    conn = _db_connect()
    try:
        conn.execute(
            "UPDATE kanban_tasks SET status=?, atualizado_em=datetime('now','localtime') WHERE id=?",
            (novo_status, task_id)
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, title, status, priority FROM kanban_tasks WHERE id=?",
            (task_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def db_logs_recentes(limite: int = 10) -> list[dict]:
    """Retorna os últimos logs de ações do sistema."""
    conn = _db_connect()
    try:
        rows = conn.execute(
            "SELECT acao, credor_nome, detalhes, data FROM logs ORDER BY data DESC LIMIT ?",
            (limite,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def db_contar_credores() -> dict:
    """Retorna contagens de credores ativos e inativos."""
    conn = _db_connect()
    try:
        ativos   = conn.execute("SELECT COUNT(*) FROM credores WHERE ativo=1").fetchone()[0]
        inativos = conn.execute("SELECT COUNT(*) FROM credores WHERE ativo=0").fetchone()[0]
        return {'ativos': ativos, 'inativos': inativos, 'total': ativos + inativos}
    finally:
        conn.close()


def db_buscar_protocolos(termo: str) -> list[dict]:
    """Busca protocolos por número, assunto ou origem/destino."""
    conn = _db_connect()
    try:
        like = f'%{termo.lower()}%'
        rows = conn.execute(
            "SELECT id, numero, tipo, direcao, origem_destino, assunto, data_protocolo, status "
            "FROM protocolos WHERE LOWER(numero) LIKE ? OR LOWER(assunto) LIKE ? OR LOWER(origem_destino) LIKE ? "
            "ORDER BY id DESC LIMIT 20",
            (like, like, like)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def db_buscar_despesas(termo: str) -> list[dict]:
    """Busca despesas (linhas processadas) por credor ou detalhe na string JSON."""
    conn = _db_connect()
    try:
        like = f'%{termo.lower()}%'
        rows = conn.execute(
            "SELECT id, importacao_id, dados "
            "FROM despesas_linhas WHERE LOWER(dados) LIKE ? "
            "ORDER BY id DESC LIMIT 20",
            (like,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════════
# Analisador Financeiro
# ════════════════════════════════════════════════════════════════════════════

def db_analise_financeira(ano: int, mes: int) -> dict:
    """
    Retorna um resumo financeiro completo do mês:
      - total_credores: quantos credores ativos existem
      - total_previsto: soma dos valores de todos os credores ativos (fixos)
      - total_empenhado: soma dos valores dos credores já empenhados no mês
      - total_pendente: soma dos não empenhados ainda
      - pct_empenhado: percentual empenhado
      - empenhados: list de dicts {nome, valor}
      - pendentes:  list de dicts {nome, valor}
      - top5_valores: 5 credores de maior valor (empenhados ou não)
      - rpas_mes: total de RPAs emitidos no mês e soma dos valores brutos
      - mes_anterior: dict com mesmo resumo do mês anterior (para comparativo)
    """
    conn = _db_connect()
    try:
        # ── Credores ativos com valor ──────────────────────────────────────
        credores = conn.execute(
            "SELECT id, nome, valor, tipo_valor FROM credores WHERE ativo=1 ORDER BY valor DESC"
        ).fetchall()
        credores = [dict(c) for c in credores]

        # ── Empenhos do mês ───────────────────────────────────────────────
        emp_rows = conn.execute(
            "SELECT credor_id FROM empenhos WHERE ano=? AND mes=? AND empenhado=1",
            (ano, mes)
        ).fetchall()
        empenhados_ids = {r['credor_id'] for r in emp_rows}

        # ── Separa e calcula totais ────────────────────────────────────────
        lista_emp:  list[dict] = []
        lista_pend: list[dict] = []
        total_previsto  = 0.0
        total_empenhado = 0.0

        for c in credores:
            v = float(c['valor'] or 0)
            total_previsto += v
            if c['id'] in empenhados_ids:
                total_empenhado += v
                lista_emp.append({'nome': c['nome'], 'valor': v})
            else:
                lista_pend.append({'nome': c['nome'], 'valor': v})

        total_pendente = total_previsto - total_empenhado
        pct = (total_empenhado / total_previsto * 100) if total_previsto > 0 else 0.0

        # ── Top 5 maiores credores ────────────────────────────────────────
        top5 = sorted(credores, key=lambda x: float(x['valor'] or 0), reverse=True)[:5]

        # ── RPAs do mês ───────────────────────────────────────────────────
        # periodo_referencia no formato MM/YYYY ou YYYY-MM
        mes_str_a = f'{mes:02d}/{ano}'
        mes_str_b = f'{ano}-{mes:02d}'
        rpas = conn.execute(
            "SELECT COUNT(*) AS qtd, COALESCE(SUM(valor_bruto), 0) AS total_bruto "
            "FROM rpas WHERE periodo_referencia LIKE ? OR periodo_referencia LIKE ?",
            (f'%{mes_str_a}%', f'%{mes_str_b}%')
        ).fetchone()
        rpas_qtd   = rpas['qtd'] if rpas else 0
        rpas_total = float(rpas['total_bruto'] if rpas else 0)

        # ── Mês anterior (comparativo) ────────────────────────────────────
        mes_ant = mes - 1 if mes > 1 else 12
        ano_ant = ano if mes > 1 else ano - 1
        emp_ant = conn.execute(
            "SELECT COUNT(*) AS qtd FROM empenhos WHERE ano=? AND mes=? AND empenhado=1",
            (ano_ant, mes_ant)
        ).fetchone()
        qtd_ant = emp_ant['qtd'] if emp_ant else 0
        # valor empenhado no mês anterior
        ids_ant = {r['credor_id'] for r in conn.execute(
            "SELECT credor_id FROM empenhos WHERE ano=? AND mes=? AND empenhado=1",
            (ano_ant, mes_ant)
        ).fetchall()}
        val_ant = sum(float(c['valor'] or 0) for c in credores if c['id'] in ids_ant)

        return {
            'ano': ano, 'mes': mes,
            'total_credores': len(credores),
            'total_previsto': total_previsto,
            'total_empenhado': total_empenhado,
            'total_pendente': total_pendente,
            'pct_empenhado': pct,
            'qtd_empenhados': len(lista_emp),
            'qtd_pendentes': len(lista_pend),
            'empenhados': sorted(lista_emp, key=lambda x: x['valor'], reverse=True),
            'pendentes':  sorted(lista_pend,  key=lambda x: x['valor'], reverse=True),
            'top5_valores': [{'nome': c['nome'], 'valor': float(c['valor'] or 0)} for c in top5],
            'rpas_qtd': rpas_qtd,
            'rpas_total': rpas_total,
            'mes_anterior': {
                'mes': mes_ant, 'ano': ano_ant,
                'qtd_empenhados': qtd_ant,
                'total_empenhado': val_ant,
            },
        }
    finally:
        conn.close()


def _moeda(valor: float) -> str:
    """Formata valor em reais BR."""
    return f'R$ {valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def _barra_progresso(pct: float, largura: int = 10) -> str:
    """Gera uma barra visual de progresso com blocos."""
    filled = round(pct / 100 * largura)
    filled = max(0, min(largura, filled))
    return '█' * filled + '░' * (largura - filled)


MESES_PT_ABREV = ['', 'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                   'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
MESES_PT_FULL  = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                   'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']


def format_analise_financeira(d: dict) -> str:
    """Formata o relatório financeiro para envio no Telegram."""
    mes_nome = MESES_PT_FULL[d['mes']]
    pct      = d['pct_empenhado']
    barra    = _barra_progresso(pct)

    # Tendência em relação ao mês anterior
    diff_val = d['total_empenhado'] - d['mes_anterior']['total_empenhado']
    if diff_val > 0:
        tendencia = f'📈 +{_moeda(diff_val)} vs {MESES_PT_ABREV[d["mes_anterior"]["mes"]]}'
    elif diff_val < 0:
        tendencia = f'📉 {_moeda(diff_val)} vs {MESES_PT_ABREV[d["mes_anterior"]["mes"]]}'
    else:
        tendencia = f'➡️ Igual ao mês anterior'

    # Cabeçalho + resumo geral
    lines = [
        f'💰 <b>Analisador Financeiro</b>',
        f'<b>{mes_nome} {d["ano"]}</b>\n',

        f'<b>📊 Visão Geral</b>',
        f'Previsto total:   <b>{_moeda(d["total_previsto"])}</b>',
        f'Empenhado:        <b>{_moeda(d["total_empenhado"])}</b>',
        f'Pendente:         <b>{_moeda(d["total_pendente"])}</b>',
        f'',
        f'Progresso: <code>{barra}</code> <b>{pct:.1f}%</b>',
        f'Credores: {d["qtd_empenhados"]}✅ empenhados / {d["qtd_pendentes"]}⏳ pendentes de {d["total_credores"]}',
        f'{tendencia}',
    ]

    # RPAs
    if d['rpas_qtd'] > 0:
        lines += [
            f'',
            f'<b>📄 RPAs do Mês</b>',
            f'{d["rpas_qtd"]} RPA(s) — total bruto: <b>{_moeda(d["rpas_total"])}</b>',
        ]

    # Top 5 maiores credores
    lines += ['', f'<b>🏆 Top 5 Maiores Credores</b>']
    for i, c in enumerate(d['top5_valores'], 1):
        nome = c['nome'][:28] + ('…' if len(c['nome']) > 28 else '')
        lines.append(f'{i}. {nome}  — <b>{_moeda(c["valor"])}</b>')

    # Pendentes (até 8)
    if d['pendentes']:
        lines += ['', f'<b>⏳ Ainda Pendentes ({d["qtd_pendentes"]})</b>']
        for c in d['pendentes'][:8]:
            nome = c['nome'][:30] + ('…' if len(c['nome']) > 30 else '')
            lines.append(f'• {nome}  {_moeda(c["valor"])}')
        if d['qtd_pendentes'] > 8:
            lines.append(f'<i>… e mais {d["qtd_pendentes"] - 8} credores</i>')

    return '\n'.join(lines)


def keyboard_financeiro(ano: int, mes: int) -> dict:
    mes_ant = mes - 1 if mes > 1 else 12
    ano_ant = ano if mes > 1 else ano - 1
    mes_prox = mes + 1 if mes < 12 else 1
    ano_prox = ano if mes < 12 else ano + 1
    return {
        'inline_keyboard': [
            [
                {'text': '⬅ Mês Anterior', 'callback_data': f'fin_{ano_ant}_{mes_ant}'},
                {'text': '➡ Próximo Mês',  'callback_data': f'fin_{ano_prox}_{mes_prox}'},
            ],
            [
                {'text': '📋 Empenhados',  'callback_data': f'fin_emp_{ano}_{mes}'},
                {'text': '⏳ Pendentes',   'callback_data': f'fin_pend_{ano}_{mes}'},
            ],
            [{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}],
        ]
    }


def format_lista_credores_fin(d: dict, modo: str) -> str:
    """Formata lista detalhada de empenhados ou pendentes."""
    mes_nome = MESES_PT_ABREV[d['mes']]
    if modo == 'emp':
        lista  = d['empenhados']
        titulo = f'✅ Empenhados — {mes_nome}/{d["ano"]}  ({d["qtd_empenhados"]})'
    else:
        lista  = d['pendentes']
        titulo = f'⏳ Pendentes — {mes_nome}/{d["ano"]}  ({d["qtd_pendentes"]})'

    if not lista:
        return f'<b>{titulo}</b>\n\n<i>Nenhum.</i>'

    lines = [f'<b>{titulo}</b>\n']
    total = 0.0
    for c in lista[:30]:
        nome  = c['nome'][:32] + ('…' if len(c['nome']) > 32 else '')
        val   = c['valor']
        total += val
        lines.append(f'• {nome}  <b>{_moeda(val)}</b>')
    lines.append(f'\n<b>Total: {_moeda(total)}</b>')
    if len(lista) > 30:
        lines.append(f'<i>… e mais {len(lista) - 30}</i>')
    return '\n'.join(lines)


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


def send_document(chat_id: int, document, caption: str = '', filename: str = 'document.pdf'):
    url = f'{TELEGRAM_API}/sendDocument'
    try:
        if isinstance(document, bytes):
            files = {'document': (filename, document)}
            data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
            requests.post(url, data=data, files=files, timeout=40)
        else:
            requests.post(url, json={'chat_id': chat_id, 'document': document, 'caption': caption, 'parse_mode': 'HTML'}, timeout=10)
    except Exception as e:
        log.error('Erro ao enviar documento: %s', e)


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
            [{'text': '— 📋 GESTÃO KANBAN —', 'callback_data': 'ignore'}],
            [
                {'text': '➕ Nova Tarefa', 'callback_data': 'cmd_nova_tarefa'},
                {'text': '🔍 Ver Tarefas', 'callback_data': 'cmd_ver_tarefas'},
            ],
            [{'text': '— 💰 FINANCEIRO & DESPESAS —', 'callback_data': 'ignore'}],
            [
                {'text': '📊 Painel Mensal', 'callback_data': 'cmd_financeiro'},
                {'text': '🔎 Consultar', 'callback_data': 'cmd_buscar_despesas'},
            ],
            [
                {'text': '📅 Calendário de Pagamentos', 'callback_data': 'cmd_calendario'},
            ],
            [{'text': '— 📝 PROTOCOLOS E PROCESSOS —', 'callback_data': 'ignore'}],
            [
                {'text': '🔎 Buscar Protocolo/Ofício', 'callback_data': 'cmd_buscar_protocolos'},
            ],
            [
                {'text': '📄 Gerar Empenho', 'callback_data': 'cmd_gerar_empenho'},
                {'text': '💼 Gerar RPA', 'callback_data': 'cmd_gerar_rpa'},
            ],
            [{'text': '— 🛒 SERVIÇOS & CONSULTAS —', 'callback_data': 'ignore'}],
            [
                {'text': '🛒 Nova Aquisição', 'callback_data': 'cmd_nova_aquisicao'},
                {'text': '✈️ Calc. Diárias', 'callback_data': 'cmd_calc_diarias'},
            ],
            [
                {'text': '🏢 Consultar CNPJ', 'callback_data': 'cmd_consulta_cnpj'},
                {'text': '⏰ Calc. Prazos', 'callback_data': 'cmd_calc_prazos'},
            ],
            [{'text': '— 🛠️ FERRAMENTAS IA —', 'callback_data': 'ignore'}],
            [
                {'text': '📄 Extrair PDF', 'callback_data': 'cmd_extrator_pdf'},
                {'text': '✨ Renomear Arq.', 'callback_data': 'cmd_renomear_arquivo'},
            ],
            [
                {'text': '🔍 Auditor NF', 'callback_data': 'cmd_auditor_nf'},
                {'text': '🏦 Extrato Bancário', 'callback_data': 'cmd_extrato_bancario'},
            ],
            [
                {'text': '📝 Resumir Doc.', 'callback_data': 'cmd_resumir'},
                {'text': '✍️ Minuta', 'callback_data': 'cmd_minuta'},
            ],
            [
                {'text': '📊 Relatório Mensal', 'callback_data': 'cmd_relatorio'},
                {'text': '🗒 Log Atividades', 'callback_data': 'cmd_log'},
            ],
            [{'text': '🔄 Atualizar Menu', 'callback_data': 'cmd_menu'}],
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
# Fluxos de Geradores e Formulários (Empenho e RPA)
# ════════════════════════════════════════════════════════════════════════════

EMP_PROMPT = '''Analise o seguinte texto extraído de um documento (fatura, contrato, ordem de serviço, ou requisição).
O seu objetivo é gerar o texto da "Descrição" para uma Nota de Empenho (NE) do setor público.

Regras Estritas:
1. A saída deve estar EXCLUSIVAMENTE em CAIXA ALTA (letras maiúsculas).
2. O texto deve começar OBRIGATORIAMENTE com a frase exata: "PELA DESPESA EMPENHADA REFERENTE A".
3. Identifique o objeto da despesa de forma sucinta mas completa.
4. Se houver número de processo, pregão, contrato ou nota fiscal visível, inclua-os no texto.
5. Não use markdown, apenas texto puro.

Texto do documento:
---
{TEXT}
---'''

def start_empenho_flow(chat_id: int, edit_msg: tuple | None = None):
    set_state(chat_id, {'step': STEP_UP_EMPENHO})
    text = (
        '📝 <b>Gerador de Nota de Empenho</b>\n\n'
        'Envie um arquivo PDF (ex: Fatura, Contrato) ou simplesmente <b>digite o texto</b> do documento aqui.\n'
        'A IA gerará a descrição formal do empenho para você.\n\n'
        '<i>Envie /cancelar para sair.</i>'
    )
    if edit_msg:
        edit_message(edit_msg[0], edit_msg[1], text, reply_markup={'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]})
    else:
        send_message(chat_id, text, reply_markup={'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]})

def process_empenho_text(chat_id: int, text: str):
    msg_id = send_message(chat_id, '⏳ Analisando texto com IA...')["result"]["message_id"]
    try:
        api_key = get_config('api_openrouter_key')
        if not api_key:
            edit_message(chat_id, msg_id, '⚠️ Chave OpenRouter não configurada. Configure no painel web ADM primeiro.')
            return

        prompt = EMP_PROMPT.replace('{TEXT}', text)
        url = 'https://openrouter.ai/api/v1/chat/completions'
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': get_config('api_openrouter_modelo') or 'meta-llama/llama-3.3-70b-instruct:free',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.2
        }
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        if r.status_code != 200:
            edit_message(chat_id, msg_id, f'⚠️ Erro na IA: {r.status_code}\n{r.text}')
            return
            
        ans = dict(r.json() or {})
        content = (ans.get('choices', [{}])[0].get('message', {}).get('content') or '').strip()
        
        if content:
            content = content.upper().replace('**', '').replace('*', '')
            if not content.startswith('PELA DESPESA EMPENHADA'):
                if content.startswith('REFERENTE'):
                    content = f'PELA DESPESA EMPENHADA {content}'
                else:
                    content = f'PELA DESPESA EMPENHADA REFERENTE A {content}'
            edit_message(chat_id, msg_id, f'✅ <b>Descrição de Empenho Gerada:</b>\n\n<code>{content}</code>\n\n<i>Toque no texto para copiar.</i>')
        else:
            edit_message(chat_id, msg_id, '⚠️ Resposta vazia da IA.')
    except Exception as e:
        log.error('Erro no /empenho: %s', e)
        edit_message(chat_id, msg_id, '⚠️ Ocorreu um erro ao processar o empenho usando a IA.')
    finally:
        clear_state(chat_id)

def process_empenho_pdf(chat_id: int, file_id: str):
    msg_id = send_message(chat_id, '⏳ Baixando e extraindo PDF...')["result"]["message_id"]
    try:
        f_info = tg_request('getFile', {'file_id': file_id})
        if not f_info.get('ok'):
            edit_message(chat_id, msg_id, '⚠️ Erro ao obter as informações do arquivo do Telegram.')
            clear_state(chat_id)
            return
            
        file_path = f_info['result']['file_path']
        download_url = f'https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}'
        r = requests.get(download_url, timeout=30)
        
        if r.status_code != 200:
            edit_message(chat_id, msg_id, '⚠️ Erro ao baixar o arquivo.')
            clear_state(chat_id)
            return

        pdf_bytes = io.BytesIO(r.content)
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(pdf_bytes)
            text = ''
            for page in reader.pages:
                text += (page.extract_text() or '') + '\n'
            text = text.strip()
        except Exception as e:
            edit_message(chat_id, msg_id, f'⚠️ Erro ao ler PDF: {e}')
            clear_state(chat_id)
            return
            
        if not text:
            edit_message(chat_id, msg_id, '⚠️ Nenhum texto pôde ser extraído deste PDF (documento escaneado?). Tente enviar o texto diretamente.')
            clear_state(chat_id)
            return
            
        process_empenho_text(chat_id, text)
        
    except Exception as e:
        log.error(e)
        edit_message(chat_id, msg_id, '⚠️ Erro não tratado ao processar PDF.')
        clear_state(chat_id)

def start_rpa_flow(chat_id: int, edit_msg: tuple | None = None):
    set_state(chat_id, {'step': STEP_RPA_NOME})
    text = (
        '💼 <b>Calculadora de RPA</b>\n\n'
        'Para gerar os cálculos do Recibo de Pagamento a Autônomo, primeiro digite o <b>Nome do Prestador</b>:\n\n'
        '<i>(Envie /cancelar para sair)</i>'
    )
    if edit_msg:
        edit_message(edit_msg[0], edit_msg[1], text, reply_markup={'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]})
    else:
        send_message(chat_id, text, reply_markup={'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]})

def handle_rpa_nome(chat_id: int, text: str):
    set_state(chat_id, {'step': STEP_RPA_VALOR, 'rpa_nome': text.strip()})
    send_message(chat_id,
        f'👤 <b>Prestador:</b> {text.strip()}\n\n'
        'Agora digite o <b>Valor Bruto (R$)</b> do serviço (apenas números e vírgula/ponto, ex: 1500,00):'
    )

def handle_rpa_valor(chat_id: int, text: str):
    state = get_state(chat_id)
    nome = state.get('rpa_nome', 'Prestador')
    try:
        val = text.strip().replace('R$', '').replace('.', '').replace(',', '.')
        bruto = float(val)
    except Exception:
        send_message(chat_id, '⚠️ Valor inválido. Digite um número (Ex: 1500,00).')
        return

    # Basic RPA parameters mirroring the frontend defaults
    aliq_inss = 11.0 
    teto_inss = 877.24
    aliq_iss = 5.0
    
    inss = min(bruto * (aliq_inss / 100), teto_inss)
    iss = bruto * (aliq_iss / 100)
    
    base_irrf = max(0, bruto - inss)
    
    faixas = [
      {'limInf': 0,       'limSup': 2428.80, 'aliq': 0,    'parcela': 0      },
      {'limInf': 2428.81, 'limSup': 2800.00, 'aliq': 7.5,  'parcela': 182.16 },
      {'limInf': 2800.01, 'limSup': 3566.00, 'aliq': 15,   'parcela': 394.16 },
      {'limInf': 3566.01, 'limSup': 4743.33, 'aliq': 22.5, 'parcela': 661.62 },
      {'limInf': 4743.34, 'limSup': 9999999, 'aliq': 27.5, 'parcela': 1065.14 }
    ]
    
    aliq_ir = 0
    parcela_ir = 0
    for f in faixas:
        if f['limSup'] is None or base_irrf <= f['limSup']:
            if base_irrf >= f['limInf']:
                aliq_ir = f['aliq']
                parcela_ir = f['parcela']
                break
                
    ir = max(0, (base_irrf * aliq_ir / 100) - parcela_ir)
    liquido = bruto - inss - ir - iss
    
    def fmt(v): return f"R$ {v:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        
    resumo = (
        f'💼 <b>Resumo do RPA</b>\n\n'
        f'👤 <b>Prestador:</b> {nome}\n\n'
        f'💰 <b>Valor Bruto:</b> {fmt(bruto)}\n'
        f'📉 <b>(-) INSS ({aliq_inss}%):</b> {fmt(inss)}\n'
    )
    if ir > 0:
        resumo += f'📉 <b>(-) IRRF ({aliq_ir}%):</b> {fmt(ir)}\n'
    resumo += (
        f'📉 <b>(-) ISS ({aliq_iss}%):</b> {fmt(iss)}\n'
        f'➖ <b>Total de Descontos:</b> {fmt(inss + ir + iss)}\n\n'
        f'💵 <b>Valor Líquido:</b> <b>{fmt(liquido)}</b>\n\n'
        f'<i>Para gerar e imprimir o PDF formal deste RPA, acesse o painel pelo navegador.</i>'
    )
    
    markup = {
        'inline_keyboard': [[{'text': '📄 Gerar PDF (Navegador)', 'url': f'{SERVER_URL}/rpa'}]]
    }
    
    send_message(chat_id, resumo, reply_markup=markup)
    clear_state(chat_id)


# ════════════════════════════════════════════════════════════════════════════
# Fluxo de Busca de Protocolos e Despesas
# ════════════════════════════════════════════════════════════════════════════

def start_protocolos_flow(chat_id: int, edit_msg: tuple | None = None):
    set_state(chat_id, {'step': STEP_PROT_BUSCA})
    text = (
        '🔎 <b>Buscar Protocolos</b>\n\n'
        'Digite um trecho do <b>Número</b>, <b>Assunto</b> ou <b>Origem/Destino</b> para pesquisar:\n\n'
        '<i>(Envie /cancelar para sair)</i>'
    )
    if edit_msg:
        edit_message(edit_msg[0], edit_msg[1], text, reply_markup={'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]})
    else:
        send_message(chat_id, text, reply_markup={'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]})

def handle_protocolos_busca(chat_id: int, text: str):
    if len(text.strip()) < 3:
        send_message(chat_id, '⚠️ Digite pelo menos 3 caracteres para buscar.')
        return
        
    msg_id = send_message(chat_id, '⏳ Buscando protocolos...')["result"]["message_id"]
    try:
        resultados = db_buscar_protocolos(text.strip())
        if not resultados:
            edit_message(chat_id, msg_id, f'🔍 Nenhum protocolo encontrado para <b>"{text.strip()}"</b>.')
            clear_state(chat_id)
            return
            
        lines = [f'🔎 <b>Resultados para: "{text.strip()}"</b>\n']
        for p in resultados:
            num = p.get('numero', 'SN')
            assunto = (p.get('assunto') or '')[:40]
            status = p.get('status', '')
            lines.append(f'📄 <b>{num}</b> <code>[{status.upper()}]</code>\n   └ <i>{assunto}</i>')
            
        lines.append('\n<i>Acesse o sistema web para ver os anexos e detalhes.</i>')
        texto_final = '\n'.join(lines)
        if len(texto_final) > 4000:
            texto_final = texto_final[:4000] + '...\n(Muitos resultados, refine a busca)'
            
        edit_message(chat_id, msg_id, texto_final)
    except Exception as e:
        log.error('Erro na busca de protocolos: %s', e)
        edit_message(chat_id, msg_id, '⚠️ Erro ao realizar a busca.')
    finally:
        clear_state(chat_id)

def start_despesas_flow(chat_id: int, edit_msg: tuple | None = None):
    set_state(chat_id, {'step': STEP_DESP_BUSCA})
    text = (
        '🔎 <b>Consultar Pagamentos de Despesas</b>\n\n'
        'Digite o <b>Nome do Credor</b>, <b>Número do Empenho</b>, ou um termo para buscar nas despesas da prefeitura:\n\n'
        '<i>(Envie /cancelar para sair)</i>'
    )
    if edit_msg:
        edit_message(edit_msg[0], edit_msg[1], text, reply_markup={'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]})
    else:
        send_message(chat_id, text, reply_markup={'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]})

def handle_despesas_busca(chat_id: int, text: str):
    if len(text.strip()) < 3:
        send_message(chat_id, '⚠️ Digite pelo menos 3 caracteres para buscar.')
        return
        
    msg_id = send_message(chat_id, '⏳ Buscando despesas...')["result"]["message_id"]
    try:
        resultados = db_buscar_despesas(text.strip())
        if not resultados:
            edit_message(chat_id, msg_id, f'🔍 Nenhuma despesa encontrada para <b>"{text.strip()}"</b>.')
            clear_state(chat_id)
            return
            
        lines = [f'🔎 <b>Despesas com: "{text.strip()}"</b>\n']
        for r in resultados:
            try:
                import json
                dados = json.loads(r['dados'])
                credor = str(dados.get('credor') or dados.get('Favorecido') or dados.get('favorecido', ''))[:30]
                historico = str(dados.get('histórico') or dados.get('historico') or dados.get('Histórico', ''))[:40]
                valor = dados.get('valor_pago') or dados.get('Valor Pago') or dados.get('ValorPago') or '0,00'
                lines.append(f'💰 <b>{credor}</b> - R$ {valor}\n   └ <i>{historico}</i>')
            except Exception:
                lines.append(f'🔹 {r["dados"][:60]}...')
                
        lines.append('\n<i>Acesse o sistema web (Aba Transparência) para mais detalhes.</i>')
        texto_final = '\n'.join(lines)
        if len(texto_final) > 4000:
            texto_final = texto_final[:4000] + '...\n(Muitos resultados, refine a busca)'
            
        edit_message(chat_id, msg_id, texto_final)
    except Exception as e:
        log.error('Erro na busca de despesas: %s', e)
        edit_message(chat_id, msg_id, '⚠️ Erro ao realizar a busca de despesas.')
    finally:
        clear_state(chat_id)


# ════════════════════════════════════════════════════════════════════════════
# Group 5 – Auditor IA de Notas Fiscais
# ════════════════════════════════════════════════════════════════════════════

def start_auditor_flow(chat_id: int, edit_msg: tuple | None = None):
    """Inicia o fluxo de auditoria de nota fiscal."""
    set_state(chat_id, {'step': STEP_UP_AUDITOR})
    text = (
        '🔍 <b>Auditor de Notas Fiscais · IA</b>\n\n'
        'Envie uma <b>Nota Fiscal</b> (PDF, JPG ou PNG) e a IA irá:\n'
        '• Extrair dados do fornecedor, CNPJ e valores\n'
        '• Verificar inconsistências matemáticas\n'
        '• Detectar descrições genéricas e datas suspeitas\n'
        '• Gerar um <b>Escore de Risco (0–100)</b>\n\n'
        '📎 <i>Envie o arquivo agora:</i>'
    )
    kb = {'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]}
    if edit_msg:
        edit_message(edit_msg[0], edit_msg[1], text, reply_markup=kb)
    else:
        send_message(chat_id, text, reply_markup=kb)


def process_auditor_file(chat_id: int, file_id: str, file_name: str):
    """Baixa o arquivo, extrai texto e chama a IA para auditoria."""
    msg_id = send_message(chat_id, '⏳ <i>Baixando arquivo e analisando com IA…</i>')["result"]["message_id"]
    try:
        # 1. Download do Telegram
        f_info = tg_request('getFile', {'file_id': file_id})
        if not f_info.get('ok'):
            edit_message(chat_id, msg_id, '⚠️ Erro ao obter informações do arquivo.')
            return
        file_path = f_info['result']['file_path']
        download_url = f'https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}'
        r = requests.get(download_url, timeout=30)
        if r.status_code != 200:
            edit_message(chat_id, msg_id, '⚠️ Erro ao baixar o arquivo.')
            return

        # 2. Extração de texto
        is_pdf = file_name.lower().endswith('.pdf')
        if is_pdf:
            try:
                import PyPDF2
                pdf_bytes = io.BytesIO(r.content)
                reader = PyPDF2.PdfReader(pdf_bytes)
                text = ''.join((page.extract_text() or '') + '\n' for page in reader.pages).strip()
            except Exception as e:
                edit_message(chat_id, msg_id, f'⚠️ Erro ao ler PDF: {e}')
                return
            if not text:
                edit_message(chat_id, msg_id, '⚠️ Não foi possível extrair texto do PDF (imagem escaneada?). Tente enviar como JPG/PNG.')
                return
        else:
            # Para imagens, enviar como base64 via prompt
            import base64
            img_b64 = base64.b64encode(r.content).decode()
            ext = file_name.rsplit('.', 1)[-1].upper()
            text = f'[Imagem {ext} da nota fiscal – dados em base64 truncados para análise de texto]'

        # 3. Prompt de auditoria
        prompt = f"""Você é um Auditor Fiscal Sênior de Prefeitura Municipal Brasileira.
Analise a Nota Fiscal abaixo e responda APENAS com um objeto JSON válido (sem texto extra):
{{
  "supplierName": "string",
  "cnpj": "string",
  "invoiceDate": "string",
  "totalAmount": number,
  "items": [{{"description": "...", "quantity": number, "unitPrice": number, "totalPrice": number}}],
  "anomalies": ["string"],
  "riskScore": number0a100,
  "riskLevel": "BAIXO|MÉDIO|ALTO|CRÍTICO",
  "auditRecommendation": "string",
  "reasoning": "string em português"
}}

Regras:
- Verifique: Qtd × Preço Unit = Total Item; soma itens = Total NF.
- Descrições genéricas ("serviços diversos") são suspeitas → riskScore alto.
- NFs muito antigas ou emitidas em fins de semana para serviços de escritório são suspeitas.
- Use ponto decimal; riskScore 0-100.

Texto da Nota Fiscal:
---
{text[:8000]}
---"""

        # 4. Chamada à IA via server.py
        try:
            resp = requests.post(
                f'{SERVER_URL}/api/ia/chat',
                json={'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.1, 'max_tokens': 1500},
                timeout=60
            )
            data = resp.json()
            if not resp.ok:
                err = data.get('error') or data
                if isinstance(err, dict):
                    err = err.get('message', str(err))
                edit_message(chat_id, msg_id, f'⚠️ Erro da IA: {err}')
                return
            content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        except Exception as e:
            edit_message(chat_id, msg_id, f'⚠️ Erro ao contatar o servidor IA: {e}\n\n<i>Certifique-se de que o servidor local está rodando e que a chave OpenRouter está configurada na aba ADM do sistema web.</i>')
            return

        # 5. Parse do JSON retornado
        try:
            import re as _re
            json_match = _re.search(r'\{[\s\S]*\}', content)
            result = json.loads(json_match.group(0)) if json_match else json.loads(content)
        except Exception:
            # Resposta não-JSON – exibe como texto
            edit_message(chat_id, msg_id, f'🤖 <b>Análise da IA:</b>\n\n{content[:3800]}', reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})
            return

        # 6. Formatar resultado
        score = result.get('riskScore', 0)
        level = result.get('riskLevel', '?')
        score_emoji = '🟢' if score < 30 else ('🟡' if score < 60 else ('🟠' if score < 80 else '🔴'))
        anomalies = result.get('anomalies', [])
        anomaly_text = '\n'.join(f'  ⚠️ {a}' for a in anomalies) if anomalies else '  ✅ Nenhuma anomalia detectada'
        items = result.get('items', [])
        items_text = ''
        for item in items[:5]:
            items_text += f'  • {item.get("description","?")[:35]} — Qtd: {item.get("quantity",0)} × R$ {item.get("unitPrice",0):.2f}\n'
        if len(items) > 5:
            items_text += f'  <i>…e mais {len(items)-5} item(ns)</i>\n'

        msg = (
            f'{score_emoji} <b>Relatório de Auditoria</b>\n\n'
            f'🏢 <b>Fornecedor:</b> {result.get("supplierName","—")}\n'
            f'📋 <b>CNPJ:</b> <code>{result.get("cnpj","—")}</code>\n'
            f'📅 <b>Data NF:</b> {result.get("invoiceDate","—")}\n'
            f'💰 <b>Valor Total:</b> R$ {result.get("totalAmount",0):,.2f}\n\n'
            f'🎯 <b>Escore de Risco: {score}/100</b> — {level}\n\n'
            f'<b>📦 Itens:</b>\n{items_text}\n'
            f'<b>⚠️ Anomalias:</b>\n{anomaly_text}\n\n'
            f'<b>🤖 Recomendação:</b>\n<i>{result.get("auditRecommendation","—")}</i>'
        )
        if len(msg) > 4000:
            msg = msg[:4000] + '…'

        edit_message(chat_id, msg_id, msg, reply_markup={'inline_keyboard': [
            [{'text': '🔍 Auditar outro arquivo', 'callback_data': 'cmd_auditor_nf'}],
            [{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]
        ]})

    except Exception as e:
        log.error('Erro no auditor: %s', e)
        edit_message(chat_id, msg_id, '⚠️ Erro inesperado na auditoria.')
    finally:
        clear_state(chat_id)


# ════════════════════════════════════════════════════════════════════════════
# Group 5 – Analisador de Extratos Bancários
# ════════════════════════════════════════════════════════════════════════════

def start_extrato_flow(chat_id: int, edit_msg: tuple | None = None):
    """Inicia o fluxo de análise de extrato bancário."""
    set_state(chat_id, {'step': STEP_UP_EXTRATO})
    text = (
        '🏦 <b>Analisador de Extratos Bancários · IA</b>\n\n'
        'Envie um <b>extrato bancário em PDF</b> (BB, Caixa, Bradesco, etc.) e a IA irá:\n'
        '• Identificar e somar todas as <b>tarifas e encargos</b>\n'
        '• Listar créditos, débitos e saldo do período\n'
        '• Alertar sobre cobranças duplicadas ou suspeitas\n\n'
        '📎 <i>Envie o PDF do extrato agora:</i>'
    )
    kb = {'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]}
    if edit_msg:
        edit_message(edit_msg[0], edit_msg[1], text, reply_markup=kb)
    else:
        send_message(chat_id, text, reply_markup=kb)


def process_extrato_file(chat_id: int, file_id: str, file_name: str):
    """Baixa o PDF do extrato, extrai texto e chama a IA para análise financeira."""
    msg_id = send_message(chat_id, '⏳ <i>Lendo extrato e analisando tarifas com IA…</i>')["result"]["message_id"]
    try:
        # 1. Download
        f_info = tg_request('getFile', {'file_id': file_id})
        if not f_info.get('ok'):
            edit_message(chat_id, msg_id, '⚠️ Erro ao obter informações do arquivo.')
            return
        file_path = f_info['result']['file_path']
        download_url = f'https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}'
        r = requests.get(download_url, timeout=30)
        if r.status_code != 200:
            edit_message(chat_id, msg_id, '⚠️ Erro ao baixar o arquivo.')
            return

        # 2. Extração de texto do PDF
        if not file_name.lower().endswith('.pdf'):
            edit_message(chat_id, msg_id, '⚠️ Envie apenas arquivos PDF para análise de extratos.')
            return
        try:
            import PyPDF2
            pdf_bytes = io.BytesIO(r.content)
            reader = PyPDF2.PdfReader(pdf_bytes)
            text = ''.join((page.extract_text() or '') + '\n' for page in reader.pages).strip()
        except Exception as e:
            edit_message(chat_id, msg_id, f'⚠️ Erro ao ler PDF: {e}')
            return
        if not text:
            edit_message(chat_id, msg_id, '⚠️ Não foi possível extrair texto do PDF. O arquivo pode ser uma imagem escaneada.')
            return

        # 3. Prompt de análise
        prompt = f"""Você é um especialista em finanças públicas municipais do Brasil.
Analise o extrato bancário abaixo e responda APENAS com um objeto JSON válido:
{{
  "total_tarifas": number,
  "categorias_tarifas": [{{"nome": "string", "valor": number}}],
  "total_creditos": number,
  "total_debitos": number,
  "saldo_periodo": number,
  "num_lancamentos": number,
  "maiores_debitos": [{{"descricao": "string", "valor": number}}],
  "alertas": ["string"],
  "resumo": "string"
}}

Regras:
- "categorias_tarifas": cada tipo de tarifa (Manutenção, IOF, TED, Pacote, etc.).
- "maiores_debitos": top 5 maiores débitos excluindo tarifas.
- Use ponto decimal. Todos os valores como números.

Extrato:
---
{text[:12000]}
---"""

        # 4. Chamada à IA
        try:
            resp = requests.post(
                f'{SERVER_URL}/api/ia/chat',
                json={'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.1, 'max_tokens': 1500},
                timeout=60
            )
            data = resp.json()
            if not resp.ok:
                err = data.get('error') or data
                if isinstance(err, dict):
                    err = err.get('message', str(err))
                edit_message(chat_id, msg_id, f'⚠️ Erro da IA: {err}')
                return
            content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        except Exception as e:
            edit_message(chat_id, msg_id, f'⚠️ Erro ao contatar o servidor IA: {e}\n\n<i>Certifique-se de que o servidor local está rodando.</i>')
            return

        # 5. Parse JSON
        try:
            import re as _re
            json_match = _re.search(r'\{[\s\S]*\}', content)
            result = json.loads(json_match.group(0)) if json_match else json.loads(content)
        except Exception:
            edit_message(chat_id, msg_id, f'🤖 <b>Análise da IA:</b>\n\n{content[:3800]}', reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})
            return

        # 6. Formatar resultado
        def fmt_brl(v):
            try:
                return f'R$ {float(v):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
            except Exception:
                return 'R$ —'

        tarifas = result.get('categorias_tarifas', [])
        tarifas_text = ''.join(f'  💳 {t["nome"]}: {fmt_brl(t["valor"])}\n' for t in tarifas[:8])
        if not tarifas_text:
            tarifas_text = '  ✅ Nenhuma tarifa identificada\n'

        debitos = result.get('maiores_debitos', [])
        debitos_text = ''.join(f'  💸 {d["descricao"][:35]}: {fmt_brl(d["valor"])}\n' for d in debitos[:5])

        alertas = result.get('alertas', [])
        alertas_text = '\n'.join(f'  🔔 {a}' for a in alertas[:4]) if alertas else '  ✅ Sem alertas'

        saldo = result.get('saldo_periodo', 0)
        saldo_emoji = '📈' if float(saldo or 0) >= 0 else '📉'

        msg = (
            f'🏦 <b>Análise do Extrato Bancário</b>\n\n'
            f'⚠️ <b>Total de Tarifas/Encargos: {fmt_brl(result.get("total_tarifas",0))}</b>\n\n'
            f'📊 <b>Resumo Financeiro</b>\n'
            f'  📈 Créditos: {fmt_brl(result.get("total_creditos",0))}\n'
            f'  📉 Débitos: {fmt_brl(result.get("total_debitos",0))}\n'
            f'  {saldo_emoji} Saldo: {fmt_brl(saldo)}\n'
            f'  🔢 Lançamentos: {result.get("num_lancamentos","—")}\n\n'
            f'<b>💳 Detalhamento de Tarifas:</b>\n{tarifas_text}\n'
            f'<b>💸 Maiores Débitos:</b>\n{debitos_text}\n'
            f'<b>🔔 Alertas:</b>\n{alertas_text}\n\n'
            f'<b>🤖 Resumo da IA:</b>\n<i>{result.get("resumo","—")[:500]}</i>'
        )
        if len(msg) > 4000:
            msg = msg[:4000] + '…'

        edit_message(chat_id, msg_id, msg, reply_markup={'inline_keyboard': [
            [{'text': '🏦 Analisar outro extrato', 'callback_data': 'cmd_extrato_bancario'}],
            [{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]
        ]})

    except Exception as e:
        log.error('Erro no extrato: %s', e)
        edit_message(chat_id, msg_id, '⚠️ Erro inesperado na análise do extrato.')
    finally:
        clear_state(chat_id)



# ════════════════════════════════════════════════════════════════════════════
# Feature 1 – /resumir: Resumo IA de Documentos
# ════════════════════════════════════════════════════════════════════════════

def start_resumir_flow(chat_id: int, edit_msg: tuple | None = None):
    """Inicia o fluxo de resumo de documento."""
    set_state(chat_id, {'step': STEP_UP_RESUMIR})
    text = (
        '📝 <b>Resumidor de Documentos · IA</b>\n\n'
        'Envie um <b>PDF ou imagem</b> de um documento (ata, decreto, contrato, portaria…) '
        'e a IA irá gerar um <b>resumo executivo</b> com os pontos principais.\n\n'
        '📎 <i>Envie o arquivo agora:</i>'
    )
    kb = {'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]}
    if edit_msg:
        edit_message(edit_msg[0], edit_msg[1], text, reply_markup=kb)
    else:
        send_message(chat_id, text, reply_markup=kb)


def process_resumir_file(chat_id: int, file_id: str, file_name: str):
    """Baixa o arquivo, extrai texto e chama a IA para resumo."""
    msg_id = send_message(chat_id, '⏳ <i>Lendo documento e gerando resumo com IA…</i>')['result']['message_id']
    try:
        f_info = tg_request('getFile', {'file_id': file_id})
        if not f_info.get('ok'):
            edit_message(chat_id, msg_id, '⚠️ Erro ao obter informações do arquivo.')
            return
        file_path = f_info['result']['file_path']
        r = requests.get(f'https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}', timeout=30)
        if r.status_code != 200:
            edit_message(chat_id, msg_id, '⚠️ Erro ao baixar o arquivo.')
            return

        is_pdf = file_name.lower().endswith('.pdf')
        if is_pdf:
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(io.BytesIO(r.content))
                text = ''.join((p.extract_text() or '') + '\n' for p in reader.pages).strip()
            except Exception as e:
                edit_message(chat_id, msg_id, f'⚠️ Erro ao ler PDF: {e}')
                return
            if not text:
                edit_message(chat_id, msg_id, '⚠️ Não foi possível extrair texto do PDF (imagem escaneada?).')
                return
        else:
            import base64
            text = f'[Imagem do documento {file_name} enviada]'

        prompt = f"""Você é um assistente jurídico-administrativo da Prefeitura de Inajá – PE.
Analise o documento abaixo e gere um RESUMO EXECUTIVO estruturado em português formal.

Seções obrigatórias:
1. 📌 TIPO DE DOCUMENTO
2. 🎯 OBJETO / ASSUNTO PRINCIPAL
3. 👥 PARTES ENVOLVIDAS (se aplicável)
4. 💰 VALORES E PRAZOS (se aplicável)
5. ⚖️ OBRIGAÇÕES E CONDIÇÕES PRINCIPAIS
6. ⚠️ PONTOS DE ATENÇÃO

Seja conciso e objetivo. Máximo 400 palavras no total.

Documento:
---
{text[:10000]}
---"""

        try:
            resp = requests.post(f'{SERVER_URL}/api/ia/chat',
                json={'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.2, 'max_tokens': 1200},
                timeout=60)
            data = resp.json()
            if not resp.ok:
                err = data.get('error') or {}
                edit_message(chat_id, msg_id, f'⚠️ Erro da IA: {err.get("message", str(err))}')
                return
            resumo = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        except Exception as e:
            edit_message(chat_id, msg_id, f'⚠️ Erro ao contatar servidor IA: {e}')
            return

        header = f'📝 <b>Resumo: {file_name[:40]}</b>\n\n'
        full_msg = header + resumo
        if len(full_msg) > 4000:
            full_msg = full_msg[:4000] + '…'

        edit_message(chat_id, msg_id, full_msg, reply_markup={'inline_keyboard': [
            [{'text': '📝 Resumir outro documento', 'callback_data': 'cmd_resumir'}],
            [{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]
        ]})
    except Exception as e:
        log.error('Erro ao resumir: %s', e)
        edit_message(chat_id, msg_id, '⚠️ Erro inesperado ao gerar resumo.')
    finally:
        clear_state(chat_id)


# ════════════════════════════════════════════════════════════════════════════
# Feature 2 – /minuta: Gerador de Ofícios e Minutas com IA
# ════════════════════════════════════════════════════════════════════════════

def start_minuta_flow(chat_id: int, edit_msg: tuple | None = None):
    """Inicia o fluxo de geração de ofício/minuta."""
    set_state(chat_id, {'step': STEP_MINUTA_TIPO})
    text = (
        '✍️ <b>Gerador de Ofícios e Minutas · IA</b>\n\n'
        'Qual <b>tipo de documento</b> você precisa gerar?\n\n'
        '1️⃣ Ofício\n'
        '2️⃣ Memorando\n'
        '3️⃣ Portaria\n'
        '4️⃣ Notificação\n'
        '5️⃣ Declaração\n\n'
        '<i>Digite o número ou o nome do tipo:</i>'
    )
    kb = {'inline_keyboard': [
        [{'text': '📄 Ofício', 'callback_data': 'minuta_tipo_oficio'},
         {'text': '📋 Memorando', 'callback_data': 'minuta_tipo_memorando'}],
        [{'text': '📜 Portaria', 'callback_data': 'minuta_tipo_portaria'},
         {'text': '📢 Notificação', 'callback_data': 'minuta_tipo_notificacao'}],
        [{'text': '📃 Declaração', 'callback_data': 'minuta_tipo_declaracao'}],
        [{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]
    ]}
    if edit_msg:
        edit_message(edit_msg[0], edit_msg[1], text, reply_markup=kb)
    else:
        send_message(chat_id, text, reply_markup=kb)


def handle_minuta_tipo(chat_id: int, tipo: str):
    """Salva o tipo e pede o assunto."""
    set_state(chat_id, {'step': STEP_MINUTA_ASSUNTO, 'minuta_tipo': tipo})
    send_message(chat_id,
        f'✅ Tipo: <b>{tipo}</b>\n\n'
        'Agora descreva o <b>assunto / objeto</b> do documento:\n'
        '<i>(Ex: Solicitação de manutenção de via pública na Rua das Flores)</i>',
        reply_markup={'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]}
    )


def handle_minuta_assunto(chat_id: int, assunto: str):
    """Salva o assunto e pede o destinatário."""
    state = get_state(chat_id) or {}
    state['assunto'] = assunto.strip()
    state['step'] = STEP_MINUTA_DEST
    set_state(chat_id, state)
    send_message(chat_id,
        f'✅ Assunto registrado.\n\n'
        'Digite o <b>nome e cargo do destinatário</b>:\n'
        '<i>(Ex: Secretário Municipal de Infraestrutura, João Silva)</i>',
        reply_markup={'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]}
    )


def handle_minuta_dest(chat_id: int, destinatario: str):
    """Salva o destinatário e gera a minuta com IA."""
    state = get_state(chat_id) or {}
    tipo = state.get('minuta_tipo', 'Ofício')
    assunto = state.get('assunto', '')
    clear_state(chat_id)

    msg_id = send_message(chat_id, '⏳ <i>Gerando documento com IA…</i>')['result']['message_id']
    hoje = date.today().strftime('%d de %B de %Y')
    # Fix month names to Portuguese
    meses = {'January': 'janeiro', 'February': 'fevereiro', 'March': 'março', 'April': 'abril',
             'May': 'maio', 'June': 'junho', 'July': 'julho', 'August': 'agosto',
             'September': 'setembro', 'October': 'outubro', 'November': 'novembro', 'December': 'dezembro'}
    for en, pt in meses.items():
        hoje = hoje.replace(en, pt)

    prompt = f"""Você é um redator oficial da Prefeitura Municipal de Inajá – PE.
Gere um {tipo} formal e completo com as seguintes informações:
- Data: {hoje}
- Prefeitura: Prefeitura Municipal de Inajá – PE
- Destinatário: {destinatario.strip()}
- Assunto: {assunto}

O documento deve:
- Usar linguagem formal e técnica da administração pública brasileira
- Seguir a estrutura padrão brasileira de documentos oficiais
- Ter número fictício de ofício/memorando se necessário (ex: Ofício Nº 001/2026/PMI)
- Incluir fecho formal e assinatura genérica (Prefeito Municipal)

Retorne APENAS o texto do documento, formatado, sem explicações adicionais."""

    try:
        resp = requests.post(f'{SERVER_URL}/api/ia/chat',
            json={'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.3, 'max_tokens': 1500},
            timeout=60)
        data = resp.json()
        if not resp.ok:
            err = data.get('error') or {}
            edit_message(chat_id, msg_id, f'⚠️ Erro da IA: {err.get("message", str(err))}')
            return
        minuta = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
    except Exception as e:
        edit_message(chat_id, msg_id, f'⚠️ Erro ao contatar servidor IA: {e}')
        return

    header = f'✍️ <b>{tipo} Gerado pela IA</b>\n\n'
    full_msg = header + minuta
    if len(full_msg) > 4000:
        full_msg = full_msg[:4000] + '\n…<i>(documento truncado)</i>'

    edit_message(chat_id, msg_id, full_msg, reply_markup={'inline_keyboard': [
        [{'text': '✍️ Gerar novo documento', 'callback_data': 'cmd_minuta'}],
        [{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]
    ]})


# ════════════════════════════════════════════════════════════════════════════
# Feature 5 – /relatorio: Relatório Financeiro Mensal
# ════════════════════════════════════════════════════════════════════════════

def cmd_relatorio(chat_id: int, edit_msg: tuple | None = None):
    """Gera relatório financeiro do mês atual a partir do DB."""
    msg_id_val = None
    if edit_msg:
        edit_message(edit_msg[0], edit_msg[1], '⏳ <i>Gerando relatório financeiro…</i>')
        msg_id_val = edit_msg[1]
    else:
        msg_id_val = send_message(chat_id, '⏳ <i>Gerando relatório financeiro…</i>')['result']['message_id']

    try:
        hoje = date.today()
        mes_atual = f'{hoje.year}-{hoje.month:02d}'
        mes_nome_meses = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
                          'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
        mes_nome = f'{mes_nome_meses[hoje.month-1]}/{hoje.year}'

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        # Total de empenhos do mês
        empenhos_rows = conn.execute("""
            SELECT COUNT(*) as qtd, COALESCE(SUM(CAST(REPLACE(REPLACE(valor,'R$',''),' ','') AS REAL)),0) as total
            FROM empenhos WHERE strftime('%Y-%m', criado_em) = ?
        """, (mes_atual,)).fetchone()

        # Total de protocolos do mês
        prot_rows = conn.execute("""
            SELECT COUNT(*) as qtd FROM protocolos WHERE strftime('%Y-%m', criado_em) = ?
        """, (mes_atual,)).fetchone()

        # Total de despesas do mês
        desp_rows = conn.execute("""
            SELECT COUNT(*) as qtd, COALESCE(SUM(CAST(valor AS REAL)),0) as total
            FROM despesas WHERE strftime('%Y-%m', data) = ?
        """, (mes_atual,)).fetchone()

        # Tarefas kanban por status
        tasks_todo = conn.execute("SELECT COUNT(*) FROM kanban_tasks WHERE status='todo'").fetchone()[0]
        tasks_prog = conn.execute("SELECT COUNT(*) FROM kanban_tasks WHERE status='in-progress'").fetchone()[0]
        tasks_done = conn.execute("SELECT COUNT(*) FROM kanban_tasks WHERE status='done'").fetchone()[0]

        # Credores fixos
        qtd_credores = conn.execute("SELECT COUNT(*) FROM credores WHERE ativo=1").fetchone()[0]
        total_credores = conn.execute("SELECT COALESCE(SUM(valor),0) FROM credores WHERE ativo=1").fetchone()[0]

        conn.close()

        def fmt(v):
            try:
                return f'R$ {float(v):,.2f}'.replace(',','X').replace('.',',').replace('X','.')
            except Exception:
                return 'R$ —'

        empenhos_qtd = empenhos_rows['qtd'] if empenhos_rows else 0
        empenhos_total = empenhos_rows['total'] if empenhos_rows else 0
        prot_qtd = prot_rows['qtd'] if prot_rows else 0
        desp_qtd = desp_rows['qtd'] if desp_rows else 0
        desp_total = desp_rows['total'] if desp_rows else 0

        msg = (
            f'📊 <b>Relatório Financeiro — {mes_nome}</b>\n'
            f'<i>Gerado em {hoje.strftime("%d/%m/%Y às %H:%M")}</i>\n'
            f'{"─" * 30}\n\n'
            f'📋 <b>Empenhos do Mês</b>\n'
            f'  • Quantidade: {empenhos_qtd}\n'
            f'  • Valor Total: {fmt(empenhos_total)}\n\n'
            f'📂 <b>Protocolos Abertos no Mês</b>\n'
            f'  • Quantidade: {prot_qtd}\n\n'
            f'💸 <b>Despesas Registradas no Mês</b>\n'
            f'  • Quantidade: {desp_qtd}\n'
            f'  • Valor Total: {fmt(desp_total)}\n\n'
            f'👥 <b>Credores Fixos Ativos</b>\n'
            f'  • Quantidade: {qtd_credores}\n'
            f'  • Folha Mensal: {fmt(total_credores)}\n\n'
            f'📌 <b>Kanban de Tarefas</b>\n'
            f'  • A fazer: {tasks_todo}\n'
            f'  • Em andamento: {tasks_prog}\n'
            f'  • Concluídas: {tasks_done}\n'
        )

        edit_message(chat_id, msg_id_val, msg, reply_markup={'inline_keyboard': [
            [{'text': '🔄 Atualizar', 'callback_data': 'cmd_relatorio'}],
            [{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]
        ]})

    except Exception as e:
        log.error('Erro no relatório: %s', e)
        edit_message(chat_id, msg_id_val, f'⚠️ Erro ao gerar relatório: {e}')


# ════════════════════════════════════════════════════════════════════════════
# Feature 10 – /log: Log de Atividades do Sistema
# ════════════════════════════════════════════════════════════════════════════

def cmd_log(chat_id: int, edit_msg: tuple | None = None):
    """Exibe as últimas atividades registradas no sistema."""
    msg_id_val = None
    if edit_msg:
        edit_message(edit_msg[0], edit_msg[1], '⏳ <i>Buscando log de atividades…</i>')
        msg_id_val = edit_msg[1]
    else:
        msg_id_val = send_message(chat_id, '⏳ <i>Buscando log de atividades…</i>')['result']['message_id']
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        linhas: list[str] = []

        # Empenhos recentes
        for r in conn.execute("SELECT numero, credor, criado_em FROM empenhos ORDER BY criado_em DESC LIMIT 4").fetchall():
            linhas.append(f'📋 Empenho <b>{r["numero"] or "s/n"}</b> — {r["credor"][:25]} <i>({r["criado_em"][:16]})</i>')

        # Protocolos recentes
        for r in conn.execute("SELECT numero, assunto, criado_em FROM protocolos ORDER BY criado_em DESC LIMIT 4").fetchall():
            linhas.append(f'📂 Protocolo <b>{r["numero"]}</b> — {(r["assunto"] or "")[:25]} <i>({r["criado_em"][:16]})</i>')

        # Tarefas kanban recentes
        for r in conn.execute("SELECT title, status, atualizado_em FROM kanban_tasks ORDER BY atualizado_em DESC LIMIT 4").fetchall():
            status_map = {'todo': '⬜', 'in-progress': '🔄', 'done': '✅'}
            emoji = status_map.get(r['status'], '❓')
            linhas.append(f'{emoji} Tarefa: {r["title"][:30]} <i>({r["atualizado_em"][:16]})</i>')

        # Despesas recentes
        for r in conn.execute("SELECT descricao, valor, data FROM despesas ORDER BY data DESC LIMIT 4").fetchall():
            try:
                v = f'R$ {float(r["valor"]):,.2f}'.replace(',','X').replace('.',',').replace('X','.')
            except Exception:
                v = str(r['valor'])
            linhas.append(f'💸 Despesa: {(r["descricao"] or "")[:25]} — {v} <i>({r["data"][:10]})</i>')

        conn.close()

        if not linhas:
            body = '<i>Nenhuma atividade registrada ainda.</i>'
        else:
            body = '\n'.join(linhas)

        msg = f'🗒 <b>Log de Atividades — Sistema</b>\n<i>Últimas entradas por módulo</i>\n{"─"*30}\n\n{body}'
        edit_message(chat_id, msg_id_val, msg, reply_markup={'inline_keyboard': [
            [{'text': '🔄 Atualizar', 'callback_data': 'cmd_log'}],
            [{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]
        ]})
    except Exception as e:
        log.error('Erro no log: %s', e)
        edit_message(chat_id, msg_id_val, f'⚠️ Erro ao buscar log: {e}')


# ════════════════════════════════════════════════════════════════════════════

def handle_message(msg: dict):
    """Processa mensagens de texto e arquivos recebidos."""
    chat_id = msg['chat']['id']
    text    = (msg.get('text') or '').strip()
    
    document = msg.get('document')
    photo = msg.get('photo')

    if not is_authorized(chat_id):
        send_message(chat_id, '⛔ Acesso negado.')
        return

    # Se a mensagem tiver arquivo e a gente estiver esperando um arquivo
    state = get_state(chat_id)
    step = state.get('step') if state else None
    
    if (document or photo) and step in {STEP_UP_PDF, STEP_UP_RENOMEAR, STEP_UP_EMPENHO, STEP_UP_AUDITOR, STEP_UP_EXTRATO}:
        file_id = document['file_id'] if document else photo[-1]['file_id']
        file_name = document['file_name'] if document else 'imagem.jpg'
        
        if step == STEP_UP_PDF:
            process_pdf_extraction(chat_id, file_id, file_name)
        elif step == STEP_UP_RENOMEAR:
            process_file_rename(chat_id, file_id, file_name)
        elif step == STEP_UP_EMPENHO:
            if document and not file_name.lower().endswith('.pdf'):
                send_message(chat_id, '⚠️ Para geração de empenho por arquivo, envie apenas PDF. (Ou envie imagens via web app).')
            else:
                process_empenho_pdf(chat_id, file_id)
        elif step == STEP_UP_AUDITOR:
            threading.Thread(target=process_auditor_file, args=(chat_id, file_id, file_name), daemon=True).start()
        elif step == STEP_UP_EXTRATO:
            if not file_name.lower().endswith('.pdf'):
                send_message(chat_id, '⚠️ Envie apenas um arquivo PDF para análise de extrato.')
            else:
                threading.Thread(target=process_extrato_file, args=(chat_id, file_id, file_name), daemon=True).start()
        elif step == STEP_UP_RESUMIR:
            threading.Thread(target=process_resumir_file, args=(chat_id, file_id, file_name), daemon=True).start()
        return

    # Comandos
    if text.startswith('/start') or text.startswith('/menu'):
        clear_state(chat_id)
        nome = msg.get('from', {}).get('first_name', '') or ''
        saudacao = f'Olá, {nome}! 👋\n\n' if nome else 'Olá! 👋\n\n'
        send_message(chat_id, saudacao + menu_text(), reply_markup=keyboard_main())
        return

    if text.startswith('/help') or text.lower() in {'ajuda', 'help', '?'}:
        send_message(chat_id, (
            '📖 <b>Comandos disponíveis</b>\n\n'
            '🏠 <b>Menu e Navegação</b>\n'
            '/start  ou  /menu  — Abre o painel principal\n'
            '/help  — Esta ajuda\n\n'
            '📋 <b>Tarefas (Kanban)</b>\n'
            '/tarefa  — Criar nova tarefa passo a passo\n'
            '/tarefas  — Ver todas as tarefas\n'
            '/buscar <i>palavra</i>  — Buscar tarefas por título\n'
            '/cancelar  — Cancela operação em andamento\n\n'
            '🛒 <b>Aquisições</b>\n'
            '/aquisicao  — Nova solicitação de aquisição\n\n'
            '✈️ <b>Diárias (Viagem)</b>\n'
            '/diarias  — Calculadora de diárias\n\n'
            '🛠️ <b>Utilitários</b>\n'
            '/cnpj [numero]  — Consulta dados de CNPJ\n'
            '/prazos  — Calculadora de prazos úteis\n\n'
            '📁 <b>Arquivos</b>\n'
            '/pdf  — Extrai texto de um PDF\n'
            '/renomear  — Renomeia arquivo usando IA\n\n'
            '📝 <b>Geradores e Formulários</b>\n'
            '/empenho  — Gerador inteligente de Nota de Empenho\n'
            '/rpa  — Calculadora e gerador de RPA\n\n'
            '🔎 <b>Pesquisa</b>\n'
            '/protocolos  — Buscar protocolos ou ofícios\n'
            '/despesas  — Buscar despesas (Transparência)\n\n'
            '💰 <b>Financeiro</b>\n'
            '/financeiro  — Analisador financeiro do mês\n\n'
            '📅 <b>Calendário</b>\n'
            '/calendario  — Calendário de pagamentos\n\n'
            '📊 <b>Sistema</b>\n'
            '/logs  — Últimas ações registradas\n'
            '/status  — Status geral do sistema\n'
        ), reply_markup={'inline_keyboard': [[{'text': '🔙 Voltar ao Menu', 'callback_data': 'cmd_menu'}]]})
        return

    if text.startswith('/tarefa') or text.lower() in {'nova tarefa', 'nova', 'criar tarefa'}:
        start_new_task_flow(chat_id)
        return

    if text.startswith('/aquisicao') or text.lower() in {'nova aquisicao', 'nova aquisição', 'aquisicao', 'aquisição'}:
        start_new_aquisicao_flow(chat_id)
        return

    if text.startswith('/diaria') or text.startswith('/viagem') or text.lower() in {'diarias', 'diárias', 'diaria', 'diária', 'calc diaria', 'viagem'}:
        start_diarias_flow(chat_id)
        return

    if text.startswith('/cnpj'):
        parts = text.split()
        if len(parts) > 1:
            run_cnpj_query(chat_id, parts[1])
        else:
            start_cnpj_flow(chat_id)
        return

    if text.startswith('/empenho'):
        start_empenho_flow(chat_id)
        return

    if text.startswith('/rpa'):
        start_rpa_flow(chat_id)
        return
        return

    if text.startswith('/prazo') or text.lower() in {'prazos', 'prazo'}:
        start_prazos_flow(chat_id)
        return

    if text.startswith('/pdf'):
        start_pdf_flow(chat_id)
        return
        
    if text.startswith('/renomear'):
        start_renomear_flow(chat_id)
        return

    if text.startswith('/protocolo'):
        start_protocolos_flow(chat_id)
        return

    if text.startswith('/despesa'):
        start_despesas_flow(chat_id)
        return

    if text.startswith('/resumir') or text.lower() in {'resumir', 'resumo'}:
        start_resumir_flow(chat_id)
        return

    if text.startswith('/minuta') or text.lower() in {'minuta', 'oficio', 'ofício', 'memorando'}:
        start_minuta_flow(chat_id)
        return

    if text.startswith('/relatorio') or text.lower() in {'relatorio', 'relatório'}:
        cmd_relatorio(chat_id)
        return

    if text.startswith('/log') and not text.startswith('/logs'):
        cmd_log(chat_id)
        return

    if text.startswith('/buscar') or text.lower().startswith('buscar '):
        # Extrai o termo de busca
        if text.startswith('/buscar'):
            termo = text[7:].strip()
        else:
            termo = text[7:].strip()
        if not termo:
            send_message(chat_id,
                '🔍 <b>Buscar Tarefas</b>\n\nDigite o que quer buscar:\n'
                '<i>Exemplo: /buscar reunião</i>')
            return
        results = db_buscar_tarefas(termo)
        if not results:
            send_message(chat_id,
                f'🔍 Nenhuma tarefa encontrada para <b>"{termo}"</b>.',
                reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})
        else:
            texto  = format_task_list(results, f'🔍 Resultados para "{termo}"', grouped=False)
            send_message(chat_id, texto,
                reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})
        return

    if text.startswith('/logs'):
        try:
            logs = db_logs_recentes(12)
            if not logs:
                send_message(chat_id, '📊 Nenhum log encontrado.')
                return
            ACAO_EMOJI = {'EMPENHAR': '✅', 'DESEMPENHAR': '↩️', 'IMPORTAR': '📥',
                          'CRIAR': '➕', 'EDITAR': '✏️', 'EXCLUIR': '🗑'}
            lines = ['📊 <b>Últimas Ações do Sistema</b>\n']
            for lg in logs:
                emoji = ACAO_EMOJI.get((lg.get('acao') or '').upper(), '🔹')
                nome  = (lg.get('credor_nome') or '—')[:25]
                det   = (lg.get('detalhes') or '')[:20]
                data  = (lg.get('data') or '')[:16]
                lines.append(f'{emoji} <b>{lg.get("acao","?")} </b> {nome}  <code>{data}</code>')
                if det:
                    lines.append(f'   └ <i>{det}</i>')
            send_message(chat_id, '\n'.join(lines),
                reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})
        except Exception as e:
            send_message(chat_id, f'⚠️ Erro ao buscar logs: <code>{e}</code>')
        return

    if text.startswith('/status'):
        try:
            credores  = db_contar_credores()
            tarefas   = {s: len(db_listar_tarefas(s)) for s in ('todo', 'in-progress', 'done')}
            hoje      = date.today()
            fin       = db_analise_financeira(hoje.year, hoje.month)
            proximos  = [ev for ev in calcular_eventos_mes(hoje.year, hoje.month) if ev['data'] >= hoje]
            prox_ev   = proximos[0] if proximos else None
            send_message(chat_id, (
                f'📊 <b>Status do Sistema</b>\n'
                f'<i>{hoje.strftime("%d/%m/%Y")}</i>\n\n'
                f'<b>👥 Credores</b>\n'
                f'Ativos: {credores["ativos"]}  |  Inativos: {credores["inativos"]}\n\n'
                f'<b>📋 Kanban</b>\n'
                f'A Fazer: {tarefas["todo"]}  |  Em Progresso: {tarefas["in-progress"]}  |  Concluído: {tarefas["done"]}\n\n'
                f'<b>💰 Empenhos {MESES_PT_ABREV[hoje.month]}</b>\n'
                f'Empenhado: {_moeda(fin["total_empenhado"])} ({fin["pct_empenhado"]:.0f}%)\n'
                f'Pendente:  {_moeda(fin["total_pendente"])}\n\n'
                f'<b>📅 Próximo Evento</b>\n'
                + (f'{prox_ev["emoji"]} {prox_ev["texto"]} — {prox_ev["data"].strftime("%d/%m")} '
                   f'({(prox_ev["data"]-hoje).days}d)' if prox_ev else '<i>Nenhum</i>')
            ), reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})
        except Exception as e:
            send_message(chat_id, f'⚠️ Erro: <code>{e}</code>')
        return

    if text.startswith('/financeiro') or text.lower() in {'financeiro', 'financ', 'financas', 'finanças'}:
        hoje = date.today()
        try:
            dados = db_analise_financeira(hoje.year, hoje.month)
            send_message(chat_id, format_analise_financeira(dados),
                         reply_markup=keyboard_financeiro(hoje.year, hoje.month))
        except Exception as e:
            log.error('Erro no financeiro: %s', e)
            send_message(chat_id, f'⚠️ Não foi possível gerar o relatório financeiro.\n<code>{e}</code>',
                         reply_markup=keyboard_main())
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
        step = state.get('step')
        # Minuta multi-step
        if step == STEP_MINUTA_ASSUNTO:
            handle_minuta_assunto(chat_id, text)
            return
        elif step == STEP_MINUTA_DEST:
            handle_minuta_dest(chat_id, text)
            return
        handle_conversation_step(chat_id, text, state)
    else:
        # Sem contexto — mostrar menu + dica
        send_message(chat_id,
            menu_text() + '\n\n<i>💡 Digite /help para ver todos os comandos.</i>',
            reply_markup=keyboard_main())


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

    if data == 'cmd_nova_aquisicao':
        start_new_aquisicao_flow(chat_id, edit_msg=(chat_id, msg_id))
        return

    if data == 'cmd_calc_diarias':
        start_diarias_flow(chat_id, edit_msg=(chat_id, msg_id))
        return

    if data == 'cmd_consulta_cnpj':
        start_cnpj_flow(chat_id, edit_msg=(chat_id, msg_id))
        return

    if data == 'cmd_calc_prazos':
        start_prazos_flow(chat_id, edit_msg=(chat_id, msg_id))
        return

    if data == 'cmd_extrator_pdf':
        start_pdf_flow(chat_id, edit_msg=(chat_id, msg_id))
        return
        
    if data == 'cmd_renomear_arquivo':
        start_renomear_flow(chat_id, edit_msg=(chat_id, msg_id))
        return

    if data == 'cmd_gerar_empenho':
        start_empenho_flow(chat_id, edit_msg=(chat_id, msg_id))
        return

    if data == 'cmd_gerar_rpa':
        start_rpa_flow(chat_id, edit_msg=(chat_id, msg_id))
        return

    if data == 'cmd_buscar_protocolos':
        start_protocolos_flow(chat_id, edit_msg=(chat_id, msg_id))
        return

    if data == 'cmd_buscar_despesas':
        start_despesas_flow(chat_id, edit_msg=(chat_id, msg_id))
        return

    if data == 'cmd_auditor_nf':
        start_auditor_flow(chat_id, edit_msg=(chat_id, msg_id))
        return

    if data == 'cmd_extrato_bancario':
        start_extrato_flow(chat_id, edit_msg=(chat_id, msg_id))
        return

    if data == 'cmd_resumir':
        start_resumir_flow(chat_id, edit_msg=(chat_id, msg_id))
        return

    if data == 'cmd_minuta':
        start_minuta_flow(chat_id, edit_msg=(chat_id, msg_id))
        return

    if data == 'cmd_relatorio':
        cmd_relatorio(chat_id, edit_msg=(chat_id, msg_id))
        return

    if data == 'cmd_log':
        cmd_log(chat_id, edit_msg=(chat_id, msg_id))
        return

    if data.startswith('minuta_tipo_'):
        tipo_map = {
            'minuta_tipo_oficio': 'Ofício',
            'minuta_tipo_memorando': 'Memorando',
            'minuta_tipo_portaria': 'Portaria',
            'minuta_tipo_notificacao': 'Notificação',
            'minuta_tipo_declaracao': 'Declaração',
        }
        tipo = tipo_map.get(data, 'Ofício')
        clear_state(chat_id)
        handle_minuta_tipo(chat_id, tipo)
        return

    if data == 'ignore':
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

    # Mudar status de tarefa via bot
    if data.startswith('tsk_status_'):
        # formato: tsk_status_TASK_ID_NOVO_STATUS
        partes = data.split('_', 4)  # ['tsk', 'status', TASK_ID, NOVO_STATUS]
        try:
            task_id    = partes[2]
            novo_status = partes[3]
        except IndexError:
            answer_callback(query_id, '⚠️ Dados inválidos.', show_alert=True)
            return
        tarefa = db_atualizar_status_tarefa(task_id, novo_status)
        if tarefa:
            s_label = STATUS_LABEL.get(novo_status, novo_status)
            s_emoji = STATUS_EMOJI.get(novo_status, '📋')
            answer_callback(query_id, f'{s_emoji} Status: {s_label}', show_alert=False)
            # Atualiza a mensagem com as tarefas
            tasks = db_listar_tarefas()
            edit_message(chat_id, msg_id,
                         format_task_list(tasks, '📋 Todas as Tarefas', grouped=True),
                         reply_markup={'inline_keyboard': [[
                             {'text': '🔙 Menu', 'callback_data': 'cmd_menu'}
                         ]]})
            log.info('Status alterado via Telegram: [%s] %s → %s', task_id, tarefa.get('title'), novo_status)
        else:
            answer_callback(query_id, '⚠️ Tarefa não encontrada.', show_alert=True)
        return

    # Busca rápida via bot (inline)
    if data == 'cmd_buscar':
        set_state(chat_id, {'step': 'aguardando_busca'})
        edit_message(chat_id, msg_id,
            '🔍 <b>Buscar Tarefas</b>\n\nDigite o termo de busca:',
            reply_markup={'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]})
        return

    if data == 'cmd_logs':
        try:
            logs = db_logs_recentes(10)
            ACAO_EMOJI = {'EMPENHAR': '✅', 'DESEMPENHAR': '↩️', 'IMPORTAR': '📥', 'CRIAR': '➕', 'EDITAR': '✏️', 'EXCLUIR': '🗑'}
            lines = ['📊 <b>Últimas Ações</b>\n']
            for lg in (logs or []):
                emoji = ACAO_EMOJI.get((lg.get('acao') or '').upper(), '🔹')
                nome  = (lg.get('credor_nome') or '—')[:22]
                data2 = (lg.get('data') or '')[:16]
                lines.append(f'{emoji} {lg.get("acao","?")}  {nome}  <code>{data2}</code>')
            edit_message(chat_id, msg_id, '\n'.join(lines) if logs else '📊 Nenhum log registrado.',
                reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})
        except Exception as e:
            edit_message(chat_id, msg_id, f'⚠️ Erro: <code>{e}</code>', reply_markup=keyboard_main())
        return

    if data == 'cmd_financeiro':
        hoje = date.today()
        try:
            dados = db_analise_financeira(hoje.year, hoje.month)
            edit_message(chat_id, msg_id,
                         format_analise_financeira(dados),
                         reply_markup=keyboard_financeiro(hoje.year, hoje.month))
        except Exception as e:
            log.error('Erro cmd_financeiro: %s', e)
            edit_message(chat_id, msg_id, f'⚠️ Erro ao gerar relatório financeiro:\n<code>{e}</code>',
                         reply_markup=keyboard_main())
        return

    # Navegação financeira: fin_ANO_MES
    if data.startswith('fin_') and not data.startswith('fin_emp') and not data.startswith('fin_pend'):
        parts = data.split('_')
        try:
            ano_nav = int(parts[1])
            mes_nav = int(parts[2])
            if not (1 <= mes_nav <= 12):
                raise ValueError
        except (IndexError, ValueError):
            ano_nav = date.today().year
            mes_nav = date.today().month
        try:
            dados = db_analise_financeira(ano_nav, mes_nav)
            edit_message(chat_id, msg_id,
                         format_analise_financeira(dados),
                         reply_markup=keyboard_financeiro(ano_nav, mes_nav))
        except Exception as e:
            log.error('Erro navegação financeira: %s', e)
            edit_message(chat_id, msg_id, f'⚠️ Erro: <code>{e}</code>',
                         reply_markup=keyboard_main())
        return

    # Drill-down: lista de empenhados ou pendentes
    if data.startswith('fin_emp_') or data.startswith('fin_pend_'):
        partes = data.split('_')
        try:
            # fin_emp_ANO_MES ou fin_pend_ANO_MES
            modo  = partes[1]  # 'emp' ou 'pend'
            ano_d = int(partes[2])
            mes_d = int(partes[3])
        except (IndexError, ValueError):
            ano_d = date.today().year
            mes_d = date.today().month
            modo  = 'pend'
        try:
            dados = db_analise_financeira(ano_d, mes_d)
            texto = format_lista_credores_fin(dados, modo)
            kb_back = {'inline_keyboard': [[
                {'text': '← Voltar', 'callback_data': f'fin_{ano_d}_{mes_d}'},
                {'text': '🔙 Menu',   'callback_data': 'cmd_menu'},
            ]]}
            edit_message(chat_id, msg_id, texto, reply_markup=kb_back)
        except Exception as e:
            log.error('Erro drill-down financeiro: %s', e)
            edit_message(chat_id, msg_id, f'⚠️ Erro: <code>{e}</code>',
                         reply_markup=keyboard_main())
        return

    # Dentro do fluxo de criação de tarefa ou aquisição
    state = get_state(chat_id)
    if not state:
        edit_message(chat_id, msg_id, '⚠️ Sessão expirada. Recomeçando...')
        start_new_task_flow(chat_id)
        return

    # Pular observação da aquisição
    if data == 'aq_obs_skip' and state.get('step') == STEP_AQ_OBS:
        state['obs'] = ''
        finalize_aquisicao(chat_id, msg_id, state)
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


def start_new_task_flow(chat_id: int, edit_msg: tuple | None = None):
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
    """Avança a conversa de criação de tarefa ou aquisição com base na etapa atual."""
    step = state.get('step')

    if step and step.startswith('aq_'):
        handle_aquisicao_step(chat_id, text, state)
        return

    if step and step.startswith('di_'):
        handle_diarias_step(chat_id, text, state)
        return

    if step and step.startswith('cnpj_'):
        handle_cnpj_step(chat_id, text, state)
        return

    if step and step.startswith('pz_'):
        handle_prazos_step(chat_id, text, state)
        return

    if step == STEP_RPA_NOME:
        handle_rpa_nome(chat_id, text)
        return

    if step == STEP_RPA_VALOR:
        handle_rpa_valor(chat_id, text)
        return

    if step == STEP_UP_EMPENHO:
        process_empenho_text(chat_id, text)
        return

    if step == STEP_PROT_BUSCA:
        handle_protocolos_busca(chat_id, text)
        return

    if step == STEP_DESP_BUSCA:
        handle_despesas_busca(chat_id, text)
        return

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


def start_new_aquisicao_flow(chat_id: int, edit_msg: tuple | None = None):
    """Inicia o fluxo guiado de criação de Solicitação de Aquisição."""
    state = {'step': STEP_AQ_SOLICITANTE, 'solicitante': '', 'empresa': '', 'itens': '', 'obs': ''}
    set_state(chat_id, state)

    text = (
        '🛒 <b>Nova Solicitação de Aquisição</b>\n\n'
        '1️⃣ <b>Qual é o nome do Solicitante?</b>\n'
        '<i>Digite o nome abaixo:</i>'
    )
    kb = {'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]}

    if edit_msg:
        edit_message(edit_msg[0], edit_msg[1], text, reply_markup=kb)
    else:
        send_message(chat_id, text, reply_markup=kb)


def handle_aquisicao_step(chat_id: int, text: str, state: dict):
    """Avança a conversa de criação de aquisição."""
    step = state.get('step')

    if step == STEP_AQ_SOLICITANTE:
        if len(text) < 2:
            send_message(chat_id, '⚠️ Nome muito curto. Digite novamente.')
            return
        state['solicitante'] = text
        state['step'] = STEP_AQ_EMPRESA
        set_state(chat_id, state)
        send_message(
            chat_id,
            f'✅ Solicitante: <b>{text}</b>\n\n'
            '2️⃣ <b>Qual é o nome da Empresa/Fornecedor?</b>\n'
            '<i>Digite abaixo:</i>',
            reply_markup={'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]}
        )

    elif step == STEP_AQ_EMPRESA:
        state['empresa'] = text
        state['step'] = STEP_AQ_ITENS
        set_state(chat_id, state)
        send_message(
            chat_id,
            f'✅ Empresa: <b>{text}</b>\n\n'
            '3️⃣ <b>Quais são os itens da solicitação?</b>\n'
            '<i>Descreva os itens (ex: 10x Papel A4 a R$ 20,00 cada). Pode mandar todos em uma única mensagem.</i>',
            reply_markup={'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]}
        )

    elif step == STEP_AQ_ITENS:
        state['itens'] = text
        state['step'] = STEP_AQ_OBS
        set_state(chat_id, state)
        send_message(
            chat_id,
            f'✅ Itens registrados.\n\n'
            '4️⃣ <b>Observações adicionais</b> (opcional):\n'
            '<i>Digite algo ou clique em "Pular".</i>',
            reply_markup={'inline_keyboard': [
                [
                    {'text': '⏭ Pular observações', 'callback_data': 'aq_obs_skip'},
                    {'text': '❌ Cancelar',          'callback_data': 'cmd_cancelar'}
                ]
            ]}
        )

    elif step == STEP_AQ_OBS:
        state['obs'] = text
        finalize_aquisicao(chat_id, None, state)


def finalize_aquisicao(chat_id: int, msg_id: int | None, state: dict):
    clear_state(chat_id)
    
    lines = [
        '📄 <b>Solicitação de Aquisição / Fornecimento</b>',
        '━━━━━━━━━━━━━━━━━━━━',
        f'👤 <b>Solicitante:</b> {state.get("solicitante", "—")}',
        f'🏢 <b>Empresa:</b> {state.get("empresa", "—")}',
        f'📅 <b>Data:</b> {date.today().strftime("%d/%m/%Y")}',
        '',
        '📦 <b>Itens:</b>',
        f'<i>{state.get("itens", "—")}</i>',
    ]
    
    if state.get("obs"):
        lines.append('')
        lines.append('📝 <b>Observações:</b>')
        lines.append(f'<i>{state.get("obs")}</i>')

    lines.append('━━━━━━━━━━━━━━━━━━━━')
    lines.append('<i>Prefeitura Municipal de Inajá</i>')
    
    doc = '\n'.join(lines)

    if msg_id:
        edit_message(chat_id, msg_id, '✅ <b>Solicitação gerada com sucesso! Você pode copiá-la ou encaminhá-la:</b>\n\n' + doc)
    else:
        send_message(chat_id, '✅ <b>Solicitação gerada com sucesso! Você pode copiá-la ou encaminhá-la:</b>\n\n' + doc)
        
    # Mostra o menu principal novamente em nova mensagem
    send_message(chat_id, menu_text(), reply_markup=keyboard_main())


def start_diarias_flow(chat_id: int, edit_msg: tuple | None = None):
    """Inicia o fluxo guiado de cálculo de Diárias."""
    state = {'step': STEP_DI_DATA_PARTIDA, 'dp': '', 'hp': '', 'dr': '', 'hr': ''}
    set_state(chat_id, state)

    text = (
        '✈️ <b>Calculadora de Diárias</b>\n\n'
        '1️⃣ <b>Qual é a data de Partida?</b>\n'
        '<i>Digite a data (ex: 15/03/2026):</i>'
    )
    kb = {'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]}

    if edit_msg:
        edit_message(edit_msg[0], edit_msg[1], text, reply_markup=kb)
    else:
        send_message(chat_id, text, reply_markup=kb)


def handle_diarias_step(chat_id: int, text: str, state: dict):
    step = state.get('step')
    kb = {'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]}

    if step == STEP_DI_DATA_PARTIDA:
        if len(text) < 5 or '/' not in text:
            send_message(chat_id, '⚠️ Formato inválido. Digite no formato DD/MM/AAAA:')
            return
        state['dp'] = text
        state['step'] = STEP_DI_HORA_PARTIDA
        set_state(chat_id, state)
        send_message(
            chat_id,
            f'✅ Data Partida: <b>{text}</b>\n\n'
            '2️⃣ <b>Qual é a hora da Partida?</b>\n'
            '<i>Digite o horário (ex: 08:30 ou 8:00):</i>',
            reply_markup=kb
        )

    elif step == STEP_DI_HORA_PARTIDA:
        if not (':' in text or 'h' in text.lower()):
            send_message(chat_id, '⚠️ Formato inválido. Digite no formato HH:MM (ex: 14:00):')
            return
        text = text.lower().replace('h', ':')
        state['hp'] = text
        state['step'] = STEP_DI_DATA_RETORNO
        set_state(chat_id, state)
        send_message(
            chat_id,
            f'✅ Hora Partida: <b>{text}</b>\n\n'
            '3️⃣ <b>Qual é a data de Retorno?</b>\n'
            '<i>Digite a data (ex: 16/03/2026):</i>',
            reply_markup=kb
        )

    elif step == STEP_DI_DATA_RETORNO:
        if len(text) < 5 or '/' not in text:
            send_message(chat_id, '⚠️ Formato inválido. Digite no formato DD/MM/AAAA:')
            return
        state['dr'] = text
        state['step'] = STEP_DI_HORA_RETORNO
        set_state(chat_id, state)
        send_message(
            chat_id,
            f'✅ Data Retorno: <b>{text}</b>\n\n'
            '4️⃣ <b>Qual é a hora de Retorno?</b>\n'
            '<i>Digite o horário (ex: 18:00):</i>',
            reply_markup=kb
        )

    elif step == STEP_DI_HORA_RETORNO:
        text = text.lower().replace('h', ':')
        state['hr'] = text
        
        # Realiza validação de datas e calcula
        _dt_formats = ["%d/%m/%Y %H:%M", "%d/%m/%y %H:%M", "%d/%m/%Y %H:%M:%S"]
        partida_dt = None
        retorno_dt = None
        
        for fmt in _dt_formats:
            try:
                partida_dt = datetime.strptime(f"{state['dp'].strip()} {state['hp'].strip()}", fmt)
                break
            except ValueError:
                pass
                
        for fmt in _dt_formats:
            try:
                retorno_dt = datetime.strptime(f"{state['dr'].strip()} {state['hr'].strip()}", fmt)
                break
            except ValueError:
                pass
                
        if partida_dt is None or retorno_dt is None:
            send_message(chat_id, '⚠️ Erro nas datas digitadas. Verifique se o formato foi DD/MM/AAAA e HH:MM. Digite novamente a Hora de Retorno.', reply_markup=kb)
            return
            
        if retorno_dt <= partida_dt:
            send_message(chat_id, '⚠️ A data/hora de retorno deve ser **depois** da partida. Digite corretamente a Hora de Retorno.', reply_markup=kb)
            return

        finalize_diarias(chat_id, state, partida_dt, retorno_dt)


def finalize_diarias(chat_id: int, state: dict, partida_dt: datetime, retorno_dt: datetime):
    clear_state(chat_id)
    
    diff_ms = (retorno_dt - partida_dt).total_seconds() * 1000
    total_hours = diff_ms / (1000.0 * 60.0 * 60.0)
    
    if total_hours < 12:
        num_diarias = 0
        explicacao = "Nenhuma diária é devida, pois o afastamento é inferior a 12 horas."
    else:
        num_diarias = int(total_hours // 24)
        horas_restantes = total_hours % 24
        if horas_restantes >= 12:
            num_diarias += 1
        if num_diarias == 0 and total_hours >= 12:
            num_diarias = 1

        explicacao = "Cálculo baseado na Legislação Municipal Vigente. "
        pC = int(total_hours // 24)
        if pC > 0:
            explicacao += f"{pC} diária(s) por período(s) completo(s) de 24h. "
        
        if num_diarias > pC and not (num_diarias == 1 and pC == 0 and total_hours < 24):
            explicacao += "Uma diária adicional foi concedida devido à fração de horas restante ser igual ou superior a 12 horas."
        elif num_diarias == 1 and pC == 0 and total_hours >= 12 and total_hours < 24:
            explicacao += f"Uma diária integral é devida pois o afastamento de {total_hours:.1f}h está entre 12h e 24h."
        elif num_diarias == pC and pC > 0:
            if 0 < horas_restantes < 12:
                explicacao += f"A fração restante de {horas_restantes:.1f}h é inferior a 12 horas e não gera diária adicional."

    lines = [
        '⚖️ <b>RELATÓRIO DE CÁLCULO DE DIÁRIAS</b>',
        '━━━━━━━━━━━━━━━━━━━━',
        f'🛫 <b>Partida:</b> {partida_dt.strftime("%d/%m/%Y")} às {partida_dt.strftime("%H:%M")}',
        f'🛬 <b>Retorno:</b> {retorno_dt.strftime("%d/%m/%Y")} às {retorno_dt.strftime("%H:%M")}',
        f'⏳ <b>Duração do afastamento:</b> {total_hours:.1f} horas',
        '',
        f'💵 <b>Diárias devidas:</b> {num_diarias}',
        '',
        'ℹ️ <b>Observação Legal:</b>',
        f'<i>{explicacao}</i>',
        '━━━━━━━━━━━━━━━━━━━━',
        f'<i>Calculado em: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}</i>'
    ]
    
    doc = '\n'.join(lines)
    send_message(chat_id, '✅ <b>Cálculo Efetuado:</b>\n\n' + doc)
    send_message(chat_id, menu_text(), reply_markup=keyboard_main())


def start_cnpj_flow(chat_id: int, edit_msg: tuple | None = None):
    state = {'step': STEP_CNPJ_NUM}
    set_state(chat_id, state)
    text = (
        '🏢 <b>Consulta CNPJ</b>\n\n'
        '<i>Digite o CNPJ que deseja consultar (apenas números ou formatado):</i>'
    )
    kb = {'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]}
    if edit_msg:
        edit_message(edit_msg[0], edit_msg[1], text, reply_markup=kb)
    else:
        send_message(chat_id, text, reply_markup=kb)


def handle_cnpj_step(chat_id: int, text: str, state: dict):
    run_cnpj_query(chat_id, text)


def run_cnpj_query(chat_id: int, cnpj_str: str):
    clear_state(chat_id)
    cnpj_clean = ''.join(filter(str.isdigit, cnpj_str))
    if len(cnpj_clean) != 14:
        send_message(chat_id, '⚠️ CNPJ inválido. Digite os 14 dígitos corretamente.',
                     reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})
        return

    send_message(chat_id, '⏳ Consultando Receita Federal...')
    try:
        resp = requests.get(f'https://brasilapi.com.br/api/cnpj/v1/{cnpj_clean}', timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            razao = data.get('razao_social', '—')
            fan = data.get('nome_fantasia')
            sit = data.get('descricao_situacao_cadastral', '—')
            end = f"{data.get('logradouro', '')}, {data.get('numero', '')} - {data.get('municipio', '')}/{data.get('uf', '')}"
            cnae = data.get('cnae_fiscal_descricao', '—')

            lines = [
                '🏢 <b>Consulta de CNPJ Oficial</b>',
                '━━━━━━━━━━━━━━━━━━━━',
                f'<b>Razão Social:</b> {razao}',
            ]
            if fan: lines.append(f'<b>Fantasia:</b> {fan}')
            lines.extend([
                f'<b>CNPJ:</b> {data.get("cnpj", "")}',
                f'<b>Situação:</b> {sit}',
                '',
                f'📍 <b>Endereço:</b> {end}',
                f'🏭 <b>CNAE Principal:</b> {cnae}',
                '',
                f'<b>Porte:</b> {data.get("porte", "—")}',
                f'<b>Abertura:</b> {data.get("data_inicio_atividade", "—")}',
            ])
            doc = '\n'.join(lines)
            send_message(chat_id, doc, reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})
        else:
            send_message(chat_id, f'❌ Erro ao consultar CNPJ: {resp.status_code}',
                         reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})
    except Exception as e:
        log.error(f"Erro na consulta de CNPJ: {e}")
        send_message(chat_id, f'❌ Ocorreu um erro: {e}',
                     reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})


def start_prazos_flow(chat_id: int, edit_msg: tuple | None = None):
    state = {'step': STEP_PZ_DATA}
    set_state(chat_id, state)
    text = (
        '⏰ <b>Calculadora de Prazos Úteis</b>\n\n'
        '1️⃣ <b>Qual a data inicial?</b>\n'
        '<i>(Formato: DD/MM/AAAA)</i>'
    )
    kb = {'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]}
    if edit_msg:
        edit_message(edit_msg[0], edit_msg[1], text, reply_markup=kb)
    else:
        send_message(chat_id, text, reply_markup=kb)


def handle_prazos_step(chat_id: int, text: str, state: dict):
    step = state.get('step')
    kb = {'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]}

    if step == STEP_PZ_DATA:
        if len(text) < 5 or '/' not in text:
            send_message(chat_id, '⚠️ Formato inválido. Digite no formato DD/MM/AAAA:', reply_markup=kb)
            return
        state['dt'] = text.strip()
        state['step'] = STEP_PZ_DIAS
        set_state(chat_id, state)
        send_message(
            chat_id,
            f'✅ Data Inicial: <b>{state["dt"]}</b>\n\n'
            '2️⃣ <b>Quantos dias deseja somar?</b>\n'
            '<i>(Apenas número)</i>',
            reply_markup=kb
        )

    elif step == STEP_PZ_DIAS:
        if not text.isdigit():
            send_message(chat_id, '⚠️ Por favor, digite apenas um número inteiro (ex: 15):', reply_markup=kb)
            return

        fmt = "%d/%m/%Y"
        try:
            start_date_str = state['dt']
            if len(start_date_str) == 8 and start_date_str.count('/') == 2:
                fmt = "%d/%m/%y"
            start_date = datetime.strptime(start_date_str, fmt)
        except ValueError:
            send_message(chat_id, '⚠️ Erro na data inicial. Tente recomeçar com formato correto (ex: 01/05/2026).', reply_markup=kb)
            start_prazos_flow(chat_id)
            return

        clear_state(chat_id)
        dias_soma = int(text)
        
        # Simple Business Days Calculation
        current_date = start_date
        dias_restantes = dias_soma
        
        while dias_restantes > 0:
            current_date += timedelta(days=1)
            # 5 = Saturday, 6 = Sunday
            if current_date.weekday() < 5:
                dias_restantes -= 1

        doc = (
            '⏰ <b>Calculadora de Prazos Úteis</b>\n'
            '━━━━━━━━━━━━━━━━━━━━\n'
            f'<b>Data Inicial:</b> {start_date.strftime("%d/%m/%Y")}\n'
            f'<b>Dias a somar (úteis):</b> {dias_soma}\n'
            f'<b>Data Final Prevista:</b> <b>{current_date.strftime("%d/%m/%Y")}</b>\n'
            '<i>Obs: Feriados não estão sendo considerados automaticamente. Ajuste manualmente se necessário.</i>/n'
            '━━━━━━━━━━━━━━━━━━━━\n'
        )
        send_message(chat_id, doc, reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})


def download_telegram_file(file_id: str) -> bytes | None:
    try:
        resp = requests.post(f'{TELEGRAM_API}/getFile', json={'file_id': file_id}, timeout=15)
        if not resp.json().get('ok'):
            return None
        file_path = resp.json()['result']['file_path']
        f_resp = requests.get(f'https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}', timeout=60)
        if f_resp.status_code == 200:
            return f_resp.content
    except Exception as e:
        log.error(f"Erro ao baixar arquivo do telegram: {e}")
    return None


def start_pdf_flow(chat_id: int, edit_msg: tuple | None = None):
    state = {'step': STEP_UP_PDF}
    set_state(chat_id, state)
    text = (
        '📄 <b>Extrator de PDF</b>\n\n'
        'Envie o arquivo PDF que você deseja extrair o texto.\n'
        '<i>Dica: PDFs baseados em imagem ainda não são suportados.</i>'
    )
    kb = {'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]}
    if edit_msg:
        edit_message(edit_msg[0], edit_msg[1], text, reply_markup=kb)
    else:
        send_message(chat_id, text, reply_markup=kb)


def process_pdf_extraction(chat_id: int, file_id: str, file_name: str):
    clear_state(chat_id)
    if not file_name.lower().endswith('.pdf'):
        send_message(chat_id, '⚠️ O arquivo enviado não parece ser um PDF.',
                     reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})
        return

    send_message(chat_id, f'📥 Baixando e processando <b>{file_name}</b>, aguarde...')
    content = download_telegram_file(file_id)
    if not content:
        send_message(chat_id, '❌ Falha ao processar o arquivo.',
                     reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})
        return

    try:
        import PyPDF2
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
        texto = ''
        for page in pdf_reader.pages[:10]: # Limita as primeiras 10 páginas para evitar travar
            texto += page.extract_text() + '\n'
            
        texto = texto.strip()
        if not texto:
            send_message(chat_id, '⚠️ Nenhum texto foi encontrado no arquivo (provavelmente é uma imagem/escaneado).',
                         reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})
            return
            
        send_message(chat_id, '✅ <b>Texto Extraído:</b>\n\n')
        # Telegram tem limite de ~4000 caracteres, quebrar se for longo
        for i in range(0, len(texto), 3500):
            send_message(chat_id, f"<code>{texto[i:i+3500]}</code>")
            
        send_message(chat_id, "━ Finalizado", reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})
    except Exception as e:
        log.error(f"Erro a extrair PDF: {e}")
        send_message(chat_id, f'❌ Erro ao ler PDF: {e}',
                     reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})


def start_renomear_flow(chat_id: int, edit_msg: tuple | None = None):
    state = {'step': STEP_UP_RENOMEAR}
    set_state(chat_id, state)
    text = (
        '✨ <b>Renomear com IA</b>\n\n'
        'Envie o arquivo (PDF ou Documento/Word) que você deseja que a IA leia e gere um nome automático.'
    )
    kb = {'inline_keyboard': [[{'text': '❌ Cancelar', 'callback_data': 'cmd_cancelar'}]]}
    if edit_msg:
        edit_message(edit_msg[0], edit_msg[1], text, reply_markup=kb)
    else:
        send_message(chat_id, text, reply_markup=kb)


def process_file_rename(chat_id: int, file_id: str, file_name: str):
    clear_state(chat_id)
    send_message(chat_id, f'📥 Baixando <b>{file_name}</b> e submetendo à IA...')
    
    content = download_telegram_file(file_id)
    if not content:
        send_message(chat_id, '❌ Falha ao processar o arquivo.',
                     reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})
        return
        
    extracted_text = f"Nome original: {file_name}"
    
    if file_name.lower().endswith('.pdf'):
        try:
            import PyPDF2
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
            texto = ''
            for page in pdf_reader.pages[:4]: # Primeiras 4 páginas
                texto += page.extract_text() + '\n'
            if len(texto.strip()) > 50:
                extracted_text = texto.strip()[:4000]
        except Exception:
            pass
            
    # Chamar IA localmente
    PROMPT = f"""Gere um nome de arquivo para este documento público brasileiro.
REGRAS: MAIÚSCULAS + números + underscore apenas. Sem espaços. Máximo 60 chars.
Formato: TIPO_DESCRICAO_DATA
Exemplos: SOLICITACAO_SERVICO_LAVAGEM_VEICULOS_2024, NOTA_FISCAL_EMPRESA_ABC_20240315
Responda SOMENTE com o nome, nada mais.

TEXTO:
{extracted_text}"""

    import sqlite3
    try:
        # Pega a chave da config ou db_config se houver (tentar ler do DB empenhos)
        conn = _db_connect()
        cur = conn.cursor()
        cur.execute("SELECT valor FROM configs WHERE chave = 'api_openrouter_key'")
        row = cur.fetchone()
        api_key = row['valor'] if row else ''
        cur.close()
        conn.close()
        
        if not api_key:
            send_message(chat_id, '⚠️ Chave da OpenRouter não está configurada no banco de dados. Configure o ADM primeiro.',
                         reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})
            return

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "meta-llama/llama-3.2-3b-instruct:free",
            "messages": [{"role": "user", "content": PROMPT}],
            "max_tokens": 100,
            "temperature": 0.2
        }
        
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=30)
        resp_json = resp.json()
        if not resp.ok or 'choices' not in resp_json:
            send_message(chat_id, f"❌ Falha na API IA: {resp_json}")
            return
            
        raw_name = resp_json['choices'][0]['message']['content'].strip()
        
        # Limpar regex do nome (tirar acentos, deixar_underscore)
        import re
        import unicodedata
        cleaned = unicodedata.normalize('NFD', raw_name).encode('ascii', 'ignore').decode("utf-8")
        cleaned = re.sub(r'[^A-Z0-9_\-]', '_', cleaned.upper())
        cleaned = re.sub(r'_+', '_', cleaned).strip('_')
        
        if len(cleaned) < 5: cleaned = file_name.replace('.pdf', '')
        
        ext = Path(file_name).suffix
        final_filename = cleaned[:70] + ext
        
        send_document(chat_id, content, f"✅ O arquivo foi renomeado e analisado.\n\n<b>Novo nome proposto:</b>\n<code>{final_filename}</code>", final_filename)
        
    except Exception as e:
        log.error(f"Erro no Rename IA: {e}")
        send_message(chat_id, f'❌ Erro interno ao renomear: {e}',
                     reply_markup={'inline_keyboard': [[{'text': '🔙 Menu', 'callback_data': 'cmd_menu'}]]})


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
