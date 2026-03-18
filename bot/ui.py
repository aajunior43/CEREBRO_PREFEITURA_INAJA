from telegram import InlineKeyboardButton, InlineKeyboardMarkup

STATUS_EMOJI  = {'todo': '📋', 'in-progress': '⚡', 'done': '✅'}
STATUS_LABEL  = {'todo': 'A Fazer', 'in-progress': 'Em Progresso', 'done': 'Concluído'}
PRIO_EMOJI    = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}
PRIO_LABEL    = {'high': 'Alta', 'medium': 'Média', 'low': 'Baixa'}

# ==============================================================================
# KEYBOARDS
# ==============================================================================
def keyboard_main() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton('— 📋 GESTÃO KANBAN —', callback_data='ignore')],
        [
            InlineKeyboardButton('➕ Nova Tarefa', callback_data='cmd_nova_tarefa'),
            InlineKeyboardButton('🔍 Ver Tarefas', callback_data='cmd_ver_tarefas'),
        ],
        [InlineKeyboardButton('— 💰 FINANCEIRO & DESPESAS —', callback_data='ignore')],
        [
            InlineKeyboardButton('📊 Painel Mensal', callback_data='cmd_financeiro'),
            InlineKeyboardButton('🔎 Consultar', callback_data='cmd_buscar_despesas'),
        ],
        [
            InlineKeyboardButton('📅 Calendário de Pagamentos', callback_data='cmd_calendario'),
        ],
        [InlineKeyboardButton('— 📝 PROTOCOLOS E PROCESSOS —', callback_data='ignore')],
        [
            InlineKeyboardButton('🔎 Buscar Protocolo/Ofício', callback_data='cmd_buscar_protocolos'),
        ],
        [
            InlineKeyboardButton('📄 Gerar Empenho', callback_data='cmd_gerar_empenho'),
            InlineKeyboardButton('💼 Gerar RPA', callback_data='cmd_gerar_rpa'),
        ],
        [InlineKeyboardButton('— 🛒 SERVIÇOS & CONSULTAS —', callback_data='ignore')],
        [
            InlineKeyboardButton('🛒 Nova Aquisição', callback_data='cmd_nova_aquisicao'),
            InlineKeyboardButton('✈️ Calc. Diárias', callback_data='cmd_calc_diarias'),
        ],
        [
            InlineKeyboardButton('🏢 Consultar CNPJ', callback_data='cmd_consulta_cnpj'),
            InlineKeyboardButton('⏰ Calc. Prazos', callback_data='cmd_calc_prazos'),
        ],
        [InlineKeyboardButton('— 🛠️ FERRAMENTAS IA —', callback_data='ignore')],
        [
            InlineKeyboardButton('📄 Extrair PDF', callback_data='cmd_extrator_pdf'),
            InlineKeyboardButton('✨ Renomear Arq.', callback_data='cmd_renomear_arquivo'),
        ],
        [
            InlineKeyboardButton('🔍 Auditor NF', callback_data='cmd_auditor_nf'),
            InlineKeyboardButton('🏦 Extrato Bancário', callback_data='cmd_extrato_bancario'),
        ],
        [
            InlineKeyboardButton('📝 Resumir Doc.', callback_data='cmd_resumir'),
            InlineKeyboardButton('✍️ Minuta', callback_data='cmd_minuta'),
        ],
        [
            InlineKeyboardButton('📊 Relatório Mensal', callback_data='cmd_relatorio'),
            InlineKeyboardButton('🗒 Log Atividades', callback_data='cmd_log'),
        ],
        [InlineKeyboardButton('🔄 Atualizar Menu', callback_data='cmd_menu')],
    ]
    return InlineKeyboardMarkup(keyboard)

def keyboard_status() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton('📋 A Fazer', callback_data='status_todo'),
            InlineKeyboardButton('⚡ Em Progresso', callback_data='status_in-progress'),
        ],
        [
            InlineKeyboardButton('✅ Concluído', callback_data='status_done'),
        ],
        [InlineKeyboardButton('❌ Cancelar', callback_data='cmd_cancelar')],
    ])

def keyboard_priority() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton('🔴 Alta', callback_data='prio_high'),
            InlineKeyboardButton('🟡 Média', callback_data='prio_medium'),
            InlineKeyboardButton('🟢 Baixa', callback_data='prio_low'),
        ],
        [InlineKeyboardButton('❌ Cancelar', callback_data='cmd_cancelar')],
    ])

def keyboard_skip_or_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton('⏭ Pular descrição', callback_data='desc_skip'),
            InlineKeyboardButton('❌ Cancelar', callback_data='cmd_cancelar'),
        ]
    ])

def keyboard_financeiro(ano: int, mes: int) -> InlineKeyboardMarkup:
    mes_ant = mes - 1 if mes > 1 else 12
    ano_ant = ano if mes > 1 else ano - 1
    mes_prox = mes + 1 if mes < 12 else 1
    ano_prox = ano if mes < 12 else ano + 1
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton('⬅ Mês Anterior', callback_data=f'fin_{ano_ant}_{mes_ant}'),
            InlineKeyboardButton('➡ Próximo Mês', callback_data=f'fin_{ano_prox}_{mes_prox}'),
        ],
        [
            InlineKeyboardButton('📋 Empenhados', callback_data=f'fin_emp_{ano}_{mes}'),
            InlineKeyboardButton('⏳ Pendentes', callback_data=f'fin_pend_{ano}_{mes}'),
        ],
        [InlineKeyboardButton('🔙 Menu', callback_data='cmd_menu')],
    ])

# ==============================================================================
# FORMATTERS
# ==============================================================================

def menu_text(todo: int, prog: int, done: int) -> str:
    return (
        f'🏛 <b>Prefeitura de Inajá — Kanban</b>\n\n'
        f'📋 A Fazer: <b>{todo}</b>  ⚡ Em Progresso: <b>{prog}</b>  ✅ Concluídas: <b>{done}</b>\n\n'
        f'Escolha uma opção:'
    )

def format_task_created(task: dict) -> str:
    s  = task.get('status', 'todo')
    p  = task.get('priority', 'medium')
    desc = task.get("description", "")
    return (
        f'✅ <b>Tarefa criada com sucesso!</b>\n\n'
        f'📝 <b>Título:</b> {task.get("title")}\n'
        f'{("📄 <b>Descrição:</b> " + desc[:100] + chr(10)) if desc else ""}'
        f'{STATUS_EMOJI.get(s, "📋")} <b>Status:</b> {STATUS_LABEL.get(s, s)}\n'
        f'{PRIO_EMOJI.get(p, "🟡")} <b>Prioridade:</b> {PRIO_LABEL.get(p, p)}\n\n'
        f'<i>Acesse o sistema para ver no Kanban.</i>'
    )

def _format_task_item(t: dict, show_status: bool = False) -> str:
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

def format_task_list(tasks: list, title: str, grouped: bool = False) -> str:
    if not tasks:
        return f'<b>{title}</b>\n\n<i>Nenhuma tarefa encontrada.</i>'

    if not grouped:
        lines = [f'<b>{title}</b>  <code>{len(tasks)}</code>\n']
        for t in tasks[:25]:
            lines.append(_format_task_item(t))
        if len(tasks) > 25:
            lines.append(f'\n<i>… e mais {len(tasks) - 25} tarefas</i>')
        return '\n'.join(lines)

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
        lines.append('')

    if not has_any:
        return f'<b>{title}</b>\n\n<i>Nenhuma tarefa encontrada.</i>'

    total = len(tasks)
    lines.append(f'<i>Total: {total} tarefa{"s" if total != 1 else ""}</i>')
    return '\n'.join(lines)
