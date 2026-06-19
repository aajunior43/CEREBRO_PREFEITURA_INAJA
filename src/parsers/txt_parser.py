"""
ExpertMoney Analyzer — TXT Parser (BB RF Curto Prazo Automático)
Equivalente a: src/parsers/txtParser.js

Lê arquivos de extrato de aplicação financeira do Banco do Brasil,
decodificados em windows-1252, e retorna estrutura padronizada.
"""
import re
import unicodedata
from typing import Optional

# ── Mapa de meses português → número ──────────────────────────────────────────
MONTH_MAP = {
    # Janeiro
    "JANEIRO": 1, "JANIERO": 1,
    # Fevereiro
    "FEVEREIRO": 2, "FEVERIRO": 2,
    # Março — cobre todas as grafias possíveis do BB (com e sem acento)
    "MARCO": 3, "MARÇO": 3,
    # Abril
    "ABRIL": 4,
    # Maio
    "MAIO": 5,
    # Junho
    "JUNHO": 6,
    # Julho
    "JULHO": 7,
    # Agosto
    "AGOSTO": 8,
    # Setembro
    "SETEMBRO": 9,
    # Outubro
    "OUTUBRO": 10,
    # Novembro
    "NOVEMBRO": 11,
    # Dezembro
    "DEZEMBRO": 12,
}

# ── Helpers internos ──────────────────────────────────────────────────────────

def _extract_brl_number(line: str) -> Optional[float]:
    """
    Extrai o primeiro número no formato BRL (1.234,56) de uma linha.
    Equivalente a extractBRLNumber do JS.
    """
    m = re.search(r"([\d.]+,\d{2})", line)
    if not m:
        return None
    return float(m.group(1).replace(".", "").replace(",", "."))


def _extract_decimal(line: str) -> Optional[float]:
    """
    Extrai decimal com vírgula ou ponto (ex: rentabilidade 1,23%).
    Equivalente a extractDecimal do JS.
    """
    m = re.search(r"(-?[\d]+[,.][\d]+)", line)
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def _normalize_period(period: str) -> str:
    """
    Converte período textual em chave sortável YYYY-MM.
    Ex: "JANEIRO/2025" → "2025-01", "MARÇO/2024" → "2024-03"
    Equivalente a normalizePeriod do JS.
    """
    # Normaliza para maiúsculas e remove diacríticos (acentos)
    normalized = unicodedata.normalize("NFD", period.upper())
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    normalized = normalized.strip()

    parts = normalized.split("/")
    month_num = MONTH_MAP.get(parts[0].strip() if parts else "", 0)
    year = int(parts[1]) if len(parts) > 1 and parts[1].strip().isdigit() else 0
    return f"{year}-{str(month_num).zfill(2)}"


# ── API pública ───────────────────────────────────────────────────────────────

def parse_txt(buffer: bytes, filename: str) -> Optional[dict]:
    """
    Parseia um arquivo TXT de extrato de aplicação financeira Banco do Brasil.

    Retorna None se o arquivo não for reconhecido como extrato de investimento
    (ausência do campo 'Mês/ano referência').

    Retorna estrutura:
    {
      filename, period, periodSort, account, fund, cnpjFund,
      items, summary, rentability, quotaValues
    }

    Equivalente a parseTXT do Node.js.
    """
    text = buffer.decode("windows-1252", errors="replace")
    lines = text.splitlines()

    inv = {
        "filename":   filename,
        "period":     "",
        "periodSort": "",
        "account":    "",
        "fund":       "BB RF Curto Prazo Automatico",
        "cnpjFund":   "",
        "items":      [],
        "summary": {
            "saldoAnterior": 0.0,
            "aplicacoes":    0.0,
            "resgates":      0.0,
            "rendBruto":     0.0,
            "ir":            0.0,
            "iof":           0.0,
            "rendLiquido":   0.0,
            "saldoAtual":    0.0,
        },
        "rentability": {
            "month": 0.0,
            "year":  0.0,
            "y12":   0.0,
        },
        "quotaValues": [],
    }

    # ── Período ───────────────────────────────────────────────────────────────
    # Cobre "Mês/ano referência:", "Mes/ano referencia:" e variações com acento
    per_match = re.search(
        r"M[eê]s\/ano refer[eê]ncia[:\s]+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]+\/\d{4})",
        text, re.IGNORECASE
    )
    if per_match:
        inv["period"]     = per_match.group(1)
        inv["periodSort"] = _normalize_period(per_match.group(1))

    # Sem período = arquivo não é extrato de investimento
    if not inv["period"]:
        return None

    # ── Conta ─────────────────────────────────────────────────────────────────
    acc_match = re.search(r"Conta[:\s]+([\d]+-[\d]+|[0-9]+)", text, re.IGNORECASE)
    if acc_match:
        inv["account"] = acc_match.group(1).strip()

    # ── CNPJ do Fundo ─────────────────────────────────────────────────────────
    cnpj_match = re.search(r"CNPJ[:\s]+([\d./\-]+)", text, re.IGNORECASE)
    if cnpj_match:
        inv["cnpjFund"] = cnpj_match.group(1).strip()

    # ── Mapeamento de palavras-chave → campos de summary ──────────────────────
    SUMMARY_KEYS = {
        "SALDO ANTERIOR":   "saldoAnterior",
        "APLICA":           "aplicacoes",     # cobre APLICAÇÕES e APLICAÇÃO
        "RESGATES":         "resgates",
        "RENDIMENTO BRUTO": "rendBruto",
        "IMPOSTO DE RENDA": "ir",
        "IOF":              "iof",
        "RENDIMENTO L":     "rendLiquido",    # cobre RENDIMENTO LÍQUIDO
        "SALDO ATUAL":      "saldoAtual",
    }

    for line in lines:
        upper = line.upper()

        # Summary
        for key, field in SUMMARY_KEYS.items():
            if key in upper:
                num = _extract_brl_number(line)
                if num is not None:
                    inv["summary"][field] = num
                break

        # Rentabilidade
        if re.search(r"NO M[EÊ]S\s*:", upper):
            val = _extract_decimal(line)
            if val is not None:
                inv["rentability"]["month"] = val
        if re.search(r"NO ANO\s*:", upper):
            val = _extract_decimal(line)
            if val is not None:
                inv["rentability"]["year"] = val
        if re.search(r"[UÚ]LTIMOS 12", upper):
            val = _extract_decimal(line)
            if val is not None:
                inv["rentability"]["y12"] = val

        # Valor da cota: "31/10/2025     1,438563723"
        quota_match = re.match(r"^(\d{2}/\d{2}/\d{4})\s+([\d,]+)$", line.strip())
        if quota_match:
            inv["quotaValues"].append({
                "date":  quota_match.group(1),
                "value": float(quota_match.group(2).replace(",", ".")),
            })

        # Linhas de detalhe da tabela: "31/01/2025  APLICAÇÃO   3.200,00"
        row_match = re.match(
            r"^(\d{2}/\d{2}/\d{4})\s{2,}([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s/]+?)\s{2,}([\d.,]+)",
            line, re.IGNORECASE
        )
        if row_match:
            raw_val = row_match.group(3).replace(".", "").replace(",", ".")
            inv["items"].append({
                "date":  row_match.group(1),
                "desc":  row_match.group(2).strip(),
                "value": float(raw_val) if raw_val else 0.0,
            })

    return inv
