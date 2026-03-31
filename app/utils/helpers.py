"""
app/utils/helpers.py — Funções auxiliares do sistema
"""

import re
import os
import hashlib
import time as _time
from config import settings


def row_to_dict(row):
    """Converte sqlite3.Row em dicionário."""
    return dict(row) if row else {}


def normalizar_cnpj(cnpj: str) -> str:
    """Remove caracteres não numéricos do CNPJ."""
    return re.sub(r'\D', '', (cnpj or '').strip())


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
