#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extrator de texto de arquivos bancários (PDF, OFX, TXT).
Adaptado do RENOMEADOR-DE-EXTRATO-PRO para uso como módulo standalone.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Importações opcionais — degradação graciosa se não instaladas
try:
    import pdfplumber
    _HAS_PDFPLUMBER = True
except ImportError:
    _HAS_PDFPLUMBER = False

try:
    import PyPDF2
    _HAS_PYPDF2 = True
except ImportError:
    _HAS_PYPDF2 = False


def extrair_texto(arquivo: Path, max_chars: int = 3000) -> Optional[str]:
    """
    Extrai texto legível de um arquivo bancário.
    Suporta PDF, OFX, QIF, TXT.
    Retorna None se não conseguir extrair nada útil.
    """
    arquivo = Path(arquivo)
    ext = arquivo.suffix.lower()

    try:
        if ext == '.pdf':
            return _extrair_pdf(arquivo, max_chars)
        elif ext in ('.ofx', '.qif'):
            return _extrair_ofx(arquivo, max_chars)
        elif ext == '.txt':
            return _extrair_txt(arquivo, max_chars)
    except Exception as e:
        logger.warning(f"[FileProcessor] Erro ao extrair texto de '{arquivo.name}': {e}")

    return None


def _extrair_pdf(arquivo: Path, max_chars: int) -> Optional[str]:
    """Extrai texto de PDF usando pdfplumber (primary) ou PyPDF2 (fallback)."""
    texto = ""

    if _HAS_PDFPLUMBER:
        try:
            with pdfplumber.open(str(arquivo)) as pdf:
                partes = []
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        partes.append(t)
                texto = "\n".join(partes).strip()
        except Exception as e:
            logger.warning(f"[pdfplumber] falhou para '{arquivo.name}': {e}")
            texto = ""

    if not texto and _HAS_PYPDF2:
        try:
            with open(str(arquivo), 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                partes = []
                for page in reader.pages:
                    t = page.extract_text()
                    if t:
                        partes.append(t)
                texto = "\n".join(partes).strip()
        except Exception as e:
            logger.warning(f"[PyPDF2] falhou para '{arquivo.name}': {e}")
            texto = ""

    return texto[:max_chars] if texto else None


def _extrair_ofx(arquivo: Path, max_chars: int) -> Optional[str]:
    """Extrai texto de OFX lendo como texto plano (tags XML-like)."""
    for enc in ('utf-8', 'iso-8859-1', 'windows-1252'):
        try:
            with open(str(arquivo), 'r', encoding=enc, errors='ignore') as f:
                conteudo = f.read(max_chars * 2)
            if conteudo.strip():
                return conteudo[:max_chars]
        except Exception:
            continue
    return None


def _extrair_txt(arquivo: Path, max_chars: int) -> Optional[str]:
    """Lê arquivo de texto simples."""
    for enc in ('utf-8', 'iso-8859-1', 'windows-1252'):
        try:
            with open(str(arquivo), 'r', encoding=enc, errors='ignore') as f:
                conteudo = f.read(max_chars)
            if conteudo.strip():
                return conteudo
        except Exception:
            continue
    return None


def dependencias_disponiveis() -> dict:
    """Retorna quais bibliotecas de extração estão disponíveis."""
    return {
        'pdfplumber': _HAS_PDFPLUMBER,
        'PyPDF2': _HAS_PYPDF2,
        'pdf_ok': _HAS_PDFPLUMBER or _HAS_PYPDF2,
    }
