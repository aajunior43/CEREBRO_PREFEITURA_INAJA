"""
app/utils/helpers.py — Funções auxiliares do sistema
"""

import re
import os
import hashlib
import time as _time
from collections import defaultdict
from threading import Lock
from flask import request, jsonify
from config import settings


def row_to_dict(row):
    """Converte sqlite3.Row em dicionário."""
    return dict(row) if row else {}


def normalizar_cnpj(cnpj: str) -> str:
    """Remove caracteres não numéricos do CNPJ."""
    return re.sub(r'\D', '', (cnpj or '').strip())


def cnpj_valido(cnpj: str) -> bool:
    """Valida um CNPJ pelos dígitos verificadores."""
    digits = normalizar_cnpj(cnpj)
    if len(digits) != 14:
        return False
    if digits == digits[0] * 14:
        return False

    base = [int(ch) for ch in digits]
    weights_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma_1 = sum(base[i] * weights_1[i] for i in range(12))
    resto_1 = soma_1 % 11
    digito_1 = 0 if resto_1 < 2 else 11 - resto_1
    if base[12] != digito_1:
        return False

    weights_2 = [6] + weights_1
    soma_2 = sum(base[i] * weights_2[i] for i in range(12)) + digito_1 * weights_2[12]
    resto_2 = soma_2 % 11
    digito_2 = 0 if resto_2 < 2 else 11 - resto_2
    return base[13] == digito_2


def parse_bool(value) -> bool:
    """Converte valor para booleano."""
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'on', 'sim'}


def slugify(value: str, fallback: str = 'geral') -> str:
    """Cria slug a partir de texto."""
    text = (value or '').strip().lower()
    text = re.sub(r'[^a-z0-9_-]+', '-', text)
    text = re.sub(r'-+', '-', text).strip('-')
    return text or fallback


def normalize_phone_br(phone: str) -> str:
    """Normaliza número de telefone brasileiro."""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 11 and digits.startswith('55'):
        return digits
    if len(digits) == 10 or len(digits) == 11:
        return '55' + digits
    return digits


def build_document_storage(categoria: str, referencia: str, original_name: str) -> tuple:
    """Cria caminho para armazenamento de documentos."""
    DOCUMENTS_DIR = os.path.join(str(settings.base_dir), 'documentos_centro')
    
    categoria_slug = slugify(categoria, 'geral')
    referencia_slug = slugify(referencia, 'sem-referencia') if referencia else 'sem-referencia'
    ext = os.path.splitext(original_name or '')[1].lower()[:20]
    
    unique_name = f"{int(_time.time() * 1000)}_{hashlib.sha1((original_name + str(_time.time())).encode()).hexdigest()[:10]}{ext}"
    relative_dir = os.path.join(categoria_slug, referencia_slug)
    abs_dir = os.path.join(DOCUMENTS_DIR, relative_dir)
    os.makedirs(abs_dir, exist_ok=True)
    
    return unique_name, relative_dir.replace('\\', '/'), os.path.join(abs_dir, unique_name)


def persist_document_file(original_name: str, content: bytes, categoria: str = 'gerados', 
                          referencia: str = '', descricao: str = '', mime_type: str = ''):
    """Persiste arquivo de documento no banco e disco."""
    from app.utils.db import get_db
    
    nome_arquivo, relative_dir, abs_path = build_document_storage(categoria, referencia, original_name)
    
    with open(abs_path, 'wb') as fh:
        fh.write(content)
    
    tamanho = os.path.getsize(abs_path)
    extensao = os.path.splitext(original_name)[1].lower()
    caminho_relativo = f"{relative_dir}/{nome_arquivo}" if relative_dir else nome_arquivo
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO documentos_centro 
           (nome_original, nome_arquivo, categoria, referencia, descricao, tamanho, extensao, caminho_relativo) 
           VALUES (?,?,?,?,?,?,?,?)""",
        (original_name, nome_arquivo, categoria, referencia, descricao, tamanho, extensao, caminho_relativo)
    )
    new_id = cur.lastrowid
    conn.commit()
    
    row = conn.execute("SELECT * FROM documentos_centro WHERE id=?", (new_id,)).fetchone()
    return row_to_dict(row)


# ── Rate limiter ─────────────────────────────────────────────
_rate_buckets: dict = defaultdict(list)
_RATE_LOCK = Lock()


def rate_limited(key: str, max_hits: int = 5, window: int = 60) -> bool:
    """Rate limitador em memória (thread-safe). Retorna True se bloqueado."""
    now = _time.time()
    with _RATE_LOCK:
        hits = _rate_buckets[key]
        _rate_buckets[key] = [t for t in hits if now - t < window]
        if len(_rate_buckets[key]) >= max_hits:
            return True
        _rate_buckets[key].append(now)
        return False


# ── Credor helpers (de routes/helpers.py) ───────────────────
def credor_payload(data: dict, *, partial: bool = False) -> tuple:
    """Valida e normaliza payload de credor."""
    errors = []
    payload = {}

    def has_value(key):
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


def buscar_credor_duplicado(conn, cnpj: str, *, ignore_id: int = None):
    """Verifica se já existe credor ativo com o mesmo CNPJ."""
    if cnpj:
        row = conn.execute(
            "SELECT id, nome FROM credores WHERE ativo=1 AND cnpj=?"
            + (" AND id<>" + str(ignore_id) if ignore_id else ""),
            (cnpj,) if not ignore_id else (cnpj, ignore_id),
        ).fetchone()
        if row:
            return row, "Já existe um credor ativo com este CNPJ"
    return None, ""


def montar_filtros_credores(args):
    """Monta cláusulas WHERE para filtro de credores."""
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
    params = []

    if search:
        like = f"%{search.lower()}%"
        clauses.append("("
            "LOWER(nome) LIKE ? "
            "OR LOWER(COALESCE(descricao, '')) LIKE ? "
            "OR LOWER(COALESCE(cnpj, '')) LIKE ? "
            "OR LOWER(COALESCE(email, '')) LIKE ?"
        ")")
        params.extend([like, like, like, like])

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


def clean_value(value):
    """Normaliza valor para string ou vazio."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def api_error(message: str, status: int = 400, code: str = None, details: dict = None):
    """Resposta JSON de erro padronizada.

    Formato consistente:
        {"error": {"code": "...", "message": "...", "details": {...}}}
    """
    error_code = code or {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "UNPROCESSABLE_ENTITY",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_ERROR",
    }.get(status, "ERROR")

    body = {
        "error": {
            "code": error_code,
            "message": message,
        }
    }
    if details:
        body["error"]["details"] = details
    return jsonify(body), status
