# ════════════════════════════════════════════════════════════════════════════
from datetime import date, timedelta

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
