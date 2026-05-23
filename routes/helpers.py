"""
Helpers compartilhados entre blueprints.
Extraídos do server.py original para reuso.
"""

import hashlib
import json
import os
import re
import time as _time
from collections import defaultdict
from io import BytesIO as _BytesIO
from threading import Lock

from flask import request, jsonify, Response

# ── Rate limiter ─────────────────────────────────────────────
_rate_buckets: dict[str, list[float]] = defaultdict(list)
_RATE_LOCK = Lock()


def rate_limited(key: str, max_hits: int = 5, window: int = 60) -> bool:
    now = _time.time()
    with _RATE_LOCK:
        hits = _rate_buckets[key]
        _rate_buckets[key] = [t for t in hits if now - t < window]
        if len(_rate_buckets[key]) >= max_hits:
            return True
        _rate_buckets[key].append(now)
        return False


# ── CNPJ ─────────────────────────────────────────────────────
def normalizar_cnpj(cnpj: str) -> str:
    return re.sub(r"\D", "", (cnpj or "").strip())


def cnpj_valido(cnpj: str) -> bool:
    digits = normalizar_cnpj(cnpj)
    if len(digits) != 14 or digits == digits[0] * 14:
        return False
    nums = [int(ch) for ch in digits]
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma1 = sum(nums[i] * pesos1[i] for i in range(12))
    resto1 = soma1 % 11
    dv1 = 0 if resto1 < 2 else 11 - resto1
    if nums[12] != dv1:
        return False
    pesos2 = [6] + pesos1
    soma2 = sum(nums[i] * pesos2[i] for i in range(12)) + dv1 * pesos2[12]
    resto2 = soma2 % 11
    dv2 = 0 if resto2 < 2 else 11 - resto2
    return nums[13] == dv2


# ── Credor payload ───────────────────────────────────────────
def credor_payload(data: dict, *, partial: bool = False) -> tuple[dict, list[str]]:
    errors: list[str] = []
    payload: dict = {}

    def has_value(key: str) -> bool:
        return key in data and data.get(key) is not None

    if not partial or has_value("nome"):
        nome = (data.get("nome") or "").strip().upper()
        if not nome:
            errors.append('Campo "nome" é obrigatório')
        elif len(nome) < 3:
            errors.append('Campo "nome" deve ter pelo menos 3 caracteres')
        else:
            payload["nome"] = nome

    if not partial or has_value("descricao"):
        payload["descricao"] = (data.get("descricao") or "").strip().upper()

    if not partial or has_value("departamento"):
        payload["departamento"] = (data.get("departamento") or "").strip().upper()

    if not partial or has_value("tipo_valor"):
        tipo_valor = (data.get("tipo_valor") or "FIXO").strip().upper()
        if tipo_valor not in {"FIXO", "VARIÁVEL", "VARIAVEL"}:
            errors.append('Campo "tipo_valor" deve ser FIXO ou VARIÁVEL')
        else:
            payload["tipo_valor"] = (
                "VARIÁVEL" if tipo_valor == "VARIAVEL" else tipo_valor
            )

    if not partial or has_value("valor"):
        try:
            valor = float(data.get("valor") or 0)
            if valor < 0:
                raise ValueError
            payload["valor"] = valor
        except Exception:
            errors.append('Campo "valor" deve ser numérico e maior ou igual a zero')

    if not partial or has_value("cnpj"):
        cnpj = normalizar_cnpj(data.get("cnpj", ""))
        if cnpj:
            if len(cnpj) != 14:
                errors.append('Campo "cnpj" deve conter 14 dígitos')
            elif not cnpj_valido(cnpj):
                errors.append('Campo "cnpj" inválido')
        payload["cnpj"] = cnpj

    if not partial or has_value("email"):
        email = (data.get("email") or "").strip().lower()
        if email and not re.fullmatch(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
            errors.append('Campo "email" inválido')
        payload["email"] = email

    if not partial or has_value("pagamento"):
        pagamento = (data.get("pagamento") or "").strip()
        if pagamento and not re.fullmatch(r"\d{1,3}", pagamento):
            errors.append('Campo "pagamento" deve conter apenas dias em número')
        payload["pagamento"] = pagamento

    if not partial or has_value("solicitacao"):
        payload["solicitacao"] = (data.get("solicitacao") or "").strip()

    if not partial or has_value("validade"):
        validade = (data.get("validade") or "").strip()
        if validade and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", validade):
            errors.append('Campo "validade" deve estar no formato AAAA-MM-DD')
        payload["validade"] = validade

    if not partial or has_value("obs"):
        payload["obs"] = (data.get("obs") or "").strip().upper()

    return payload, errors


def buscar_credor_duplicado(conn, cnpj: str, *, ignore_id: int | None = None):
    if cnpj:
        row = conn.execute(
            "SELECT id, nome FROM credores WHERE ativo=1 AND cnpj=?"
            + (" AND id<>?" if ignore_id else ""),
            (cnpj, ignore_id) if ignore_id else (cnpj,),
        ).fetchone()
        if row:
            return row, "Já existe um credor ativo com este CNPJ"
    return None, ""


def montar_filtros_credores(args):
    search = (args.get("search") or "").strip()
    departamento = (args.get("departamento") or "").strip().upper()
    tipo = (args.get("tipo") or "").strip().upper()
    status_cadastro = (args.get("status_cadastro") or "").strip().lower()
    somente_vencidos = parse_bool(args.get("somente_vencidos"))
    vencendo_dias = args.get("vencendo_dias", type=int)
    status = (args.get("status") or "").strip().lower()
    ano = args.get("ano", type=int)
    mes = args.get("mes", type=int)

    clauses = ["ativo=1"]
    params: list = []

    if search:
        clauses.append("id IN (SELECT rowid FROM credores_fts WHERE credores_fts MATCH ?)")
        params.append(search)

    if departamento:
        clauses.append("COALESCE(departamento, '')=?")
        params.append(departamento)

    if tipo:
        clauses.append("COALESCE(tipo_valor, 'FIXO')=?")
        params.append("VARIÁVEL" if tipo == "VARIAVEL" else tipo)

    if status_cadastro == "sem_cnpj":
        clauses.append("COALESCE(cnpj, '')=''")
    elif status_cadastro == "sem_email":
        clauses.append("COALESCE(email, '')=''")
    elif status_cadastro == "com_pendencias":
        clauses.append("(COALESCE(cnpj, '')='' OR COALESCE(email, '')='')")

    if somente_vencidos:
        clauses.append(
            "COALESCE(validade, '')<>'' AND date(validade) < date('now','localtime')"
        )
    elif vencendo_dias is not None and vencendo_dias >= 0:
        clauses.append(
            "COALESCE(validade, '')<>'' AND date(validade) >= date('now','localtime') AND date(validade) <= date('now','localtime', ?)"
        )
        params.append(f"+{vencendo_dias} day")

    if status in {"empenhado", "pendente"} and ano and mes:
        exists_sql = (
            "EXISTS (SELECT 1 FROM empenhos e "
            "WHERE e.credor_id = credores.id AND e.ano=? AND e.mes=?)"
        )
        clauses.append(exists_sql if status == "empenhado" else f"NOT {exists_sql}")
        params.extend([ano, mes])

    return clauses, params


# ── Utils ────────────────────────────────────────────────────
def parse_bool(value) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "sim"}


def slugify(value: str, fallback: str = "geral") -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_-]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or fallback


def clean_value(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def api_error(message: str, status: int = 400, details: dict | None = None):
    body: dict = {"error": message}
    if details:
        body["details"] = details
    return jsonify(body), status
