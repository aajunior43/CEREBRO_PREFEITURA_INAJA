#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prompts otimizados para análise de extratos bancários brasileiros.
Adaptado do RENOMEADOR-DE-EXTRATO-PRO para uso com qualquer API de chat (OpenRouter).
"""

# Bancos brasileiros mapeados para nomes padronizados
BANCOS_CONHECIDOS = {
    'banco do brasil': 'Banco_do_Brasil',
    ' bb ': 'Banco_do_Brasil',
    'caixa econômica': 'Caixa_Economica',
    'caixa economica': 'Caixa_Economica',
    'cef': 'Caixa_Economica',
    'itaú': 'Itau',
    'itau': 'Itau',
    'bradesco': 'Bradesco',
    'santander': 'Santander',
    'nubank': 'Nubank',
    'inter': 'Banco_Inter',
    'original': 'Banco_Original',
    'safra': 'Banco_Safra',
    'btg pactual': 'BTG_Pactual',
    'c6 bank': 'C6_Bank',
    'c6bank': 'C6_Bank',
    'next': 'Next',
    'picpay': 'PicPay',
    'sicoob': 'Sicoob',
    'sicredi': 'Sicredi',
    'banrisul': 'Banrisul',
    'unicred': 'Unicred',
}

# Padrões de conta por banco (para detecção local no texto extraído)
PADROES_BANCO = {
    'Banco_do_Brasil': {
        'conta': [r'Conta:\s*(\d[\d\-]+)', r'C/C:\s*(\d[\d\-]+)'],
        'agencia': [r'Agência:\s*(\d+)', r'Ag\.?:\s*(\d+)'],
        'periodo': [r'Período:\s*(\d{2}/\d{2}/\d{4})\s*a\s*(\d{2}/\d{2}/\d{4})'],
    },
    'Caixa_Economica': {
        'conta': [r'Conta:\s*(\d[\d\-]+)', r'Op:\s*(\d+)\s*Conta:\s*(\d[\d\-]+)'],
        'agencia': [r'Ag\.?:\s*(\d+)'],
    },
    'Itau': {
        'conta': [r'Conta:\s*(\d[\d\-]+)'],
        'agencia': [r'Agência:\s*(\d+)'],
        'periodo': [r'de\s*(\d{2}/\d{2}/\d{4})\s*até\s*(\d{2}/\d{2}/\d{4})'],
    },
}


def montar_prompt(nome_arquivo: str, texto_conteudo: str = None) -> str:
    """
    Monta o prompt para envio à IA.
    Se texto_conteudo estiver disponível, usa análise do conteúdo.
    Caso contrário, analisa apenas o nome do arquivo.
    """
    if texto_conteudo and len(texto_conteudo.strip()) > 50:
        return _prompt_com_conteudo(nome_arquivo, texto_conteudo)
    else:
        return _prompt_nome_apenas(nome_arquivo)


def _prompt_com_conteudo(nome_arquivo: str, texto: str) -> str:
    # Trunca para não exceder tokens
    texto_truncado = texto[:2500]
    return f"""Analise este extrato bancário brasileiro e retorne SOMENTE um JSON válido.

NOME DO ARQUIVO: "{nome_arquivo}"

CONTEÚDO DO ARQUIVO (primeiros 2500 caracteres):
{texto_truncado}

🔍 BUSCAR:
1. NÚMERO DA CONTA: procure "Conta:", "C/C:", "Ag: XXXX Conta: YYYY" — extraia apenas os dígitos principais
2. MÊS e ANO de referência do extrato (período)
3. BANCO: identifique o nome do banco
4. TIPO: corrente, poupanca, aplicacao, cartao

📤 RETORNE APENAS este JSON (sem texto adicional):
{{
  "mes": "01-12 com 2 dígitos, ou null",
  "ano": "YYYY com 4 dígitos, ou null",
  "conta": "número da conta sem formatação especial, ou null",
  "banco": "nome do banco ou null",
  "tipo_conta": "corrente|poupanca|aplicacao|cartao ou null",
  "confianca": 0.0
}}
"""


def _prompt_nome_apenas(nome_arquivo: str) -> str:
    return f"""Analise este nome de arquivo de extrato bancário e retorne SOMENTE um JSON válido.

NOME DO ARQUIVO: "{nome_arquivo}"

📤 RETORNE APENAS este JSON (sem texto adicional):
{{
  "mes": "01-12 com 2 dígitos, ou null",
  "ano": "YYYY com 4 dígitos, ou null",
  "conta": "número da conta bancária (dígitos e hífen), ou null",
  "banco": "nome do banco se identificável, ou null",
  "tipo_conta": "corrente|poupanca|aplicacao|cartao ou null",
  "confianca": 0.0
}}
"""


def detectar_banco_no_texto(texto: str) -> str | None:
    """Detecta nome do banco no texto extraído do arquivo."""
    if not texto:
        return None
    texto_lower = texto.lower()
    for chave, nome in BANCOS_CONHECIDOS.items():
        if chave.strip() in texto_lower:
            return nome
    return None
