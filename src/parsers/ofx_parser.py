"""
ExpertMoney Analyzer — OFX Parser (Python)
Equivalente a: src/parsers/ofxParser.js

Suporta:
  - Múltiplos blocos STMTRS no mesmo arquivo (multi-conta)
  - Detecção automática de banco pelo BANKID
  - Fallback de encoding (windows-1252 → utf-8)
  - Extração do período a partir do nome do arquivo
  - Cálculo de período mediano das transações
"""
import re
from datetime import datetime, timezone
from typing import Optional

# ── Bank Profiles ─────────────────────────────────────────────────────────────
BANK_PROFILES = {
    "001": {"name": "Banco do Brasil",          "encoding": "windows-1252"},
    "341": {"name": "Itau Unibanco",            "encoding": "windows-1252"},
    "033": {"name": "Santander",                "encoding": "utf-8"},
    "237": {"name": "Bradesco",                 "encoding": "windows-1252"},
    "104": {"name": "Caixa Economica Federal",  "encoding": "windows-1252"},
    "260": {"name": "Nu Pagamentos (Nubank)",   "encoding": "utf-8"},
    "077": {"name": "Banco Inter",              "encoding": "utf-8"},
    "290": {"name": "PagSeguro",                "encoding": "utf-8"},
    "748": {"name": "Sicredi",                  "encoding": "windows-1252"},
    "756": {"name": "Sicoob",                   "encoding": "windows-1252"},
    "422": {"name": "Banco Safra",              "encoding": "windows-1252"},
    "399": {"name": "HSBC Brasil",              "encoding": "utf-8"},
}

# ── Helpers internos ──────────────────────────────────────────────────────────

def _extract_tag(text: str, tag: str) -> Optional[str]:
    """Extrai o valor de uma tag OFX simples (equivalente a extractTag do JS)."""
    m = re.search(rf"<{tag}>([^<\r\n]+)", text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _parse_ofx_date(s: str) -> Optional[datetime]:
    """
    Converte data OFX (YYYYMMDD ou YYYYMMDDHHMMSS[.mmm][+TZ]) em datetime UTC.
    Equivalente a parseOFXDate do JS.
    """
    if not s or len(s) < 8:
        return None
    s = s.strip()
    try:
        y, mo, d = int(s[0:4]), int(s[4:6]), int(s[6:8])
        return datetime(y, mo, d, 12, 0, 0, tzinfo=timezone.utc)
    except (ValueError, IndexError):
        return None


def _period_from_ofx_date(s: str) -> str:
    """Converte data OFX em string de período MM/YYYY."""
    if not s or len(s) < 6:
        return ""
    return f"{s[4:6]}/{s[0:4]}"


def _format_date(d: datetime) -> str:
    """Formata datetime em DD/MM/YYYY (equivalente a formatDate do JS)."""
    return d.strftime("%d/%m/%Y")


def _clean_memo(s: str) -> str:
    """Remove caracteres de controle e normaliza espaços no memo."""
    s = re.sub(r"[^\x20-\x7EÀ-ÖØ-öø-ÿÁáÉéÍíÓóÚúÃãÕõÂâÊêÎîÔôÛûÇç]", " ", s or "")
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()


def _extract_file_period(filename: str) -> str:
    """Extrai período MM/YYYY do nome do arquivo (ex: '01-2025.ofx' → '01/2025')."""
    m = re.search(r"(\d{2})-(\d{4})", filename)
    return f"{m.group(1)}/{m.group(2)}" if m else ""


def _calculate_median_period(text: str) -> str:
    """Calcula o período mediano das datas de transação no bloco OFX."""
    dates = []
    for m in re.finditer(r"<DTPOSTED>([^<\r\n]+)", text, re.IGNORECASE):
        d = _parse_ofx_date(m.group(1).strip())
        if d:
            dates.append(d)
    if not dates:
        return ""
    dates.sort()
    mid = len(dates) // 2
    median = dates[mid] if len(dates) % 2 != 0 else dates[mid - 1]
    return median.strftime("%m/%Y")


def _detect_bank_profile(raw: bytes) -> dict:
    """
    Detecta banco pelo BANKID e determina encoding correto.
    Equivalente a detectBankProfile do JS.
    """
    preview = raw[:2000].decode("latin-1", errors="replace")
    m = re.search(r"<BANKID>([^<\r\n]+)", preview, re.IGNORECASE)
    bank_id = m.group(1).strip() if m else ""

    profile = BANK_PROFILES.get(bank_id, {
        "name": f"Banco {bank_id or 'Desconhecido'}",
        "encoding": "windows-1252",
    })
    result = {**profile, "bankId": bank_id}

    # Teste de encoding: decodifica 500 bytes e verifica substituições
    chunk = raw[:500]
    try:
        decoded = chunk.decode(result["encoding"], errors="replace")
        if "\ufffd" in decoded or any("\u0080" <= c <= "\u009f" for c in decoded):
            result["encoding"] = "utf-8"
            result["encodingFallback"] = True
    except (LookupError, UnicodeDecodeError):
        result["encoding"] = "utf-8"

    return result


def _extract_stmt_blocks(text: str) -> list:
    """
    Extrai blocos <STMTRS>...</STMTRS> do documento OFX.
    Equivalente a extractStmtBlocks do JS.
    """
    return re.findall(r"<STMTRS>([\s\S]*?)</STMTRS>", text, re.IGNORECASE)


def _parse_transactions(text: str, period: str, filename: str,
                        acct_id: str, seq_offset: int = 0) -> list:
    """
    Extrai todas as transações de um bloco OFX.
    Equivalente a parseTransactions do JS — preserva a mesma estrutura de campos.
    """
    txns = []
    seq = seq_offset

    for m in re.finditer(r"<STMTTRN>([\s\S]*?)</STMTTRN>", text, re.IGNORECASE):
        block = m.group(1)

        def get(tag):
            return _extract_tag(block, tag) or ""

        tx_type  = get("TRNTYPE")
        posted   = get("DTPOSTED")
        raw_amt  = get("TRNAMT")
        fitid    = get("FITID")
        memo     = get("MEMO")
        checknum = get("CHECKNUM")

        if not tx_type or not posted:
            continue

        try:
            amount = float(raw_amt.replace(",", "."))
        except ValueError:
            amount = 0.0

        date = _parse_ofx_date(posted)
        if date is None:
            continue

        seq += 1
        tx_id = f"{period}-{fitid}" if fitid else f"{period}-{acct_id}-{seq}"

        txns.append({
            "seq":           seq,
            "id":            tx_id,
            "type":          tx_type,
            "date":          date.isoformat(),
            "dateStr":       _format_date(date),
            "amount":        amount,
            "amountAbs":     abs(amount),
            "direction":     "credit" if amount >= 0 else "debit",
            "memo":          _clean_memo(memo),
            "checknum":      checknum,
            "period":        period,
            "filename":      filename,
            "sourceAccount": acct_id or None,
            "flagged":       False,
            "flags":         [],
            "alerts":        [],
        })

    return txns


def _parse_single_block(text: str, filename: str, file_period: str,
                        seq_offset: int, bank_profile: dict) -> dict:
    """
    Parseia um único bloco STMTRS.
    Equivalente a parseSingleBlock do JS.
    """
    period = (file_period
              or _calculate_median_period(text)
              or _period_from_ofx_date(_extract_tag(text, "DTSTART") or ""))

    account = _extract_tag(text, "ACCTID") or ""
    bank_id = _extract_tag(text, "BANKID") or bank_profile.get("bankId", "")

    date_start = _parse_ofx_date(_extract_tag(text, "DTSTART") or "")
    date_end   = _parse_ofx_date(_extract_tag(text, "DTEND")   or "")

    bal_amt = _extract_tag(text, "BALAMT")
    ledger_balance      = float(bal_amt.replace(",", ".")) if bal_amt else None
    ledger_balance_date = _parse_ofx_date(_extract_tag(text, "DTASOF") or "")

    transactions = _parse_transactions(text, period, filename, account, seq_offset)
    transactions.sort(key=lambda t: t["date"])

    return {
        "filename":          filename,
        "period":            period,
        "account":           account,
        "accounts":          [account] if account else [],
        "multiAccount":      False,
        "bankId":            bank_id,
        "bankName":          bank_profile.get("name", ""),
        "currency":          _extract_tag(text, "CURDEF") or "BRL",
        "dateStart":         date_start.isoformat() if date_start else None,
        "dateEnd":           date_end.isoformat()   if date_end   else None,
        "ledgerBalance":     ledger_balance,
        "ledgerBalanceDate": ledger_balance_date.isoformat() if ledger_balance_date else None,
        "transactions":      transactions,
    }


# ── API pública ───────────────────────────────────────────────────────────────

def parse_ofx(buffer: bytes, filename: str) -> dict:
    """
    Parseia um arquivo OFX e retorna estrutura de dados padrão.

    Suporta:
      - Arquivo com único bloco STMTRS
      - Arquivo com múltiplos blocos STMTRS (multi-conta)
      - Encoding automático (windows-1252 / utf-8)

    Retorna:
      {
        filename, period, account, accounts, multiAccount,
        bankId, bankName, currency, dateStart, dateEnd,
        ledgerBalance, ledgerBalanceDate, transactions
      }
    """
    bank_profile = _detect_bank_profile(buffer)
    text         = buffer.decode(bank_profile["encoding"], errors="replace")
    file_period  = _extract_file_period(filename)

    stmt_blocks = _extract_stmt_blocks(text)

    # Sem estrutura STMTRS reconhecida — tenta o documento inteiro
    if not stmt_blocks:
        return _parse_single_block(text, filename, file_period, 0, bank_profile)

    # Único bloco — caminho rápido
    if len(stmt_blocks) == 1:
        return _parse_single_block(stmt_blocks[0], filename, file_period, 0, bank_profile)

    # Múltiplos blocos: mescla tudo
    all_transactions = []
    account_numbers  = []
    primary_bank_id  = ""
    primary_date_start      = None
    primary_date_end        = None
    primary_balance         = None
    primary_balance_date    = None
    global_seq = 0

    for block in stmt_blocks:
        acct_id = _extract_tag(block, "ACCTID") or ""
        bank_id = _extract_tag(block, "BANKID") or ""
        if acct_id and acct_id not in account_numbers:
            account_numbers.append(acct_id)
        if bank_id and not primary_bank_id:
            primary_bank_id = bank_id

        dt_start = _extract_tag(block, "DTSTART")
        dt_end   = _extract_tag(block, "DTEND")
        if dt_start and not primary_date_start:
            primary_date_start = _parse_ofx_date(dt_start)
        if dt_end and not primary_date_end:
            primary_date_end = _parse_ofx_date(dt_end)

        bal_amt = _extract_tag(block, "BALAMT")
        if bal_amt and primary_balance is None:
            primary_balance = float(bal_amt.replace(",", "."))
        dt_asof = _extract_tag(block, "DTASOF")
        if dt_asof and not primary_balance_date:
            primary_balance_date = _parse_ofx_date(dt_asof)

        period = (file_period
                  or _calculate_median_period(block)
                  or _period_from_ofx_date(dt_start or ""))
        txns = _parse_transactions(block, period, filename, acct_id, global_seq)
        global_seq += len(txns)
        all_transactions.extend(txns)

    all_transactions.sort(key=lambda t: t["date"])

    return {
        "filename":          filename,
        "period":            file_period or _calculate_median_period(text),
        "account":           account_numbers[0] if account_numbers else "",
        "accounts":          account_numbers,
        "multiAccount":      len(account_numbers) > 1,
        "bankId":            primary_bank_id,
        "bankName":          bank_profile.get("name", ""),
        "currency":          _extract_tag(text, "CURDEF") or "BRL",
        "dateStart":         primary_date_start.isoformat() if primary_date_start else None,
        "dateEnd":           primary_date_end.isoformat()   if primary_date_end   else None,
        "ledgerBalance":     primary_balance,
        "ledgerBalanceDate": primary_balance_date.isoformat() if primary_balance_date else None,
        "transactions":      all_transactions,
    }
