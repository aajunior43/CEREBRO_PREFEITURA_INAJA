# src/analyzers/detectors.py
import re
import uuid
import math
import numpy as np
import pandas as pd
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Tuple, Optional, Set
from .config import DEFAULT_CONFIG

CONFIG = DEFAULT_CONFIG

# Prefixos genéricos ignorados na identificação de beneficiários
BENE_IGNORE = {
    'PIX', 'TED', 'DOC', 'PAG', 'PAGAMENTO', 'TRANSF', 'TRANSFERENCIA',
    'CRED', 'DEB', 'ENVIO', 'RECEBIMENTO', 'PARA', 'PARA:', 'ENVIADO', 'RECEBIDO', 'ESTORNO', 'DEVOLUCAO'
}

def parse_date(d) -> datetime:
    """Converte string, datetime ou timestamp para datetime aware (UTC)."""
    if isinstance(d, datetime):
        if d.tzinfo is None:
            return d.replace(tzinfo=timezone.utc)
        return d
    if isinstance(d, date):
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    if isinstance(d, (int, float)):
        # Assume timestamp ms ou s
        if d > 1e11:  # ms
            d = d / 1000.0
        return datetime.fromtimestamp(d, tz=timezone.utc)
    if isinstance(d, str):
        # Tenta múltiplos formatos comuns
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(d, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(d.replace("Z", "+00:00"))
        except ValueError:
            pass
    raise ValueError(f"Não foi possível parsear a data: {d}")

def days_between(a, b) -> float:
    """Calcula a diferença em dias entre duas datas."""
    dt_a = parse_date(a)
    dt_b = parse_date(b)
    return abs((dt_b - dt_a).total_seconds()) / 86400.0

def fmt_brl(v: float) -> str:
    """Formata valor como moeda brasileira (ex: 1.234,56)."""
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def mk_alert(severity: str, category: str, icon: str, title: str, description: str,
             evidence: List[Dict[str, str]] = None, related_ids: List[str] = None) -> Dict[str, Any]:
    """Cria um dicionário padronizado para alertas."""
    return {
        "id": str(uuid.uuid4()),
        "severity": severity,
        "category": category,
        "icon": icon,
        "title": title,
        "description": description,
        "evidence": evidence or [],
        "relatedIds": related_ids or [],
    }

def is_aplic(t: Dict[str, Any]) -> bool:
    return bool(re.search(r"APLIC", t.get("memo", ""), re.IGNORECASE))

def is_resgate(t: Dict[str, Any]) -> bool:
    return bool(re.search(r"RESGATE AUTOM", t.get("memo", ""), re.IGNORECASE))

def tx_category(t: Dict[str, Any]) -> str:
    m = t.get("memo", "").upper()
    if "PIX" in m:
        return 'PIX'
    if "TED" in m:
        return 'TED'
    if "DOC" in m:
        return 'DOC'
    if "FATURA" in m:
        return 'FATURA'
    if any(k in m for k in ("TARIFA", "MANUTENCAO", "MANUT.")):
        return 'TARIFA'
    if any(k in m for k in ("ORDEM BANC", "REPASSE", "FNAS")):
        return 'OB'
    return 'OUTROS'

def dedup_window(t: Dict[str, Any]) -> int:
    m = t.get("memo", "").upper()
    if "PIX" in m or "TED" in m:
        return CONFIG["DEDUP_WINDOWS"]["PIX"]
    if "FATURA" in m:
        return CONFIG["DEDUP_WINDOWS"]["FATURA"]
    return CONFIG["DEDUP_WINDOWS"]["DEFAULT"]

def extract_pix_time(memo: str) -> Optional[str]:
    if not memo:
        return None
    # \d{2}/\d{2} \d{2}:\d{2}
    m = re.search(r"(\d{2}/\d{2})\s+(\d{2}:\d{2})", memo)
    if m:
        return f"{m.group(1)}|{m.group(2)}"
    # \b\d{2}:\d{2}:\d{2}\b
    m = re.search(r"\b(\d{2}:\d{2}):\d{2}\b", memo)
    if m:
        return m.group(1)
    # \b\d{2}:\d{2}\b
    m = re.search(r"\b(\d{2}:\d{2})\b", memo)
    if m:
        return m.group(1)
    return None

def normalize_beneficiary(memo: str) -> str:
    if not memo or not isinstance(memo, str):
        return 'Outros'

    # Remove acentos
    import unicodedata
    normalized = unicodedata.normalize("NFD", memo.upper())
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")

    # Extrai CPF/CNPJ
    cnpj_match = re.search(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}", normalized)
    if cnpj_match:
        return re.sub(r"\D", "", cnpj_match.group(0))
    
    cpf_match = re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", normalized)
    if cpf_match:
        return re.sub(r"\D", "", cpf_match.group(0))

    # Divide em tokens
    raw_tokens = re.split(r"[\s\-\/,.:]+", normalized)
    legal_suffixes = {'SA', 'LTDA', 'EIRELI', 'EPP', 'ME', 'SS', 'SERVICOS', 'COMERCIO'}
    prepositions = {'DE', 'DA', 'DO', 'DAS', 'DOS', 'E'}

    tokens = []
    for t in raw_tokens:
        t_clean = t.strip()
        if not t_clean:
            continue
        if t_clean in BENE_IGNORE:
            continue
        if t_clean in legal_suffixes:
            continue
        if t_clean in prepositions:
            continue
        if re.match(r"^\d+$", t_clean):
            continue
        if len(t_clean) <= 1:
            continue
        tokens.append(t_clean)

    if not tokens:
        return 'Outros'

    return " ".join(tokens)[:50].strip() or 'Outros'

def beneficiary_key(memo: str) -> str:
    return normalize_beneficiary(memo)

def tx_month(t: Dict[str, Any]) -> str:
    dt = parse_date(t["date"])
    return f"{dt.year}-{dt.month:02d}"

def mean_std(values: List[float]) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return mean, math.sqrt(variance)

def z_score(value: float, mean: float, std: float) -> float:
    return (value - mean) / std if std > 0 else 0.0

def levenshtein(a: str, b: str) -> int:
    m, n = len(a), len(b)
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        curr = [i]
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr.append(prev[j - 1])
            else:
                curr.append(1 + min(prev[j], curr[j - 1], prev[j - 1]))
        prev = curr
    return prev[n]

def memo_similarity(a: str, b: str) -> float:
    wa = keywords(a)
    wb = keywords(b)
    if not wa or not wb:
        return 0.0
    
    match_count = sum(1 for k in wa if any(k in r or r in k for r in wb))
    keyword_score = match_count / max(len(wa), len(wb))

    na = (a or "").upper().replace("  ", " ").strip()[:80]
    nb = (b or "").upper().replace("  ", " ").strip()[:80]
    max_len = max(len(na), len(nb))
    lev_score = 1.0 - levenshtein(na, nb) / max_len if max_len > 0 else 0.0

    return max(keyword_score, lev_score)

def keywords(memo: str) -> List[str]:
    if not memo:
        return []
    words = re.split(r"[\s\-\/,.:]+", memo.upper())
    return [w for w in words if len(w) > 2 and not re.match(r"^\d+$", w)]

def easter_date(year: int) -> datetime:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return datetime(year, month, day, tzinfo=timezone.utc)

_holiday_cache = {}

def brazilian_holidays(year: int) -> Dict[str, str]:
    if year in _holiday_cache:
        return _holiday_cache[year]
    
    holidays = {
        '01-01': 'Confraternização Universal',
        '04-21': 'Tiradentes',
        '05-01': 'Dia do Trabalho',
        '09-07': 'Independência',
        '10-12': 'Nossa Senhora Aparecida',
        '11-02': 'Finados',
        '11-15': 'Proclamação da República',
        '12-25': 'Natal',
    }
    
    easter = easter_date(year)
    def mmdd(dt: datetime) -> str:
        return f"{dt.month:02d}-{dt.day:02d}"
    
    holidays[mmdd(easter - pd.Timedelta(days=47))] = 'Carnaval (terça-feira)'
    holidays[mmdd(easter - pd.Timedelta(days=48))] = 'Carnaval (segunda-feira)'
    holidays[mmdd(easter - pd.Timedelta(days=2))] = 'Sexta-feira Santa'
    holidays[mmdd(easter + pd.Timedelta(days=60))] = 'Corpus Christi'
    
    _holiday_cache[year] = holidays
    return holidays

def national_holiday_name(dt_val) -> Optional[str]:
    dt = parse_date(dt_val)
    key = f"{dt.month:02d}-{dt.day:02d}"
    return brazilian_holidays(dt.year).get(key)

# --- Detectores ---

def detect_duplicates(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    debits = [t for t in txns if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t)]
    
    by_amount = {}
    for t in debits:
        key = f"{abs(t['amount']):.2f}"
        by_amount.setdefault(key, []).append(t)
        
    for group in by_amount.values():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                window = dedup_window(a)
                if days_between(a["date"], b["date"]) > window:
                    continue
                if memo_similarity(a["memo"], b["memo"]) < CONFIG["MEMO_SIM_DUPLICATE"]:
                    continue
                
                flagged.add(a["id"])
                flagged.add(b["id"])
                a.setdefault("flags", []).append('duplicate')
                b.setdefault("flags", []).append('duplicate')
                
                diff_days = days_between(a["date"], b["date"])
                alerts.append(mk_alert(
                    'critical',
                    'Pagamento Duplicado / Repetido',
                    '🔴',
                    f"Possível pagamento duplicado — R$ {fmt_brl(abs(a['amount']))}",
                    f"Dois débitos com mesmo valor e beneficiário similar em {diff_days:.0f} dia(s).",
                    [
                        {"label": "Transação 1", "value": f"{a.get('dateStr', '')} | {a['memo'][:70]}"},
                        {"label": "Transação 2", "value": f"{b.get('dateStr', '')} | {b['memo'][:70]}"},
                        {"label": "Valor", "value": f"R$ {fmt_brl(abs(a['amount']))}"}
                    ],
                    [a["id"], b["id"]]
                ))
    return alerts

def detect_returned_transfers(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    pattern = re.compile(r"DEVOLVIDA|DEVOLVIDO|DEVOL\.|ESTORNO|RESTITUICAO|RESTITUIÇÃO|DEVOLUCAO|DEVOLUÇÃO|RET\s*PIX", re.IGNORECASE)
    returns = [t for t in txns if t["amount"] > 0 and pattern.search(t.get("memo", ""))]
    
    for ret in returns:
        resend = None
        for t in txns:
            if t["amount"] < 0 and abs(abs(t["amount"]) - ret["amount"]) < 0.02:
                # Retorna >= ret e <= window
                if parse_date(t["date"]) >= parse_date(ret["date"]):
                    if days_between(ret["date"], t["date"]) <= CONFIG["RETURN_WINDOW_DAYS"]:
                        if not is_aplic(t) and not is_resgate(t):
                            resend = t
                            break
        
        if not resend:
            flagged.add(ret["id"])
            ret.setdefault("flags", []).append('returned_no_resend')
            alerts.append(mk_alert(
                'critical',
                'TED/PIX Devolvido sem Re-envio',
                '🔴',
                f"TED/PIX devolvido sem re-envio — R$ {fmt_brl(ret['amount'])}",
                f"Devolução recebida sem re-envio nos {CONFIG['RETURN_WINDOW_DAYS']} dias seguintes.",
                [
                    {"label": "Data", "value": ret.get("dateStr", "")},
                    {"label": "Valor", "value": f"R$ {fmt_brl(ret['amount'])}"},
                    {"label": "Memo", "value": ret.get("memo", "")}
                ],
                [ret["id"]]
            ))
        else:
            ret_kws = keywords(ret.get("memo", ""))
            res_kws = keywords(resend.get("memo", ""))
            overlap = [k for k in ret_kws if any(k in r or r in k for r in res_kws)]
            if not overlap:
                alerts.append(mk_alert(
                    'warning',
                    'TED Devolvida — Destino Diferente',
                    '🟡',
                    "TED re-enviada para destino aparentemente diferente",
                    "Beneficiário do re-envio diverge do original.",
                    [
                        {"label": "Devolução", "value": f"{ret.get('dateStr', '')} | {ret.get('memo', '')[:60]}"},
                        {"label": "Re-envio", "value": f"{resend.get('dateStr', '')} | {resend.get('memo', '')[:60]}"}
                    ],
                    [ret["id"], resend["id"]]
                ))
    return alerts

def adaptive_z_threshold(sample_size: int, cv: float) -> float:
    threshold = CONFIG["ATYPICAL_ZSCORE"]
    if sample_size < CONFIG["ATYPICAL_MIN_SAMPLE"] + 3:
        threshold += 0.5
    if cv < 0.15:
        threshold -= 0.3
    elif cv > 0.75:
        threshold += 0.3
    return threshold

def detect_atypical(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    debits = [t for t in txns if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t) and abs(t["amount"]) >= CONFIG["ATYPICAL_MIN_VALUE"]]
    if len(debits) < CONFIG["ATYPICAL_MIN_SAMPLE"]:
        return alerts

    by_category = {}
    for t in debits:
        cat = tx_category(t)
        by_category.setdefault(cat, []).append(t)

    for cat, group in by_category.items():
        if len(group) < CONFIG["ATYPICAL_MIN_SAMPLE"]:
            continue
        amts = [abs(t["amount"]) for t in group]
        mean, std = mean_std(amts)
        if std < 1.0:
            continue
        cv = std / mean if mean > 0 else 0.0
        z_thresh = adaptive_z_threshold(len(group), cv)
        
        for t in group:
            val = abs(t["amount"])
            z = z_score(val, mean, std)
            if z >= z_thresh:
                flagged.add(t["id"])
                t.setdefault("flags", []).append('atypical')
                alerts.append(mk_alert(
                    'warning',
                    'Movimentação Atípica — Valor Elevado',
                    '🟡',
                    f"Débito {cat} atípico: R$ {fmt_brl(val)} ({z:.1f}σ acima da média {cat})",
                    f"{z:.1f} desvios-padrão acima da média da categoria {cat} (R$ {fmt_brl(mean)}). Limiar adaptado para esta categoria: {z_thresh:.1f}σ (amostra de {len(group)}, variação relativa de {cv*100:.0f}%).",
                    [
                        {"label": "Data", "value": t.get("dateStr", "")},
                        {"label": "Valor", "value": f"R$ {fmt_brl(val)}"},
                        {"label": "Categoria", "value": cat},
                        {"label": "Média", "value": f"R$ {fmt_brl(mean)}"},
                        {"label": "Memo", "value": t.get("memo", "")[:80]}
                    ],
                    [t["id"]]
                ))
    return alerts

def detect_unapplied_funds(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    is_ob_pattern = re.compile(r"ORDEM\s*BANC|ORD\.?\s*BANC|OB\s+\d+|TRANSF\.?\s*GOV|FUNDO\s+A\s+FUNDO|FNAS|MDS|MINISTERIO|REPASSE", re.IGNORECASE)
    obs = [t for t in txns if t["amount"] > 0 and is_ob_pattern.search(t.get("memo", ""))]
    if not obs:
        return alerts
    aplicacoes = [t for t in txns if t["amount"] < 0 and is_aplic(t)]

    for dep in obs:
        matching_aplic = None
        for t in aplicacoes:
            diff_days = days_between(dep["date"], t["date"])
            is_close = abs(abs(t["amount"]) - dep["amount"]) < 0.05
            if is_close and parse_date(t["date"]) >= parse_date(dep["date"]) and diff_days <= CONFIG["MAX_UNAPPLIED_WINDOW_DAYS"]:
                matching_aplic = t
                break
        
        if matching_aplic:
            continue

        same_day_deps = [t for t in obs if days_between(dep["date"], t["date"]) <= 1]
        same_day_deps_total = sum(t["amount"] for t in same_day_deps)
        same_day_aplications = [t for t in aplicacoes if parse_date(t["date"]) >= parse_date(dep["date"]) and days_between(dep["date"], t["date"]) <= CONFIG["MAX_UNAPPLIED_WINDOW_DAYS"]]
        same_day_aplications_total = sum(abs(t["amount"]) for t in same_day_aplications)

        tolerance = max(0.10, same_day_deps_total * 0.01)
        if same_day_aplications_total >= same_day_deps_total - tolerance:
            continue

        flagged.add(dep["id"])
        dep.setdefault("flags", []).append('not_applied')
        alerts.append(mk_alert(
            'warning',
            'Recurso de Ordem Bancária Não Aplicado',
            '🟡',
            f"Repasse / OB sem aplicação correspondente: R$ {fmt_brl(dep['amount'])}",
            f"Recebimento de recurso público via OB/Repasse governamental sem aplicação financeira correspondente nos {CONFIG['MAX_UNAPPLIED_WINDOW_DAYS']} dias úteis subsequentes.",
            [
                {"label": "Data do Repasse", "value": dep.get("dateStr", "")},
                {"label": "Valor da OB", "value": f"R$ {fmt_brl(dep['amount'])}"},
                {"label": "Nomenclatura (Memo)", "value": dep.get("memo", "")},
                {"label": "Total Aplicado na Janela", "value": f"R$ {fmt_brl(same_day_aplications_total)}"}
            ],
            [dep["id"]]
        ))
    return alerts

def detect_unusual_rescues(txns: List[Dict[str, Any]], investments: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    for res in [t for t in txns if t["amount"] > 0 and is_resgate(t)]:
        payment = None
        for t in txns:
            if t["amount"] < 0 and not is_aplic(t):
                if abs(abs(t["amount"]) - res["amount"]) < 0.02 and t.get("dateStr") == res.get("dateStr"):
                    payment = t
                    break
        if not payment:
            alerts.append(mk_alert(
                'info',
                'Resgate sem Débito Correspondente',
                '🔵',
                f"Resgate automático sem débito no mesmo dia: R$ {fmt_brl(res['amount'])}",
                "Resgate do fundo sem pagamento/débito correspondente identificado.",
                [
                    {"label": "Data", "value": res.get("dateStr", "")},
                    {"label": "Valor", "value": f"R$ {fmt_brl(res['amount'])}"},
                    {"label": "Memo", "value": res.get("memo", "")}
                ],
                [res["id"]]
            ))
    return alerts

def detect_batch_pix(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    pix_sent = [t for t in txns if t["amount"] < 0 and re.search(r"PIX.*ENVIADO", t.get("memo", ""), re.IGNORECASE)]
    groups = {}
    for t in pix_sent:
        time_str = extract_pix_time(t.get("memo", ""))
        if not time_str:
            continue
        key = f"{t.get('dateStr')}|{time_str}"
        groups.setdefault(key, []).append(t)
        
    for key, group in groups.items():
        if len(group) >= 3:
            total = sum(abs(t["amount"]) for t in group)
            for t in group:
                flagged.add(t["id"])
                t.setdefault("flags", []).append('batch_pix')
            alerts.append(mk_alert(
                'warning',
                'Lote de PIX no Mesmo Momento',
                '🟡',
                f"{len(group)} PIXs enviados simultâneos — Total: R$ {fmt_brl(total)}",
                f"{len(group)} transferências PIX enviadas no mesmo instante para beneficiários diferentes. Verifique se é um pagamento em lote autorizado.",
                [{"label": f"PIX {idx+1}", "value": f"R$ {fmt_brl(abs(t['amount']))} → {t['memo'][:50]}"} for idx, t in enumerate(group)],
                [t["id"] for t in group]
            ))
    return alerts

def detect_ofx_vs_txt_mismatch(txns: List[Dict[str, Any]], investments: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    ofx_resgates = [t for t in txns if t["amount"] > 0 and is_resgate(t)]
    ofx_aplics = [t for t in txns if t["amount"] < 0 and is_aplic(t)]

    for inv in investments:
        month = inv.get("periodSort")  # "2025-11"
        if not month:
            continue
        
        # Resgates
        txt_resgate = inv.get("summary", {}).get("resgates", 0.0)
        if txt_resgate >= 0.01:
            ofx_resc_in_month = sum(t["amount"] for t in ofx_resgates if tx_month(t) == month)
            diff_r = abs(ofx_resc_in_month - txt_resgate)
            if diff_r > 0.10 and diff_r / txt_resgate > 0.05:
                alerts.append(mk_alert(
                    'warning',
                    'Divergência OFX vs Extrato TXT — Resgates',
                    '🟡',
                    f"Resgates divergem entre OFX e TXT — {inv.get('period')}",
                    f"OFX registra R$ {fmt_brl(ofx_resc_in_month)} em resgates, TXT mostra R$ {fmt_brl(txt_resgate)} (diferença de R$ {fmt_brl(diff_r)}).",
                    [
                        {"label": "Período", "value": inv.get("period", "")},
                        {"label": "Resgates OFX", "value": f"R$ {fmt_brl(ofx_resc_in_month)}"},
                        {"label": "Resgates TXT", "value": f"R$ {fmt_brl(txt_resgate)}"},
                        {"label": "Diferença", "value": f"R$ {fmt_brl(diff_r)}"}
                    ],
                    []
                ))

        # Aplicações
        txt_aplic = inv.get("summary", {}).get("aplicacoes", 0.0)
        if txt_aplic >= 0.01:
            ofx_aplic_in_month = sum(abs(t["amount"]) for t in ofx_aplics if tx_month(t) == month)
            diff_a = abs(ofx_aplic_in_month - txt_aplic)
            if diff_a > 0.10 and diff_a / txt_aplic > 0.05:
                alerts.append(mk_alert(
                    'warning',
                    'Divergência OFX vs Extrato TXT — Aplicações',
                    '🟡',
                    f"Aplicações divergem entre OFX e TXT — {inv.get('period')}",
                    f"OFX registra R$ {fmt_brl(ofx_aplic_in_month)} em aplicações, TXT mostra R$ {fmt_brl(txt_aplic)} (diferença de R$ {fmt_brl(diff_a)}).",
                    [
                        {"label": "Período", "value": inv.get("period", "")},
                        {"label": "Aplicações OFX", "value": f"R$ {fmt_brl(ofx_aplic_in_month)}"},
                        {"label": "Aplicações TXT", "value": f"R$ {fmt_brl(txt_aplic)}"},
                        {"label": "Diferença", "value": f"R$ {fmt_brl(diff_a)}"}
                    ],
                    []
                ))
    return alerts

def detect_round_amounts(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    debits = [t for t in txns if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t)]
    if not debits:
        return alerts

    sorted_amts = sorted([abs(t["amount"]) for t in debits])
    p90_idx = int(len(sorted_amts) * 0.9)
    p90 = sorted_amts[p90_idx] if sorted_amts else 0.0

    recurrence_map = {}
    for t in debits:
        abs_amt = abs(t["amount"])
        if abs(abs_amt % CONFIG["ROUND_AMOUNT_STEP"]) < 0.01:
            amt_key = f"{abs_amt:.2f}"
            bene = normalize_beneficiary(t.get("memo", ""))
            month = tx_month(t)
            key = f"{amt_key}|{bene}"
            recurrence_map.setdefault(key, set()).add(month)

    whitelist_pattern = CONFIG["ROUND_AMOUNT_WHITELIST_MEMO"]

    for t in debits:
        abs_amt = abs(t["amount"])
        if abs_amt < CONFIG["ROUND_AMOUNT_MIN"]:
            continue
        if abs(abs_amt % CONFIG["ROUND_AMOUNT_STEP"]) >= 0.01:
            continue
        if whitelist_pattern.search(t.get("memo", "")):
            continue
        if re.search(r"ORDEM BANC", t.get("memo", ""), re.IGNORECASE):
            continue

        amt_key = f"{abs_amt:.2f}"
        bene = normalize_beneficiary(t.get("memo", ""))
        key = f"{amt_key}|{bene}"
        if key in recurrence_map and len(recurrence_map[key]) >= 3:
            continue

        severity = 'warning' if abs_amt >= p90 else 'info'
        icon = '🟡' if severity == 'warning' else '🔵'

        flagged.add(t["id"])
        t.setdefault("flags", []).append('round_amount')
        alerts.append(mk_alert(
            severity,
            'Débito com Valor Exatamente Redondo',
            icon,
            f"Débito de valor redondo: R$ {fmt_brl(abs_amt)}",
            f"Transações com valores exatamente redondos (múltiplos de R$ {fmt_brl(CONFIG['ROUND_AMOUNT_STEP'])}) são atípicas em pagamentos reais. Verifique se foi autorizado.",
            [
                {"label": "Data", "value": t.get("dateStr", "")},
                {"label": "Valor", "value": f"R$ {fmt_brl(abs_amt)}"},
                {"label": "Memo", "value": t.get("memo", "")[:80]}
            ],
            [t["id"]]
        ))
    return alerts

def detect_missing_fnas_month(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    periods_raw = list({t["period"] for t in txns if t.get("period")})
    
    def parse_period(p):
        try:
            m, y = p.split('/')
            return int(y), int(m)
        except ValueError:
            return 0, 0
            
    periods = sorted(periods_raw, key=parse_period)
    if not periods:
        return alerts

    fnas_by_period = {}
    for p in periods:
        total = sum(t["amount"] for t in txns if t.get("period") == p and t["amount"] > 0 and re.search(r"ORDEM BANC|FNAS|FUNDO NACION", t.get("memo", ""), re.IGNORECASE))
        fnas_by_period[p] = total

    with_fnas = [v for v in fnas_by_period.values() if v > 0]
    if not with_fnas:
        return alerts
    avg_fnas, std_fnas = mean_std(with_fnas)
    cv_fnas = std_fnas / avg_fnas if avg_fnas > 0 else 0.0
    divergence_threshold = max(CONFIG["FNAS_DIVERGENCE_PCT"], cv_fnas * 2)

    for p in periods:
        amount = fnas_by_period[p]
        if not amount:
            alerts.append(mk_alert(
                'warning',
                'Mês sem Repasse do FNAS',
                '🟡',
                f"Nenhuma Ordem Bancária do FNAS em {p}",
                f"O período {p} não possui registro de repasse do FNAS. Verifique se foi bloqueado ou recebido em conta diferente.",
                [
                    {"label": "Período", "value": p},
                    {"label": "Status", "value": "Sem Ordem Bancária FNAS"}
                ],
                []
            ))
        elif avg_fnas > 0:
            month_num = p.split('/')[0]
            factor = CONFIG["FNAS_SEASONAL_MONTHS"].get(month_num)
            current_threshold = divergence_threshold
            is_adjusted = False
            if factor:
                multiplier = factor if factor > 1 else 1 / factor
                current_threshold = divergence_threshold * multiplier
                is_adjusted = True

            diff_ratio = abs(amount - avg_fnas) / avg_fnas
            if diff_ratio > current_threshold:
                variacao = ((amount - avg_fnas) / avg_fnas * 100)
                evidence = [
                    {"label": "Período", "value": p},
                    {"label": "Valor Recebido", "value": f"R$ {fmt_brl(amount)}"},
                    {"label": "Média Histórica", "value": f"R$ {fmt_brl(avg_fnas)}"},
                    {"label": "Variação", "value": f"{variacao:+.1f}%"},
                    {"label": "Limiar Adaptativo", "value": f"{current_threshold*100:.0f}%"}
                ]
                if is_adjusted:
                    evidence.append({"label": "Ajuste Sazonal", "value": "Mês de alta/baixa histórica — limiar ajustado"})

                alerts.append(mk_alert(
                    'warning',
                    'Repasse FNAS Divergente do Histórico',
                    '🟡',
                    f"FNAS de {p} diverge {variacao:+.1f}% da média histórica",
                    f"O valor recebido do FNAS (R$ {fmt_brl(amount)}) diverge {abs(variacao):.1f}% da média histórica (R$ {fmt_brl(avg_fnas)}), acima do limiar adaptativo de {current_threshold*100:.0f}% (calculado a partir da variação histórica de repasses). Verifique se houve bloqueio parcial ou repasse incorreto.",
                    evidence,
                    []
                ))
    return alerts

def detect_alternating_beneficiary(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    debits = [t for t in txns if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t)]
    by_amt = {}
    for t in debits:
        key = f"{abs(t['amount']):.2f}"
        by_amt.setdefault(key, []).append(t)

    for amt_str, group in by_amt.items():
        if len(group) < 6:
            continue
        unique_memos = list({normalize_beneficiary(t.get("memo", "")) for t in group})
        if len(unique_memos) >= 2 and len(unique_memos) <= len(group) / 2:
            sorted_group = sorted(group, key=lambda x: parse_date(x["date"]))
            memo_seq = [normalize_beneficiary(t.get("memo", "")) for t in sorted_group]
            switches = sum(1 for i in range(1, len(memo_seq)) if memo_seq[i] != memo_seq[i-1])
            if switches >= 2:
                for t in group:
                    flagged.add(t["id"])
                    t.setdefault("flags", []).append('alternating')
                
                evidence = [{"label": t.get("dateStr", ""), "value": t.get("memo", "")[:60]} for t in sorted_group[:6]]
                alerts.append(mk_alert(
                    'warning',
                    'Beneficiário Alternado Suspeito',
                    '🟡',
                    f"Mesmo valor R$ {fmt_brl(float(amt_str))} pago alternadamente para {len(unique_memos)} beneficiários diferentes",
                    "Padrão incomum: pagamentos do mesmo valor se alternam entre beneficiários diferentes a cada período. Pode indicar desvio em esquema de revezamento.",
                    evidence,
                    [t["id"] for t in group]
                ))
    return alerts

def detect_smurfing(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    alerted_ids = set()
    debits = [t for t in txns if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t)]

    grouped_by_bene = {}
    for t in debits:
        key = normalize_beneficiary(t.get("memo", ""))
        if not key or key == 'Outros':
            continue
        grouped_by_bene.setdefault(key, []).append(t)

    for bene, items in grouped_by_bene.items():
        if len(items) < CONFIG["SMURFING_MIN_ITEMS"]:
            continue
        items_sorted = sorted(items, key=lambda x: parse_date(x["date"]))

        for i in range(len(items_sorted) - 2):
            window_items = [items_sorted[i]]
            for j in range(i + 1, len(items_sorted)):
                if days_between(items_sorted[i]["date"], items_sorted[j]["date"]) <= CONFIG["SMURFING_WINDOW_DAYS"]:
                    window_items.append(items_sorted[j])
            if len(window_items) < CONFIG["SMURFING_MIN_ITEMS"]:
                continue

            if any(t["id"] in alerted_ids for t in window_items):
                continue

            amounts = [abs(t["amount"]) for t in window_items]
            total = sum(amounts)
            mean, std = mean_std(amounts)
            cv = std / mean if mean > 0 else 0.0
            span = days_between(window_items[0]["date"], window_items[-1]["date"])

            uniform_amounts = cv <= CONFIG["SMURFING_CV_THRESHOLD"]
            high_velocity = len(window_items) >= CONFIG["SMURFING_VELOCITY_COUNT"] and span <= CONFIG["SMURFING_VELOCITY_DAYS"]
            high_total = total > CONFIG["SMURFING_MIN_TOTAL"]

            if uniform_amounts or high_velocity or high_total:
                ids = [t["id"] for t in window_items]
                for tid in ids:
                    alerted_ids.add(tid)
                    flagged.add(tid)
                for t in window_items:
                    t.setdefault("flags", []).append('smurfing')

                reasons = []
                if uniform_amounts:
                    reasons.append(f"valores quase idênticos (variação de {cv*100:.1f}% entre eles)")
                if high_velocity:
                    reasons.append(f"{len(window_items)} pagamentos em {span:.0f} dia(s) — alta frequência")
                if high_total:
                    reasons.append(f"total acumulado de R$ {fmt_brl(total)} na janela")

                alerts.append(mk_alert(
                    'warning',
                    'Suspeita de Fracionamento (Smurfing)',
                    '🟡',
                    f"Fracionamento de pagamentos para {bene} — Total: R$ {fmt_brl(total)}",
                    f"Detectados {len(window_items)} pagamentos próximos em até {CONFIG['SMURFING_WINDOW_DAYS']} dias para o mesmo favorecido: {'; '.join(reasons)}. Pode indicar fracionamento de despesa para evasão de limites licitatórios.",
                    [{"label": f"Pagamento {idx+1} ({t.get('dateStr', '')})", "value": f"R$ {fmt_brl(abs(t['amount']))} — {t.get('memo', '')[:50]}"} for idx, t in enumerate(window_items)],
                    ids
                ))
    return alerts

def detect_cash_remnants(txns: List[Dict[str, Any]], investments: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    if not investments:
        return alerts

    resgates = [t for t in txns if t["amount"] > 0 and is_resgate(t)]
    processed = set()

    for res in resgates:
        day = res.get("dateStr")
        if not day or day in processed:
            continue
        processed.add(day)

        same_day_txns = [t for t in txns if t.get("dateStr") == day]
        res_date = parse_date(res["date"])
        next_day_txns = [t for t in txns if 0 < days_between(res["date"], t["date"]) <= 1]
        
        day_resgates_total = sum(t["amount"] for t in same_day_txns if t["amount"] > 0 and is_resgate(t))
        day_debits_total = sum(abs(t["amount"]) for t in same_day_txns if t["amount"] < 0 and not is_aplic(t)) + \
                           sum(abs(t["amount"]) for t in next_day_txns if t["amount"] < 0 and not is_aplic(t))

        surplus = day_resgates_total - day_debits_total
        if surplus > CONFIG["CASH_REMNANT_SURPLUS"]:
            alerts.append(mk_alert(
                'info',
                'Recurso Resgatado Ocioso',
                '🔵',
                f"Resgate com sobra ociosa em conta corrente — R$ {fmt_brl(surplus)}",
                f"No dia {day}, foi efetuado um resgate de R$ {fmt_brl(day_resgates_total)}, porém apenas R$ {fmt_brl(day_debits_total)} foram debitados (incluindo D+1). R$ {fmt_brl(surplus)} ficaram ociosos sem gerar rendimentos.",
                [
                    {"label": "Data", "value": day},
                    {"label": "Total Resgatado", "value": f"R$ {fmt_brl(day_resgates_total)}"},
                    {"label": "Total Utilizado", "value": f"R$ {fmt_brl(day_debits_total)}"},
                    {"label": "Sobra Ociosa", "value": f"R$ {fmt_brl(surplus)}"}
                ],
                [t["id"] for t in same_day_txns]
            ))
    return alerts

def detect_new_high_value_beneficiary(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    debits = [t for t in txns if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t)]
    if len(debits) < 4:
        return alerts
    
    amounts = sorted([abs(t["amount"]) for t in debits])
    p75 = amounts[int(len(amounts) * 0.75)]
    threshold = max(p75, 1000.0)
    seen = set()

    for t in txns:
        bene = normalize_beneficiary(t.get("memo", ""))
        if bene == 'Outros':
            continue
        if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t):
            amt = abs(t["amount"])
            if bene not in seen and amt >= threshold:
                flagged.add(t["id"])
                t.setdefault("flags", []).append('new_high_value_bene')
                alerts.append(mk_alert(
                    'warning',
                    'Novo Beneficiário de Alto Valor',
                    '🟡',
                    f"Primeiro pagamento de alto valor para {bene}: R$ {fmt_brl(amt)}",
                    f"Beneficiário \"{bene}\" recebe pela primeira vez um pagamento de R$ {fmt_brl(amt)}, acima do percentil 75% dos débitos da conta (R$ {fmt_brl(threshold)}).",
                    [
                        {"label": "Data", "value": t.get("dateStr", "")},
                        {"label": "Beneficiário", "value": bene},
                        {"label": "Valor", "value": f"R$ {fmt_brl(amt)}"},
                        {"label": "Limiar P75", "value": f"R$ {fmt_brl(threshold)}"}
                    ],
                    [t["id"]]
                ))
            seen.add(bene)
    return alerts

def detect_interrupted_recurring(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    debits = [t for t in txns if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t)]
    by_bene = {}
    for t in debits:
        key = normalize_beneficiary(t.get("memo", ""))
        if not key or key == 'Outros':
            continue
        by_bene.setdefault(key, []).append(t)

    all_months = sorted(list({tx_month(t) for t in txns if t.get("date")}))
    if len(all_months) < 3:
        return alerts
    latest_idx = len(all_months) - 1

    for bene, items in by_bene.items():
        if len(items) < 3:
            continue
        months = sorted(list({tx_month(t) for t in items}))
        if len(months) < 3:
            continue

        idxs = [all_months.index(m) for m in months if m in all_months]
        max_run = 1
        run = 1
        for i in range(1, len(idxs)):
            run = run + 1 if idxs[i] == idxs[i - 1] + 1 else 1
            if run > max_run:
                max_run = run
        
        if max_run < 3:
            continue

        last_month = months[-1]
        last_month_idx = all_months.index(last_month)
        gap = latest_idx - last_month_idx
        if gap >= 2:
            last_tx = sorted(items, key=lambda x: parse_date(x["date"]), reverse=True)[0]
            alerts.append(mk_alert(
                'info',
                'Pagamento Recorrente Interrompido',
                '🔵',
                f"Pagamento recorrente para {bene} ausente há {gap} mês(es)",
                f"O beneficiário \"{bene}\" recebia pagamentos por {len(months)} meses ({months[0]} a {last_month}) mas não recebeu nos últimos {gap} meses.",
                [
                    {"label": "Beneficiário", "value": bene},
                    {"label": "Última Ocorrência", "value": f"{last_tx.get('dateStr', '')} — R$ {fmt_brl(abs(last_tx['amount']))}"},
                    {"label": "Meses com Pag.", "value": f"{months[0]} → {last_month}"},
                    {"label": "Meses sem Pag.", "value": str(gap)}
                ],
                []
            ))
    return alerts

def detect_circular_transfers(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    alerted = set()
    debits = [t for t in txns if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t) and abs(t["amount"]) >= 500.0]
    credits = [t for t in txns if t["amount"] > 0 and not is_resgate(t) and not re.search(r"DEVOLVIDA|DEVOLVIDO|ESTORNO|RESTITUICAO", t.get("memo", ""), re.IGNORECASE)]

    for debit in debits:
        if debit["id"] in alerted:
            continue
        amt = abs(debit["amount"])
        debit_kws = [k for k in keywords(debit.get("memo", "")) if k not in BENE_IGNORE]
        if not debit_kws:
            continue
        
        for credit in credits:
            if credit["id"] in alerted:
                continue
            
            # diferença em dias
            days = (parse_date(credit["date"]) - parse_date(debit["date"])).total_seconds() / 86400.0
            if days < 1.0 or days > 30.0:
                continue
            
            if abs(credit["amount"] - amt) / amt > 0.03:
                continue
            
            credit_kws = [k for k in keywords(credit.get("memo", "")) if k not in BENE_IGNORE]
            overlap = [k for k in debit_kws if any(r == k or r in k or k in r for r in credit_kws)]
            if not overlap:
                continue

            flagged.add(debit["id"])
            flagged.add(credit["id"])
            debit.setdefault("flags", []).append('circular_transfer')
            credit.setdefault("flags", []).append('circular_transfer')
            alerted.add(debit["id"])
            alerted.add(credit["id"])

            alerts.append(mk_alert(
                'warning',
                'Suspeita de Transferência Circular',
                '🟡',
                f"Débito de R$ {fmt_brl(amt)} retorna em {round(days)} dia(s)",
                f"Transferência de R$ {fmt_brl(amt)} enviada em {debit.get('dateStr', '')} retorna como crédito em {credit.get('dateStr', '')} ({round(days)} dia(s)) para mesmo beneficiário. Pode indicar circularidade financeira suspeita.",
                [
                    {"label": "Débito", "value": f"{debit.get('dateStr', '')} — {debit.get('memo', '')[:60]}"},
                    {"label": "Crédito", "value": f"{credit.get('dateStr', '')} — {credit.get('memo', '')[:60]}"},
                    {"label": "Intervalo", "value": f"{round(days)} dia(s)"},
                    {"label": "Elo Comum", "value": ", ".join(overlap[:3])}
                ],
                [debit["id"], credit["id"]]
            ))
            break
    return alerts

def detect_bank_fee_anomaly(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    fees = [t for t in txns if t["amount"] < 0 and re.search(r"TARIFA|MANUTENCAO|MANUT\.|TAXA|ANUIDADE", t.get("memo", ""), re.IGNORECASE)]
    if len(fees) < 3:
        return alerts
    
    amounts = [abs(t["amount"]) for t in fees]
    mean, std = mean_std(amounts)
    if std < 0.01:
        return alerts
        
    for t in fees:
        amt = abs(t["amount"])
        z = z_score(amt, mean, std)
        if z >= CONFIG["ATYPICAL_ZSCORE"]:
            flagged.add(t["id"])
            t.setdefault("flags", []).append('fee_anomaly')
            alerts.append(mk_alert(
                'warning',
                'Tarifa Bancária Indevida / Atípica',
                '🟡',
                f"Tarifa atípica: R$ {fmt_brl(amt)} ({z:.1f}σ acima da média)",
                f"Cobrança de tarifa de R$ {fmt_brl(amt)} é {z:.1f} desvios-padrão acima da média histórica de R$ {fmt_brl(mean)}. Verifique se a cobrança foi autorizada.",
                [
                    {"label": "Data", "value": t.get("dateStr", "")},
                    {"label": "Valor", "value": f"R$ {fmt_brl(amt)}"},
                    {"label": "Média Histórica", "value": f"R$ {fmt_brl(mean)}"},
                    {"label": "Memo", "value": t.get("memo", "")[:80]}
                ],
                [t["id"]]
            ))
    return alerts

def detect_after_hours_payments(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    pix = [t for t in txns if t["amount"] < 0 and re.search(r"PIX", t.get("memo", ""), re.IGNORECASE) and abs(t["amount"]) >= CONFIG["AFTER_HOURS_MIN_VALUE"]]
    for t in pix:
        time_str = extract_pix_time(t.get("memo", ""))
        if not time_str:
            continue
        parts = time_str.split('|')
        hhmm = parts[-1]
        if not hhmm or ":" not in hhmm:
            continue
        try:
            hh = int(hhmm.split(':')[0])
        except ValueError:
            continue
        
        if hh < CONFIG["AFTER_HOURS_START_HOUR"] or hh >= CONFIG["AFTER_HOURS_END_HOUR"]:
            flagged.add(t["id"])
            t.setdefault("flags", []).append('after_hours')
            alerts.append(mk_alert(
                'info',
                'PIX Fora do Horário Comercial',
                '🔵',
                f"PIX de R$ {fmt_brl(abs(t['amount']))} enviado às {hhmm}",
                f"Transferência PIX efetuada fora do horário comercial ({hhmm}). Pagamentos noturnos merecem verificação adicional de autorização.",
                [
                    {"label": "Data", "value": t.get("dateStr", "")},
                    {"label": "Horário", "value": hhmm},
                    {"label": "Valor", "value": f"R$ {fmt_brl(abs(t['amount']))}"},
                    {"label": "Memo", "value": t.get("memo", "")[:80]}
                ],
                [t["id"]]
            ))
    return alerts

def detect_ofx_gaps(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    if len(txns) < 2:
        return alerts
    months = sorted(list({tx_month(t) for t in txns if t.get("date")}))
    if len(months) < 2:
        return alerts
        
    for i in range(len(months) - 1):
        y1, m1 = map(int, months[i].split('-'))
        y2, m2 = map(int, months[i + 1].split('-'))
        gap = (y2 * 12 + m2) - (y1 * 12 + m1)
        if gap > 1:
            missing = []
            for g in range(1, gap):
                total_months = y1 * 12 + (m1 - 1) + g
                yr = total_months // 12
                mo = (total_months % 12) + 1
                missing.append(f"{mo:02d}/{yr}")
            alerts.append(mk_alert(
                'warning',
                'Lacuna no Extrato OFX',
                '🟡',
                f"Extrato sem cobertura de {len(missing)} mês(es): {', '.join(missing)}",
                f"Detectada descontinuidade no extrato: após {months[i]} os dados retomam somente em {months[i+1]}, sem cobertura de {', '.join(missing)}.",
                [
                    {"label": "Mês Anterior", "value": months[i]},
                    {"label": "Próximo Mês", "value": months[i + 1]},
                    {"label": "Meses Faltando", "value": ", ".join(missing)}
                ],
                []
            ))
    return alerts

def detect_benford_deviation(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    debits = [t for t in txns if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t) and abs(t["amount"]) >= 1.0]
    if len(debits) < CONFIG["BENFORD_MIN_SAMPLE"]:
        return alerts

    expected_dist = [0.301, 0.176, 0.125, 0.097, 0.079, 0.067, 0.058, 0.051, 0.046]
    counts = [0] * 9
    for t in debits:
        digits = re.sub(r"[^1-9]", "", f"{abs(t['amount'])}")
        if digits:
            first_digit = int(digits[0])
            if 1 <= first_digit <= 9:
                counts[first_digit - 1] += 1
                
    n = sum(counts)
    if n < CONFIG["BENFORD_MIN_SAMPLE"]:
        return alerts

    chi2 = 0.0
    for i in range(9):
        expected = expected_dist[i] * n
        chi2 += (counts[i] - expected) ** 2 / expected

    if chi2 < CONFIG["BENFORD_CHI2_INFO"]:
        return alerts

    severity = 'warning' if chi2 >= CONFIG["BENFORD_CHI2_WARNING"] else 'info'
    icon = '🟡' if severity == 'warning' else '🔵'
    
    deviations = []
    for i in range(9):
        observed = counts[i] / n
        expected = expected_dist[i]
        diff = observed - expected
        deviations.append({"digit": i + 1, "observed": observed, "expected": expected, "diff": diff})
    
    deviations.sort(key=lambda x: abs(x["diff"]), reverse=True)
    evidence = [
        {"label": "Amostra", "value": f"{n} débitos"},
        {"label": "χ² (8 g.l.)", "value": f"{chi2:.2f}"}
    ]
    for d in deviations[:3]:
        evidence.append({
            "label": f"Dígito {d['digit']}",
            "value": f"observado {d['observed']*100:.1f}% vs esperado {d['expected']*100:.1f}%"
        })

    alerts.append(mk_alert(
        severity,
        'Desvio da Lei de Benford',
        icon,
        f"Distribuição de valores foge do padrão natural (χ² = {chi2:.1f})",
        f"O primeiro dígito dos {n} débitos da conta diverge significativamente da Lei de Benford (qui-quadrado {chi2:.1f}, limiar {severity.upper()} {CONFIG['BENFORD_CHI2_WARNING'] if severity == 'warning' else CONFIG['BENFORD_CHI2_INFO']}). Valores fabricados ou fracionados artificialmente costumam produzir esse desvio. Não é prova de fraude — é um indicador estatístico que merece amostragem manual.",
        evidence,
        []
    ))
    return alerts

def detect_weekend_payments(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    for t in txns:
        if t["amount"] >= 0 or is_aplic(t) or is_resgate(t):
            continue
        if abs(t["amount"]) < CONFIG["WEEKEND_MIN_VALUE"]:
            continue
        
        dt = parse_date(t["date"])
        # No JS: getUTCDay() (0=Sun, 6=Sat)
        # No Python: dt.weekday() (0=Mon, 6=Sun)
        # Portanto, Sat=5, Sun=6 no Python
        dow = dt.weekday()
        if dow in (5, 6):
            dow_str = "domingo" if dow == 6 else "sábado"
            flagged.add(t["id"])
            t.setdefault("flags", []).append('weekend_payment')
            alerts.append(mk_alert(
                'info',
                'Pagamento em Fim de Semana',
                '🔵',
                f"Débito de R$ {fmt_brl(abs(t['amount']))} em {dow_str}",
                f"Pagamento efetuado em {dow_str} ({t.get('dateStr', '')}). Contas públicas raramente movimentam em fins de semana — verifique se a operação foi autorizada.",
                [
                    {"label": "Data", "value": f"{t.get('dateStr', '')} ({dow_str})"},
                    {"label": "Valor", "value": f"R$ {fmt_brl(abs(t['amount']))}"},
                    {"label": "Memo", "value": t.get("memo", "")[:80]}
                ],
                [t["id"]]
            ))
    return alerts

def detect_holiday_payments(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    for t in txns:
        if t["amount"] >= 0 or is_aplic(t) or is_resgate(t):
            continue
        if abs(t["amount"]) < CONFIG["WEEKEND_MIN_VALUE"]:
            continue
        
        holiday = national_holiday_name(t["date"])
        if holiday:
            flagged.add(t["id"])
            t.setdefault("flags", []).append('holiday_payment')
            alerts.append(mk_alert(
                'info',
                'Pagamento em Feriado Nacional',
                '🔵',
                f"Débito de R$ {fmt_brl(abs(t['amount']))} em feriado ({holiday})",
                f"Pagamento efetuado em {t.get('dateStr', '')}, feriado nacional de {holiday}. Órgãos públicos não processam pagamentos em feriados — verifique a autorização.",
                [
                    {"label": "Data", "value": f"{t.get('dateStr', '')} ({holiday})"},
                    {"label": "Valor", "value": f"R$ {fmt_brl(abs(t['amount']))}"},
                    {"label": "Memo", "value": t.get("memo", "")[:80]}
                ],
                [t["id"]]
            ))
    return alerts

def detect_threshold_skirting(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    debits = [t for t in txns if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t)]
    for t in debits:
        amt = abs(t["amount"])
        for limit in CONFIG["PROCUREMENT_THRESHOLDS"]:
            floor = limit * (1.0 - CONFIG["PROCUREMENT_SKIRT_PCT"])
            if floor <= amt < limit:
                flagged.add(t["id"])
                t.setdefault("flags", []).append('threshold_skirting')
                alerts.append(mk_alert(
                    'warning',
                    'Valor Logo Abaixo de Limite Licitatório',
                    '🟡',
                    f"Débito de R$ {fmt_brl(amt)} a {(1.0 - amt / limit)*100:.1f}% do limite de R$ {fmt_brl(limit)}",
                    f"Pagamento de R$ {fmt_brl(amt)} fica imediatamente abaixo do limite de dispensa de licitação de R$ {fmt_brl(limit)}. Valores calibrados logo abaixo de limites legais podem indicar fuga ao processo licitatório.",
                    [
                        {"label": "Data", "value": t.get("dateStr", "")},
                        {"label": "Valor", "value": f"R$ {fmt_brl(amt)}"},
                        {"label": "Limite Próximo", "value": f"R$ {fmt_brl(limit)}"},
                        {"label": "Distância", "value": f"R$ {fmt_brl(limit - amt)} ({(1.0 - amt / limit)*100:.1f}%)"},
                        {"label": "Memo", "value": t.get("memo", "")[:80]}
                    ],
                    [t["id"]]
                ))
                break
    return alerts

def detect_dormant_account_burst(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    debits = sorted(
        [t for t in txns if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t)],
        key=lambda x: parse_date(x["date"])
    )
    if len(debits) < CONFIG["DORMANT_BURST_MIN_COUNT"] + 1:
        return alerts

    i = 1
    while i < len(debits):
        gap = days_between(debits[i - 1]["date"], debits[i]["date"])
        if gap < CONFIG["DORMANT_MIN_GAP_DAYS"]:
            i += 1
            continue

        burst = [debits[i]]
        for j in range(i + 1, len(debits)):
            if days_between(debits[i]["date"], debits[j]["date"]) <= CONFIG["DORMANT_BURST_DAYS"]:
                burst.append(debits[j])
            else:
                break

        total = sum(abs(t["amount"]) for t in burst)
        if len(burst) >= CONFIG["DORMANT_BURST_MIN_COUNT"] or total >= CONFIG["DORMANT_BURST_MIN_TOTAL"]:
            for t in burst:
                flagged.add(t["id"])
                t.setdefault("flags", []).append('dormant_burst')

            evidence = [
                {"label": "Período Dormente", "value": f"{debits[i - 1].get('dateStr', '')} → {debits[i].get('dateStr', '')} ({gap:.0f} dias)"},
                {"label": "Débitos na Rajada", "value": str(len(burst))},
                {"label": "Total da Rajada", "value": f"R$ {fmt_brl(total)}"}
            ]
            for idx, t in enumerate(burst[:4]):
                evidence.append({
                    "label": f"Pagamento {idx+1}",
                    "value": f"{t.get('dateStr', '')} — R$ {fmt_brl(abs(t['amount']))} — {t.get('memo', '')[:40]}"
                })

            alerts.append(mk_alert(
                'warning',
                'Rajada de Pagamentos após Dormência',
                '🟡',
                f"Conta parada há {gap:.0f} dias movimenta R$ {fmt_brl(total)} in {CONFIG['DORMANT_BURST_DAYS']} dias",
                f"Após {gap:.0f} dias sem débitos, a conta registrou {len(burst)} pagamento(s) somando R$ {fmt_brl(total)} em até {CONFIG['DORMANT_BURST_DAYS']} dias. Reativações abruptas merecem confirmação do gestor.",
                evidence,
                [t["id"] for t in burst]
            ))
            i += len(burst)
        else:
            i += 1
    return alerts

def detect_price_creep(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    debits = [t for t in txns if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t)]
    by_bene = {}
    for t in debits:
        bene = normalize_beneficiary(t.get("memo", ""))
        if not bene or bene == 'Outros':
            continue
        m = tx_month(t)
        by_bene.setdefault(bene, {}).setdefault(m, {"sum": 0.0, "count": 0, "txs": []})
        by_bene[bene][m]["sum"] += abs(t["amount"])
        by_bene[bene][m]["count"] += 1
        by_bene[bene][m]["txs"].append(t)

    for bene, months_data in by_bene.items():
        keys = sorted(months_data.keys())
        if len(keys) < CONFIG["CREEP_MIN_MONTHS"]:
            continue

        avgs = [months_data[k]["sum"] / months_data[k]["count"] for k in keys]
        overall_avg = sum(avgs) / len(avgs)
        if overall_avg < CONFIG["CREEP_MIN_AVG"]:
            continue

        n = len(avgs)
        x_mean = (n - 1) / 2.0
        y_mean = overall_avg
        num = 0.0
        den = 0.0
        for i in range(n):
            num += (i - x_mean) * (avgs[i] - y_mean)
            den += (i - x_mean) ** 2
        if den == 0:
            continue
        slope = num / den
        intercept = y_mean - slope * x_mean
        fit_start = intercept
        fit_end = intercept + slope * (n - 1)
        if fit_start <= 0:
            continue
        growth = (fit_end - fit_start) / fit_start
        if growth < CONFIG["CREEP_GROWTH_PCT"]:
            continue

        ids = []
        for k in keys:
            for t in months_data[k]["txs"]:
                ids.append(t["id"])
                flagged.add(t["id"])
                t.setdefault("flags", []).append('price_creep')

        alerts.append(mk_alert(
            'warning',
            'Aumento Gradual de Preços de Fornecedor',
            '🟡',
            f"{bene}: ticket médio cresceu {growth*100:.0f}% em {len(keys)} meses",
            f"O valor médio pago a \"{bene}\" apresenta tendência consistente de alta: de R$ {fmt_brl(fit_start)} para R$ {fmt_brl(fit_end)} ({growth*100:.0f}% acumulado em {len(keys)} meses). Aumentos progressivos podem indicar superfaturamento gradual — verifique reajustes contratuais.",
            [
                {"label": "Beneficiário", "value": bene},
                {"label": "Meses Analisados", "value": f"{keys[0]} → {keys[-1]} ({len(keys)})"},
                {"label": "Ticket Médio Inicial", "value": f"R$ {fmt_brl(avgs[0])}"},
                {"label": "Ticket Médio Final", "value": f"R$ {fmt_brl(avgs[-1])}"},
                {"label": "Crescimento (tendência)", "value": f"{growth*100:.1f}%"}
            ],
            ids
        ))
    return alerts

def detect_balance_mismatch(ofx_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    alerts = []
    if not ofx_files or len(ofx_files) < 2:
        return alerts

    def get_date(f, key):
        val = f.get(key)
        if not val:
            return datetime.min.replace(tzinfo=timezone.utc)
        return parse_date(val)

    usable = []
    for f in ofx_files:
        balance = f.get("ledgerBalance")
        if balance is not None and not math.isnan(balance):
            if f.get("dateEnd") or f.get("ledgerBalanceDate"):
                usable.append(f)

    usable.sort(key=lambda x: get_date(x, "dateEnd" if x.get("dateEnd") else "ledgerBalanceDate"))

    for i in range(len(usable) - 1):
        prev, next_file = usable[i], usable[i + 1]
        if not next_file.get("dateStart"):
            continue
        prev_end = get_date(prev, "dateEnd" if prev.get("dateEnd") else "ledgerBalanceDate")
        next_start = parse_date(next_file["dateStart"])
        gap_days = (next_start - prev_end).total_seconds() / 86400.0
        
        if gap_days < -1 or gap_days > CONFIG["BALANCE_MAX_GAP_DAYS"]:
            continue

        expected = prev["ledgerBalance"] + (next_file.get("txSum") or 0.0)
        diff = abs(expected - next_file["ledgerBalance"])
        if diff <= CONFIG["BALANCE_TOLERANCE"]:
            continue

        alerts.append(mk_alert(
            'critical',
            'Saldo OFX Não Concilia',
            '🔴',
            f"Extrato {next_file.get('period') or next_file.get('filename')}: diferença de R$ {fmt_brl(diff)} na conciliação",
            f"O saldo declarado no extrato anterior (R$ {fmt_brl(prev['ledgerBalance'])}) somado à movimentação do período (R$ {fmt_brl(next_file.get('txSum') or 0.0)}) deveria resultar em R$ {fmt_brl(expected)}, mas o extrato declara R$ {fmt_brl(next_file['ledgerBalance'])}. Indica transações suprimidas do arquivo ou saldo adulterado.",
            [
                {"label": "Extrato Anterior", "value": f"{prev.get('filename')} (saldo R$ {fmt_brl(prev['ledgerBalance'])})"},
                {"label": "Extrato Analisado", "value": next_file.get("filename", "")},
                {"label": "Movimentação do Período", "value": f"R$ {fmt_brl(next_file.get('txSum') or 0.0)} em {next_file.get('txCount') or 0} transações"},
                {"label": "Saldo Esperado", "value": f"R$ {fmt_brl(expected)}"},
                {"label": "Saldo Declarado", "value": f"R$ {fmt_brl(next_file['ledgerBalance'])}"},
                {"label": "Diferença", "value": f"R$ {fmt_brl(diff)}"}
            ],
            []
        ))
    return alerts

def detect_year_end_rush(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    debits = [t for t in txns if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t)]
    by_month = {}
    for t in debits:
        m = tx_month(t)
        by_month[m] = by_month.get(m, 0.0) + abs(t["amount"])

    months = sorted(by_month.keys())
    if len(months) < CONFIG["YEAR_END_MIN_MONTHS"]:
        return alerts

    for month in months:
        if not month.endswith('-12'):
            continue
        others = [by_month[m] for m in months if m != month]
        if len(others) < CONFIG["YEAR_END_MIN_MONTHS"] - 1:
            continue
        avg = sum(others) / len(others)
        if avg <= 0:
            continue
        ratio = by_month[month] / avg
        if ratio >= CONFIG["YEAR_END_RATIO"]:
            yr = month.split('-')[0]
            alerts.append(mk_alert(
                'warning',
                'Concentração de Gastos no Fim do Exercício',
                '🟡',
                f"Dezembro/{yr} gastou {ratio:.1f}x a média mensal",
                f"Os débitos de dezembro/{yr} (R$ {fmt_brl(by_month[month])}) superam em {ratio:.1f}x a média dos demais meses (R$ {fmt_brl(avg)}). Corridas de fim de exercício podem indicar empenhos apressados sem o devido processo.",
                [
                    {"label": "Dezembro", "value": f"R$ {fmt_brl(by_month[month])}"},
                    {"label": "Média Mensal", "value": f"R$ {fmt_brl(avg)}"},
                    {"label": "Razão", "value": f"{ratio:.1f}x"},
                    {"label": "Meses no Histórico", "value": str(len(months))}
                ],
                []
            ))
    return alerts

def detect_vendor_concentration(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    debits = [t for t in txns if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t)]
    if not debits:
        return alerts

    total_debits = sum(abs(t["amount"]) for t in debits)
    if total_debits == 0:
        return alerts

    by_bene = {}
    for t in debits:
        bene = normalize_beneficiary(t.get("memo", ""))
        if not bene or bene == 'Outros':
            continue
        by_bene.setdefault(bene, {"txs": [], "total": 0.0})
        by_bene[bene]["txs"].append(t)
        by_bene[bene]["total"] += abs(t["amount"])

    candidates = []
    for bene, info in by_bene.items():
        pct = info["total"] / total_debits
        candidates.append({
            "bene": bene,
            "total": info["total"],
            "pct": pct,
            "txs": info["txs"]
        })

    candidates.sort(key=lambda x: x["total"], reverse=True)

    alert_count = 0
    for c in candidates:
        if alert_count >= 3:
            break

        severity = None
        category = None
        icon = None

        if c["pct"] > 0.30 and c["total"] > 10000.0:
            severity = 'critical'
            category = 'Concentração de Pagamentos em Fornecedor Único'
            icon = '🔴'
        elif c["pct"] >= 0.15 and c["pct"] <= 0.30 and c["total"] > 5000.0:
            severity = 'warning'
            category = 'Fornecedor com Alta Concentração de Gastos'
            icon = '🟡'

        if severity:
            alert_count += 1
            ids = [t["id"] for t in c["txs"]]
            for tid in ids:
                flagged.add(tid)
            for t in c["txs"]:
                t.setdefault("flags", []).append('vendor_concentration')

            sorted_txs = sorted(c["txs"], key=lambda x: parse_date(x["date"]))
            start_period = sorted_txs[0].get("dateStr", "")
            end_period = sorted_txs[-1].get("dateStr", "")
            period_range = start_period if start_period == end_period else f"{start_period} a {end_period}"

            alerts.append(mk_alert(
                severity,
                category,
                icon,
                f"{category}: {c['bene']}",
                f"O beneficiário \"{c['bene']}\" concentra {c['pct']*100:.1f}% de todos os débitos da conta (total: R$ {fmt_brl(c['total'])}).",
                [
                    {"label": "Beneficiário", "value": c["bene"]},
                    {"label": "Total Recebido", "value": f"R$ {fmt_brl(c['total'])}"},
                    {"label": "Participação", "value": f"{c['pct']*100:.1f}% (Total da conta: R$ {fmt_brl(total_debits)})"},
                    {"label": "Número de Transações", "value": str(len(c["txs"]))},
                    {"label": "Período", "value": period_range}
                ],
                ids
            ))
    return alerts

RAPID_BURST_MIN_ITEMS = 4
RAPID_BURST_WINDOW_HOURS = 3
RAPID_BURST_MIN_TOTAL = 5000.0

def detect_rapid_debit_burst(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    alerted = set()
    debits = [t for t in txns if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t) and abs(t["amount"]) >= 200.0]

    for i in range(len(debits)):
        if debits[i]["id"] in alerted:
            continue
        base = debits[i]
        base_time = extract_pix_time(base.get("memo", ""))
        if not base_time:
            continue

        try:
            bhh, bmm = map(int, base_time.split('|')[-1].split(':'))
        except (ValueError, IndexError):
            continue
        base_minutes = bhh * 60 + bmm

        window = [base]
        for j in range(i + 1, len(debits)):
            other = debits[j]
            if other.get("dateStr") != base.get("dateStr"):
                break
            if other["id"] in alerted:
                continue
            other_time = extract_pix_time(other.get("memo", ""))
            if not other_time:
                continue
            try:
                ohh, omm = map(int, other_time.split('|')[-1].split(':'))
            except (ValueError, IndexError):
                continue
            other_minutes = ohh * 60 + omm
            if abs(other_minutes - base_minutes) <= RAPID_BURST_WINDOW_HOURS * 60:
                window.append(other)

        if len(window) < RAPID_BURST_MIN_ITEMS:
            continue
        total = sum(abs(t["amount"]) for t in window)
        if total < RAPID_BURST_MIN_TOTAL:
            continue

        for t in window:
            alerted.add(t["id"])
            flagged.add(t["id"])
            t.setdefault("flags", []).append('rapid_burst')

        evidence = [
            {"label": "Data", "value": base.get("dateStr", "")},
            {"label": "Período Detectado", "value": f"{RAPID_BURST_WINDOW_HOURS} horas"},
            {"label": "Nº de Débitos", "value": str(len(window))},
            {"label": "Total Movimentado", "value": f"R$ {fmt_brl(total)}"}
        ]
        for idx, t in enumerate(window[:4]):
            evidence.append({
                "label": f"Débito {idx+1}",
                "value": f"R$ {fmt_brl(abs(t['amount']))} — {t.get('memo', '')[:45]}"
            })

        alerts.append(mk_alert(
            'warning',
            'Rajada de Débitos em Curto Intervalo de Tempo',
            '🟡',
            f"{len(window)} débitos em {RAPID_BURST_WINDOW_HOURS}h — Total: R$ {fmt_brl(total)}",
            f"Detectados {len(window)} débitos em menos de {RAPID_BURST_WINDOW_HOURS} horas no dia {base.get('dateStr', '')}, somando R$ {fmt_brl(total)}. Pode indicar automação não autorizada ou sequência de pagamentos sem aprovação individual.",
            evidence,
            [t["id"] for t in window]
        ))
    return alerts

SEASONALITY_MIN_YEARS = 2
SEASONALITY_RATIO = 2.5

def detect_inverted_seasonality(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    debits = [t for t in txns if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t)]
    if not debits:
        return alerts

    by_month_year = {}
    for t in debits:
        dt = parse_date(t["date"])
        mm = f"{dt.month:02d}"
        yyyy = str(dt.year)
        by_month_year.setdefault(mm, {}).setdefault(yyyy, 0.0)
        by_month_year[mm][yyyy] += abs(t["amount"])

    for mm, year_map in by_month_year.items():
        years = sorted(year_map.keys())
        if len(years) < SEASONALITY_MIN_YEARS:
            continue

        latest_year = years[-1]
        prev_years = years[:-1]
        latest_val = year_map[latest_year]
        prev_avg = sum(year_map[y] for y in prev_years) / len(prev_years)
        if prev_avg < 500.0:
            continue

        ratio = latest_val / prev_avg
        month_names = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']
        month_name = month_names[int(mm) - 1]

        if ratio < 1.0 / SEASONALITY_RATIO:
            alerts.append(mk_alert(
                'info',
                'Sazonalidade Invertida — Gasto Anormalmente Baixo',
                '🔵',
                f"{month_name}/{latest_year} gastou {ratio*100:.0f}% do histórico do mesmo mês",
                f"O mês de {month_name}/{latest_year} apresentou apenas R$ {fmt_brl(latest_val)} in débitos, enquanto a média histórica para {month_name} era de R$ {fmt_brl(prev_avg)} ({ratio*100:.0f}% do histórico). Pode indicar bloqueio de verbas, não-utilização de recursos disponíveis ou reclassificação contábil.",
                [
                    {"label": "Mês Analisado", "value": f"{month_name}/{latest_year}"},
                    {"label": "Gasto Atual", "value": f"R$ {fmt_brl(latest_val)}"},
                    {"label": "Média Histórica do Mês", "value": f"R$ {fmt_brl(prev_avg)}"},
                    {"label": "Variação", "value": f"{ratio*100:.0f}% do histórico"},
                    {"label": "Anos de Histórico", "value": ", ".join(prev_years)}
                ],
                []
            ))
        elif ratio > SEASONALITY_RATIO:
            alerts.append(mk_alert(
                'warning',
                'Sazonalidade Invertida — Gasto Explosivo Atípico',
                '🟡',
                f"{month_name}/{latest_year} gastou {ratio:.1f}x o histórico do mesmo mês",
                f"O mês de {month_name}/{latest_year} apresentou R$ {fmt_brl(latest_val)} em débitos, {ratio:.1f}x acima da média histórica para {month_name} (R$ {fmt_brl(prev_avg)}). Gastos explosivos em meses historicamente moderados merecem verificação de autorização.",
                [
                    {"label": "Mês Analisado", "value": f"{month_name}/{latest_year}"},
                    {"label": "Gasto Atual", "value": f"R$ {fmt_brl(latest_val)}"},
                    {"label": "Média Histórica do Mês", "value": f"R$ {fmt_brl(prev_avg)}"},
                    {"label": "Multiplicador", "value": f"{ratio:.1f}x"},
                    {"label": "Anos de Histórico", "value": ", ".join(prev_years)}
                ],
                []
            ))
    return alerts

GENERIC_BENE_MIN_VALUE = 3000.0

def detect_generic_beneficiary(txns: List[Dict[str, Any]], flagged: Set[str]) -> List[Dict[str, Any]]:
    alerts = []
    debits = [t for t in txns if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t) and abs(t["amount"]) >= GENERIC_BENE_MIN_VALUE]

    for t in debits:
        bene = normalize_beneficiary(t.get("memo", ""))
        if bene != 'Outros':
            continue

        has_cpf_cnpj = bool(re.search(r"\d{11}|\d{14}|\d{3}\.\d{3}\.\d{3}-\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", t.get("memo", "")))
        if has_cpf_cnpj:
            continue

        flagged.add(t["id"])
        t.setdefault("flags", []).append('generic_beneficiary')
        alerts.append(mk_alert(
            'info',
            'Débito sem Beneficiário Identificável',
            '🔵',
            f"Débito de R$ {fmt_brl(abs(t['amount']))} sem destinatário claro",
            f"O memo desta transação não permite identificar o beneficiário real (\"{t.get('memo', '')[:60]}...\"). Débitos relevantes sem destinatário rastreável comprometem a transparência e a conciliação contábil.",
            [
                {"label": "Data", "value": t.get("dateStr", "")},
                {"label": "Valor", "value": f"R$ {fmt_brl(abs(t['amount']))}"},
                {"label": "Memo Completo", "value": t.get("memo", "")[:120]}
            ],
            [t["id"]]
        ))
    return alerts

def correlate_alerts(alerts: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    if not alerts:
        return {"alerts": [], "allAlerts": []}

    adj = [[] for _ in range(len(alerts))]
    for i in range(len(alerts)):
        a = alerts[i]
        a_set = set(a.get("relatedIds", []))
        if not a_set:
            continue
        for j in range(i + 1, len(alerts)):
            b = alerts[j]
            b_ids = b.get("relatedIds", [])
            if not b_ids:
                continue
            if any(tid in a_set for tid in b_ids):
                adj[i].append(j)
                adj[j].append(i)

    visited = set()
    groups = []

    for i in range(len(alerts)):
        if i in visited:
            continue
        component = []
        queue = [i]
        visited.add(i)
        while queue:
            curr = queue.pop(0)
            component.append(curr)
            for neighbor in adj[curr]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        groups.append([alerts[idx] for idx in component])

    severity_value = {"critical": 3, "warning": 2, "info": 1}

    for group in groups:
        if len(group) < 2:
            continue

        def sort_key(a):
            sev = severity_value.get(a.get("severity"), 0)
            ev_len = len(a.get("evidence", []))
            return (sev, ev_len)

        group.sort(key=sort_key, reverse=True)
        master = group[0]
        master.setdefault("correlatedWith", [])
        master.setdefault("evidence", [])

        for i in range(1, len(group)):
            discarded = group[i]
            discarded["mergedInto"] = master["id"]
            master["correlatedWith"].append(discarded["id"])
            master["evidence"].append({
                "label": "Também detectado",
                "value": f"{discarded['category']}: {discarded.get('title') or discarded.get('description')}"
            })

    non_merged = [a for a in alerts if "mergedInto" not in a]
    return {"alerts": non_merged, "allAlerts": alerts}

def build_stats(transactions: List[Dict[str, Any]], investments: List[Dict[str, Any]], alerts: List[Dict[str, Any]], all_alerts: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    if all_alerts is None:
        all_alerts = alerts

    invs = sorted(investments, key=lambda x: x.get("periodSort") or "")
    total_credits = sum(t["amount"] for t in transactions if t["amount"] > 0)
    total_debits = sum(abs(t["amount"]) for t in transactions if t["amount"] < 0)
    total_aplic = sum(abs(t["amount"]) for t in transactions if is_aplic(t))
    total_resgate = sum(t["amount"] for t in transactions if is_resgate(t))
    total_rendimento = sum(inv.get("summary", {}).get("rendBruto", 0.0) for inv in invs)
    last_inv = invs[-1] if invs else {}

    def parse_period(p):
        try:
            m, y = p.split('/')
            return int(y), int(m)
        except ValueError:
            return 0, 0

    periods = sorted(list({t["period"] for t in transactions if t.get("period")}), key=parse_period)

    # Top 10 beneficiários
    bene_map = {}
    for t in [t for t in transactions if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t)]:
        kw = normalize_beneficiary(t.get("memo", ""))
        bene_map.setdefault(kw, {"total": 0.0, "count": 0})
        bene_map[kw]["total"] += abs(t["amount"])
        bene_map[kw]["count"] += 1

    top_beneficiaries = sorted(
        [{"name": k, "total": v["total"], "count": v["count"]} for k, v in bene_map.items()],
        key=lambda x: x["total"],
        reverse=True
    )[:10]

    # Fluxo mensal
    monthly_flow = {}
    for t in transactions:
        dt = parse_date(t["date"])
        key = f"{dt.month:02d}/{dt.year}"
        monthly_flow.setdefault(key, {"in": 0.0, "out": 0.0, "aplic": 0.0, "resgate": 0.0, "balance": 0.0})
        if t["amount"] > 0 and is_resgate(t):
            monthly_flow[key]["resgate"] += t["amount"]
        elif t["amount"] < 0 and is_aplic(t):
            monthly_flow[key]["aplic"] += abs(t["amount"])
        elif t["amount"] > 0:
            monthly_flow[key]["in"] += t["amount"]
        else:
            monthly_flow[key]["out"] += abs(t["amount"])

    sorted_months = sorted(monthly_flow.keys(), key=parse_period)
    run_balance = 0.0
    for month in sorted_months:
        mf = monthly_flow[month]
        run_balance += (mf["in"] + mf["resgate"]) - (mf["out"] + mf["aplic"])
        mf["balance"] = run_balance

    # Daily balance
    daily_bal_map = {}
    for t in sorted(transactions, key=lambda x: parse_date(x["date"])):
        key = t.get("dateStr") or ""
        if key:
            daily_bal_map[key] = daily_bal_map.get(key, 0.0) + t["amount"]

    def parse_dmy(d):
        try:
            day, m, y = d.split('/')
            return int(y), int(m), int(day)
        except ValueError:
            return 0, 0, 0

    cum_bal = 0.0
    daily_balance = []
    for date_str in sorted(daily_bal_map.keys(), key=parse_dmy):
        cum_bal += daily_bal_map[date_str]
        daily_balance.append({"date": date_str, "balance": round(cum_bal, 2)})

    # Risk score
    tx_dates = []
    for t in transactions:
        try:
            tx_dates.append(parse_date(t["date"]).timestamp() * 1000)
        except Exception:
            pass
    latest_tx_date = max(tx_dates) if tx_dates else None
    tx_by_id = {t["id"]: t for t in transactions}

    def alert_recency_weight(alert):
        if latest_tx_date is None or not alert.get("relatedIds"):
            return 1.0
        most_recent = None
        for tid in alert["relatedIds"]:
            t = tx_by_id.get(tid)
            if not t:
                continue
            try:
                d = parse_date(t["date"]).timestamp() * 1000
                if most_recent is None or d > most_recent:
                    most_recent = d
            except Exception:
                pass
        if most_recent is None:
            return 1.0
        age_days = (latest_tx_date - most_recent) / 86400000.0
        return CONFIG["RISK_RECENT_BOOST"] if age_days <= CONFIG["RISK_RECENT_WINDOW_DAYS"] else CONFIG["RISK_STALE_DISCOUNT"]

    critical_score = 0.0
    warning_score = 0.0
    for a in alerts:
        w = alert_recency_weight(a)
        if a.get("severity") == "critical":
            critical_score += 25.0 * w
        elif a.get("severity") == "warning":
            warning_score += 10.0 * w
            
    flagged_count = sum(1 for t in transactions if t.get("flagged"))
    flagged_score = min(flagged_count * 3.0, 25.0)

    category_counts = {}
    for a in alerts:
        cat = a.get("category", "")
        category_counts[cat] = category_counts.get(cat, 0) + 1
    dominant_share = max(category_counts.values()) / len(alerts) if alerts else 0.0
    concentration_factor = CONFIG["RISK_CONCENTRATION_DISCOUNT"] if (len(alerts) >= CONFIG["RISK_CONCENTRATION_MIN_ALERTS"] and dominant_share >= CONFIG["RISK_CONCENTRATION_SHARE"]) else 1.0

    risk_score = min(100, round((critical_score + warning_score + flagged_score) * concentration_factor))

    # Weekday distribution (Mon=0, Sun=6)
    weekday_distribution = [0.0] * 7
    for t in [t for t in transactions if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t)]:
        dow = parse_date(t["date"]).weekday()
        weekday_distribution[dow] += abs(t["amount"])

    return {
        "totalTransactions": len(transactions),
        "totalCredits": total_credits,
        "totalDebits": total_debits,
        "totalAplic": total_aplic,
        "totalResgate": total_resgate,
        "totalRendimento": total_rendimento,
        "lastBalance": last_inv.get("summary", {}).get("saldoAtual", 0.0),
        "lastPeriod": last_inv.get("period", ""),
        "periods": periods,
        "totalAlerts": len(all_alerts),
        "totalAlertsNote": f"Total de alertas originais detectados antes da correlação e agrupamento de duplicidades (alertas deduplicados: {len(alerts)})",
        "criticalAlerts": sum(1 for a in alerts if a.get("severity") == "critical"),
        "warningAlerts": sum(1 for a in alerts if a.get("severity") == "warning"),
        "infoAlerts": sum(1 for a in alerts if a.get("severity") == "info"),
        "flaggedCount": flagged_count,
        "investmentCount": len(investments),
        "topBeneficiaries": top_beneficiaries,
        "monthlyFlow": monthly_flow,
        "dailyBalance": daily_balance,
        "riskScore": risk_score,
        "weekdayDistribution": weekday_distribution,
        "monthlyInvestments": [
            {
                "period": i.get("period", ""),
                "periodSort": i.get("periodSort", ""),
                "saldoAnterior": i.get("summary", {}).get("saldoAnterior", 0.0),
                "aplicacoes": i.get("summary", {}).get("aplicacoes", 0.0),
                "resgates": i.get("summary", {}).get("resgates", 0.0),
                "rendBruto": i.get("summary", {}).get("rendBruto", 0.0),
                "ir": i.get("summary", {}).get("ir", 0.0),
                "saldoAtual": i.get("summary", {}).get("saldoAtual", 0.0),
                "rentMonth": i.get("rentability", {}).get("month", 0.0),
                "rentYear": i.get("rentability", {}).get("year", 0.0),
                "rentY12": i.get("rentability", {}).get("y12", 0.0),
            } for i in invs
        ]
    }

def run_analysis(transactions: List[Dict[str, Any]], investments: List[Dict[str, Any]], custom_config: Dict[str, Any] = None, ofx_files: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    global CONFIG
    previous_config = CONFIG
    if custom_config:
        CONFIG = custom_config
    try:
        alerts = []
        flagged_ids = set()
        sorted_txns = sorted(transactions, key=lambda x: parse_date(x["date"]))

        alerts.extend(detect_duplicates(sorted_txns, flagged_ids))
        alerts.extend(detect_returned_transfers(sorted_txns, flagged_ids))
        alerts.extend(detect_atypical(sorted_txns, flagged_ids))
        alerts.extend(detect_unapplied_funds(sorted_txns, flagged_ids))
        alerts.extend(detect_unusual_rescues(sorted_txns, investments, flagged_ids))
        alerts.extend(detect_batch_pix(sorted_txns, flagged_ids))
        alerts.extend(detect_ofx_vs_txt_mismatch(sorted_txns, investments, flagged_ids))
        alerts.extend(detect_round_amounts(sorted_txns, flagged_ids))
        alerts.extend(detect_missing_fnas_month(sorted_txns, flagged_ids))
        alerts.extend(detect_alternating_beneficiary(sorted_txns, flagged_ids))
        alerts.extend(detect_smurfing(sorted_txns, flagged_ids))
        alerts.extend(detect_vendor_concentration(sorted_txns, flagged_ids))
        alerts.extend(detect_cash_remnants(sorted_txns, investments, flagged_ids))
        alerts.extend(detect_new_high_value_beneficiary(sorted_txns, flagged_ids))
        alerts.extend(detect_interrupted_recurring(sorted_txns, flagged_ids))
        alerts.extend(detect_circular_transfers(sorted_txns, flagged_ids))
        alerts.extend(detect_bank_fee_anomaly(sorted_txns, flagged_ids))
        alerts.extend(detect_after_hours_payments(sorted_txns, flagged_ids))
        alerts.extend(detect_ofx_gaps(sorted_txns, flagged_ids))
        alerts.extend(detect_benford_deviation(sorted_txns, flagged_ids))
        alerts.extend(detect_weekend_payments(sorted_txns, flagged_ids))
        alerts.extend(detect_holiday_payments(sorted_txns, flagged_ids))
        alerts.extend(detect_threshold_skirting(sorted_txns, flagged_ids))
        alerts.extend(detect_dormant_account_burst(sorted_txns, flagged_ids))
        alerts.extend(detect_year_end_rush(sorted_txns, flagged_ids))
        alerts.extend(detect_price_creep(sorted_txns, flagged_ids))
        if ofx_files:
            alerts.extend(detect_balance_mismatch(ofx_files))
        alerts.extend(detect_rapid_debit_burst(sorted_txns, flagged_ids))
        alerts.extend(detect_inverted_seasonality(sorted_txns, flagged_ids))
        alerts.extend(detect_generic_beneficiary(sorted_txns, flagged_ids))

        tx_by_id = {t["id"]: t for t in transactions}
        for fid in flagged_ids:
            t = tx_by_id.get(fid)
            if t:
                t["flagged"] = True

        correlation = correlate_alerts(alerts)
        stats = build_stats(transactions, investments, correlation["alerts"], correlation["allAlerts"])
        return {
            "alerts": correlation["alerts"],
            "allAlerts": correlation["allAlerts"],
            "flaggedIds": list(flagged_ids),
            "stats": stats
        }
    finally:
        CONFIG = previous_config

def run_cross_account_analysis(account_results: List[Dict[str, Any]]):
    if not account_results or len(account_results) < 2:
        return

    cross_alerts_by_account = {}
    for res in account_results:
        acc = res.get("account")
        if acc and acc.get("id"):
            cross_alerts_by_account[acc["id"]] = []

    def get_day_diff(str_a, str_b):
        if not str_a or not str_b:
            return float("nan")
        try:
            dA, mA, yA = map(int, str_a.split('/'))
            dB, mB, yB = map(int, str_b.split('/'))
            date_a = datetime(yA, mA, dA)
            date_b = datetime(yB, mB, dB)
            return (date_b - date_a).total_seconds() / 86400.0
        except Exception:
            return float("nan")

    for i in range(len(account_results)):
        res_x = account_results[i]
        acc_x = res_x.get("account")
        if not acc_x:
            continue
        clean_acc_x = re.sub(r"\D", "", acc_x.get("number", ""))
        raw_acc_x = acc_x.get("number", "").upper()

        debits_x = [t for t in res_x.get("transactions", []) if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t)]

        for j in range(len(account_results)):
            if i == j:
                continue
            res_y = account_results[j]
            acc_y = res_y.get("account")
            if not acc_y:
                continue
            clean_acc_y = re.sub(r"\D", "", acc_y.get("number", ""))
            raw_acc_y = acc_y.get("number", "").upper()

            credits_y = [t for t in res_y.get("transactions", []) if t["amount"] > 0 and not is_resgate(t)]

            for tx_x in debits_x:
                val_x = abs(tx_x["amount"])

                for tx_y in credits_y:
                    val_y = tx_y["amount"]
                    diff_pct = abs(val_x - val_y) / val_x
                    if diff_pct > 0.01:
                        continue

                    date_diff = get_day_diff(tx_x.get("dateStr"), tx_y.get("dateStr"))
                    if date_diff != 0.0 and date_diff != 1.0:
                        continue

                    memo_x = (tx_x.get("memo") or "").upper()
                    memo_y = (tx_y.get("memo") or "").upper()

                    contains_acc = (
                        (len(clean_acc_x) > 2 and (clean_acc_x in memo_x or clean_acc_x in memo_y)) or
                        (len(clean_acc_y) > 2 and (clean_acc_y in memo_x or clean_acc_y in memo_y)) or
                        raw_acc_x in memo_x or raw_acc_x in memo_y or
                        raw_acc_y in memo_x or raw_acc_y in memo_y
                    )

                    if contains_acc:
                        alert_data = {
                            "severity": 'critical',
                            "category": 'Transferência Entre Contas Municipais',
                            "icon": '🔴',
                            "title": f"Transf. entre contas: R$ {fmt_brl(val_x)}",
                            "description": f"Identificada possível transferência entre as contas municipais {acc_x.get('number')} e {acc_y.get('number')} no mesmo dia ou D+1.",
                            "evidence": [
                                {"label": 'Conta Origem', "value": acc_x.get("number", "")},
                                {"label": 'Conta Destino', "value": acc_y.get("number", "")},
                                {"label": 'Débito (Origem)', "value": f"{tx_x.get('dateStr')} | R$ {fmt_brl(val_x)} | {tx_x.get('memo')}"},
                                {"label": 'Crédito (Destino)', "value": f"{tx_y.get('dateStr')} | R$ {fmt_brl(val_y)} | {tx_y.get('memo')}"}
                            ],
                            "relatedIds": [tx_x["id"], tx_y["id"]],
                            "crossAccount": True
                        }

                        if acc_x.get("id") in cross_alerts_by_account:
                            cross_alerts_by_account[acc_x["id"]].append({**alert_data, "id": str(uuid.uuid4())})
                        if acc_y.get("id") in cross_alerts_by_account:
                            cross_alerts_by_account[acc_y["id"]].append({**alert_data, "id": str(uuid.uuid4())})

    # Detector 19b: Mesmo beneficiário em múltiplas contas
    bene_accounts = {}
    def get_p50(amounts):
        if not amounts:
            return 0.0
        sorted_amts = sorted(amounts)
        mid = len(sorted_amts) // 2
        return sorted_amts[mid] if len(sorted_amts) % 2 != 0 else (sorted_amts[mid - 1] + sorted_amts[mid]) / 2.0

    for res in account_results:
        acc = res.get("account")
        if not acc:
            continue
        debits = [t for t in res.get("transactions", []) if t["amount"] < 0 and not is_aplic(t) and not is_resgate(t)]
        p50 = get_p50([abs(t["amount"]) for t in debits])

        for t in debits:
            val = abs(t["amount"])
            if val > p50:
                bene = normalize_beneficiary(t.get("memo", ""))
                if bene and bene != 'Outros':
                    acc_num = acc.get("number")
                    bene_accounts.setdefault(bene, {})
                    bene_accounts[bene].setdefault(acc_num, {"accId": acc.get("id"), "txs": []})
                    bene_accounts[bene][acc_num]["txs"].append(t)

    for bene, acc_map in bene_accounts.items():
        if len(acc_map) >= 3:
            acc_list = list(acc_map.keys())
            alert_data = {
                "severity": 'warning',
                "category": 'Fornecedor Comum a Múltiplas Contas — Risco de Concentração',
                "icon": '🟡',
                "title": f"Risco de concentração: {bene}",
                "description": f"O beneficiário \"{bene}\" recebeu pagamentos significativos (acima da mediana P50) em {len(acc_map)} contas diferentes do município.",
                "evidence": [
                    {"label": 'Beneficiário', "value": bene},
                    {"label": 'Contas Envolvidas', "value": ", ".join(acc_list)}
                ],
                "relatedIds": [],
                "crossAccount": True
            }

            for acc_num, details in acc_map.items():
                acc_alert = {
                    **alert_data,
                    "id": str(uuid.uuid4()),
                    "relatedIds": [t["id"] for t in details["txs"]]
                }
                acc_id = details["accId"]
                if acc_id in cross_alerts_by_account:
                    cross_alerts_by_account[acc_id].append(acc_alert)

    # Push new alerts
    for res in account_results:
        acc = res.get("account")
        if not acc or not acc.get("id"):
            continue
        new_alerts = cross_alerts_by_account.get(acc["id"], [])
        if new_alerts:
            res.setdefault("alerts", []).extend(new_alerts)
            stats = res.setdefault("stats", {})
            for a in new_alerts:
                severity = a.get("severity")
                if severity == "critical":
                    stats["criticalAlerts"] = stats.get("criticalAlerts", 0) + 1
                elif severity == "warning":
                    stats["warningAlerts"] = stats.get("warningAlerts", 0) + 1
                elif severity == "info":
                    stats["infoAlerts"] = stats.get("infoAlerts", 0) + 1
                stats["totalAlerts"] = stats.get("totalAlerts", 0) + 1
