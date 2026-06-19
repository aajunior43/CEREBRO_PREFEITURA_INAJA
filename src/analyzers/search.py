# src/analyzers/search.py
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
from routes.expertmoney_db import get_em_db_connection as get_db_connection
from src.analyzers.detectors import normalize_beneficiary

def to_iso_date(v) -> str:
    if not v:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    # DD/MM/YYYY
    br = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", str(v))
    if br:
        return f"{br.group(3)}-{br.group(2)}-{br.group(1)}"
    return str(v)[:10]

def date_only(iso_str: str) -> str:
    if not iso_str:
        return ""
    return str(iso_str)[:10]

def build_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_amount = 0.0
    total_debits = 0.0
    total_credits = 0.0
    accounts_found = set()
    periods_found = set()

    for r in results:
        abs_amt = abs(r["amount"])
        total_amount += abs_amt
        if r["amount"] < 0:
            total_debits += abs_amt
        else:
            total_credits += abs_amt
        if r.get("accountId"):
            accounts_found.add(r["accountId"])
        if r.get("period"):
            periods_found.add(r["period"])

    return {
        "totalMatches": len(results),
        "totalAmount": total_amount,
        "totalDebits": total_debits,
        "totalCredits": total_credits,
        "netBalance": total_credits - total_debits,
        "accountCount": len(accounts_found),
        "accounts": list(accounts_found),
        "periods": sorted(list(periods_found)),
        "flaggedCount": sum(1 for r in results if r.get("flagged")),
    }

def search_transactions(filters: Dict[str, Any] = None) -> Dict[str, Any]:
    if filters is None:
        filters = {}

    type_val = filters.get("type", "both")
    amount = filters.get("amount")
    amount_tolerance = filters.get("amountTolerance", 0.0)
    amount_min = filters.get("amountMin")
    amount_max = filters.get("amountMax")
    date_val = filters.get("date")
    date_from = filters.get("dateFrom")
    date_to = filters.get("dateTo")
    memo = filters.get("memo")
    account_id = filters.get("accountId")
    session_id = filters.get("sessionId")
    flagged = filters.get("flagged")
    flag = filters.get("flag")
    limit = filters.get("limit", 500)
    sort_by = filters.get("sortBy", "date")
    sort_dir = filters.get("sortDir", "desc")

    conditions = []
    params = []

    if type_val == "debit":
        conditions.append("amount < 0")
    elif type_val == "credit":
        conditions.append("amount > 0")

    if amount is not None and amount != "":
        abs_amt = abs(float(amount))
        tol = abs(float(amount_tolerance or 0.0))
        if tol == 0.0:
            conditions.append("ABS(amount) = ?")
            params.append(abs_amt)
        else:
            conditions.append("ABS(amount) BETWEEN ? AND ?")
            params.append(abs_amt - tol, abs_amt + tol)

    if amount_min is not None and amount_min != "":
        conditions.append("ABS(amount) >= ?")
        params.append(abs(float(amount_min)))

    if amount_max is not None and amount_max != "":
        conditions.append("ABS(amount) <= ?")
        params.append(abs(float(amount_max)))

    if date_val:
        iso = to_iso_date(date_val)
        conditions.append("SUBSTR(date, 1, 10) = ?")
        params.append(iso)

    if date_from:
        conditions.append("SUBSTR(date, 1, 10) >= ?")
        params.append(to_iso_date(date_from))

    if date_to:
        conditions.append("SUBSTR(date, 1, 10) <= ?")
        params.append(to_iso_date(date_to))

    if memo and str(memo).strip():
        conditions.append("UPPER(memo) LIKE ?")
        params.append(f"%{str(memo).strip().upper()}%")

    if account_id:
        conditions.append("account_id = ?")
        params.append(account_id)

    if session_id:
        conditions.append("session_id = ?")
        params.append(session_id)

    if flagged is True:
        conditions.append("flagged = 1")
    elif flagged is False:
        conditions.append("flagged = 0")

    if flag and str(flag).strip():
        conditions.append("flags_json LIKE ?")
        params.append(f'%"{str(flag).strip()}"%')

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    sort_fields = {
        "date": "date",
        "amount": "ABS(amount)",
        "account": "account_id",
    }
    safe_sort = sort_fields.get(sort_by, "date")
    safe_dir = "ASC" if sort_dir == "asc" else "DESC"
    safe_limit = min(max(1, int(limit or 500)), 5000)

    sql = f"""
        SELECT
          tl.id,
          tl.session_id,
          tl.account_id,
          tl.type,
          tl.date,
          tl.date_str,
          tl.amount,
          tl.memo,
          tl.period,
          tl.flagged,
          tl.flags_json,
          acc.name   AS account_name,
          acc.number AS account_number,
          acc.bank   AS account_bank,
          acc.agency AS account_agency
        FROM transactions_log tl
        LEFT JOIN accounts acc ON acc.id = tl.account_id
        {where_clause}
        ORDER BY {safe_sort} {safe_dir}
        LIMIT ?
    """
    params.append(safe_limit)

    conn = get_db_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    results = []
    import json
    for r in rows:
        flags = []
        if r["flags_json"]:
            try:
                flags = json.loads(r["flags_json"])
            except Exception:
                pass
        
        results.append({
            "id": r["id"],
            "sessionId": r["session_id"],
            "accountId": r["account_id"],
            "accountName": r["account_name"] or "",
            "accountNumber": r["account_number"] or "",
            "accountBank": r["account_bank"] or "",
            "accountAgency": r["account_agency"] or "",
            "type": r["type"],
            "date": r["date"],
            "dateStr": r["date_str"] or date_only(r["date"]),
            "amount": r["amount"],
            "absAmount": abs(r["amount"]),
            "direction": "credit" if r["amount"] >= 0 else "debit",
            "memo": r["memo"] or "",
            "period": r["period"] or "",
            "flagged": bool(r["flagged"]),
            "flags": flags,
            "beneficiary": normalize_beneficiary(r["memo"])
        })

    summary = build_summary(results)
    return {"results": results, "summary": summary}

def search_debits(filters: Dict[str, Any] = None) -> Dict[str, Any]:
    filters = filters or {}
    filters["type"] = "debit"
    return search_transactions(filters)

def search_credits(filters: Dict[str, Any] = None) -> Dict[str, Any]:
    filters = filters or {}
    filters["type"] = "credit"
    return search_transactions(filters)

def find_by_amount(amount: float, tolerance: float = 0.02, extra_filters: Dict[str, Any] = None) -> Dict[str, Any]:
    filters = extra_filters or {}
    filters["amount"] = amount
    filters["amountTolerance"] = tolerance
    return search_transactions(filters)

def find_by_date_range(date_from: str, date_to: str, extra_filters: Dict[str, Any] = None) -> Dict[str, Any]:
    filters = extra_filters or {}
    filters["dateFrom"] = date_from
    filters["dateTo"] = date_to
    return search_transactions(filters)
