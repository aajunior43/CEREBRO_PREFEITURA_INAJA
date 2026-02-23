#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Organizador Local Avançado - SEM IA
Sistema com detecção avançada de padrões para contas, datas e números
(Adaptado para uso como módulo no servidor web)
"""

import os
import re
import shutil
import json
from datetime import datetime
from pathlib import Path
import logging
from typing import Dict, List


class OrganizadorLocalAvancado:
    def __init__(self, diretorio_origem: str, diretorio_destino: str):
        """Inicializa organizador local avançado"""
        self.diretorio_origem = Path(diretorio_origem)
        self.diretorio_destino = Path(diretorio_destino)
        self.setup_logging()

        # Padrões avançados para detecção
        self.padroes = {
            'data_mm_yyyy': re.compile(r'(\d{1,2})[\/\-\.](\d{4})', re.IGNORECASE),
            'data_mm_yy': re.compile(r'(\d{1,2})[\/\-\.](\d{2})', re.IGNORECASE),
            'data_yyyy_mm': re.compile(r'(\d{4})[\/\-\.](\d{1,2})', re.IGNORECASE),
            'data_yyyymm': re.compile(r'(\d{4})(\d{2})', re.IGNORECASE),
            'data_timestamp': re.compile(r'(\d{4})-(\d{2})-(\d{2})', re.IGNORECASE),
            'mes_nome_completo': re.compile(r'(JANEIRO|FEVEREIRO|MARÇO|MARCO|ABRIL|MAIO|JUNHO|JULHO|AGOSTO|SETEMBRO|OUTUBRO|NOVEMBRO|DEZEMBRO)', re.IGNORECASE),
            'mes_nome_abrev': re.compile(r'(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)', re.IGNORECASE),
            'conta_inicio_mes': re.compile(r'^(\d{4,8}[-]?[A-Z0-9])\s+(JANEIRO|FEVEREIRO|MARÇO|MARCO|ABRIL|MAIO|JUNHO|JULHO|AGOSTO|SETEMBRO|OUTUBRO|NOVEMBRO|DEZEMBRO)', re.IGNORECASE),
            'conta_inicio_mes_abrev': re.compile(r'^(\d{4,8}[-]?[A-Z0-9])\s+(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)', re.IGNORECASE),
            'conta_mes_inicio': re.compile(r'^(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)\s+(\d{4,8}[-]?[A-Z0-9])', re.IGNORECASE),
            'conta_hifen': re.compile(r'(\d{3,8}[-]\d{1})', re.IGNORECASE),
            'conta_hifen_letra': re.compile(r'(\d{3,8}[-][A-Z0-9]{1})', re.IGNORECASE),
            'conta_hifen_espaco': re.compile(r'(\d{4,8}[-]\s*[A-Z0-9])', re.IGNORECASE),
            'conta_simples': re.compile(r'(?<![\d])(\d{4,8})(?![\d])', re.IGNORECASE),
            'conta_ext': re.compile(r'EXT\w*\s+\w*\s*(\d+[-]?\w*)', re.IGNORECASE),
            'conta_ext_simples': re.compile(r'^EXT\s+(\d+[-]?\w*)', re.IGNORECASE),
            'conta_extrato': re.compile(r'[Ee]xtrato\s*(\d+)', re.IGNORECASE),
            'conta_extrato_longo': re.compile(r'[Ee]xtrato(\d{8,})', re.IGNORECASE),
            'conta_caixa': re.compile(r'CAIXA\w*\s+\w*\s+(\d+[-]?\w*)', re.IGNORECASE),
            'conta_banco': re.compile(r'(?:BANCO|CONTA|CC|AG)\s*(\d+[-]?\w*)', re.IGNORECASE),
            'conta_codigo_data': re.compile(r'(\d{8,12})(?=\d{4})', re.IGNORECASE),
            'conta_gfi': re.compile(r'GFI(\d+)', re.IGNORECASE),
            'conta_timestamp_longo': re.compile(r'(\d{15,})', re.IGNORECASE),
            'ano_4digitos': re.compile(r'(20\d{2})', re.IGNORECASE),
            'ano_2digitos': re.compile(r'(\d{2})(?=\D|$)', re.IGNORECASE),
        }

        self.meses_nomes = {
            'JANEIRO': '01', 'JAN': '01',
            'FEVEREIRO': '02', 'FEV': '02',
            'MARÇO': '03', 'MARCO': '03', 'MAR': '03',
            'ABRIL': '04', 'ABR': '04',
            'MAIO': '05', 'MAI': '05',
            'JUNHO': '06', 'JUN': '06',
            'JULHO': '07', 'JUL': '07',
            'AGOSTO': '08', 'AGO': '08',
            'SETEMBRO': '09', 'SET': '09',
            'OUTUBRO': '10', 'OUT': '10',
            'NOVEMBRO': '11', 'NOV': '11',
            'DEZEMBRO': '12', 'DEZ': '12'
        }

        self.stats = {
            'total_arquivos': 0, 'processados': 0,
            'erros': 0, 'data_encontrada': 0, 'conta_encontrada': 0
        }

    def setup_logging(self):
        """Configura logging sem poluir configuração global."""
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.FileHandler('organizador_local.log', encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def detectar_data(self, texto: str, caminho_completo: str = "") -> Dict:
        """Detecta mês e ano no texto usando múltiplos padrões"""
        texto_completo = f"{texto} {caminho_completo}".upper()
        mes = None
        ano = None

        for padrao_nome in ['mes_nome_completo', 'mes_nome_abrev']:
            match = self.padroes[padrao_nome].search(texto_completo)
            if match:
                nome_mes = match.group(1).upper()
                mes = self.meses_nomes.get(nome_mes)
                if mes:
                    break

        match = self.padroes['ano_4digitos'].search(texto_completo)
        if match:
            ano = match.group(1)

        if not mes or not ano:
            match = self.padroes['data_mm_yyyy'].search(texto_completo)
            if match:
                mes_num = match.group(1).zfill(2)
                ano_encontrado = match.group(2)
                if not mes and 1 <= int(mes_num) <= 12:
                    mes = mes_num
                if not ano:
                    ano = ano_encontrado

        if not mes or not ano:
            match = self.padroes['data_mm_yy'].search(texto_completo)
            if match:
                mes_num = match.group(1).zfill(2)
                ano_curto = match.group(2)
                if not mes and 1 <= int(mes_num) <= 12:
                    mes = mes_num
                if not ano:
                    ano = f"20{ano_curto}"

        if not mes or not ano:
            match = self.padroes['data_yyyy_mm'].search(texto_completo)
            if match:
                ano_encontrado = match.group(1)
                mes_num = match.group(2).zfill(2)
                if not ano:
                    ano = ano_encontrado
                if not mes and 1 <= int(mes_num) <= 12:
                    mes = mes_num

        if not mes or not ano:
            match = self.padroes['data_yyyymm'].search(texto_completo)
            if match:
                ano_encontrado = match.group(1)
                mes_num = match.group(2)
                if not ano:
                    ano = ano_encontrado
                if not mes and 1 <= int(mes_num) <= 12:
                    mes = mes_num

        if not mes or not ano:
            match = self.padroes['data_timestamp'].search(texto_completo)
            if match:
                ano_encontrado = match.group(1)
                mes_num = match.group(2)
                if not ano:
                    ano = ano_encontrado
                if not mes and 1 <= int(mes_num) <= 12:
                    mes = mes_num

        if mes and not (1 <= int(mes) <= 12):
            mes = None
        if ano and len(ano) == 2:
            ano = f"20{ano}"
        if ano and not (2020 <= int(ano) <= 2035):
            ano = None

        return {'mes': mes, 'ano': ano, 'encontrado': bool(mes and ano)}

    def detectar_conta(self, texto: str) -> Dict:
        """Detecta número da conta usando múltiplos padrões"""
        texto_upper = texto.upper()
        conta = None
        metodo = None

        padroes_conta = [
            ('conta_inicio_mes', 'INICIO_MES'),
            ('conta_inicio_mes_abrev', 'INICIO_MES_ABREV'),
            ('conta_mes_inicio', 'MES_INICIO'),
            ('conta_ext_simples', 'EXT_SIMPLES'),
            ('conta_ext', 'EXT'),
            ('conta_caixa', 'CAIXA'),
            ('conta_extrato_longo', 'EXTRATO_LONGO'),
            ('conta_extrato', 'EXTRATO'),
            ('conta_gfi', 'GFI'),
            ('conta_banco', 'BANCO'),
            ('conta_hifen_espaco', 'HIFEN_ESPACO'),
            ('conta_hifen', 'HIFEN'),
            ('conta_hifen_letra', 'HIFEN_LETRA'),
            ('conta_timestamp_longo', 'TIMESTAMP_LONGO'),
            ('conta_codigo_data', 'CODIGO_DATA'),
            ('conta_simples', 'SIMPLES')
        ]

        for padrao_nome, metodo_nome in padroes_conta:
            match = self.padroes[padrao_nome].search(texto_upper)
            if match:
                if padrao_nome == 'conta_mes_inicio':
                    conta_bruta = match.group(2)
                elif padrao_nome in ['conta_inicio_mes', 'conta_inicio_mes_abrev']:
                    conta_bruta = match.group(1)
                else:
                    conta_bruta = match.group(1)
                conta = re.sub(r'[^\w]', '', conta_bruta)
                metodo = metodo_nome
                break

        if conta and len(conta) < 3:
            conta = None
            metodo = None

        return {'conta': conta, 'metodo': metodo, 'encontrado': bool(conta)}

    def processar_arquivo(self, arquivo: Path, modo_teste: bool = True) -> Dict:
        """Processa um arquivo individual"""
        resultado = {
            'arquivo_original': str(arquivo),
            'nome_original': arquivo.name,
            'sucesso': False,
            'erro': None,
            'detalhes': {}
        }

        try:
            deteccao_data = self.detectar_data(arquivo.name, str(arquivo.parent))
            deteccao_conta = self.detectar_conta(arquivo.name)

            resultado['detalhes'] = {'data': deteccao_data, 'conta': deteccao_conta}

            if not deteccao_data['encontrado']:
                raise Exception("Data não identificada")
            if not deteccao_conta['encontrado']:
                raise Exception("Conta não identificada")

            mes = deteccao_data['mes']
            ano = deteccao_data['ano']
            conta = deteccao_conta['conta']

            tipo = "PDF" if arquivo.suffix.lower() == ".pdf" else "OFX"
            nome_novo = f"{ano}-{mes}_{conta}_{tipo}{arquivo.suffix.lower()}"

            meses_ext = {
                '01': 'JANEIRO', '02': 'FEVEREIRO', '03': 'MARÇO',
                '04': 'ABRIL', '05': 'MAIO', '06': 'JUNHO',
                '07': 'JULHO', '08': 'AGOSTO', '09': 'SETEMBRO',
                '10': 'OUTUBRO', '11': 'NOVEMBRO', '12': 'DEZEMBRO'
            }

            pasta_conta = f"CONTA_{conta}"
            pasta_data = f"{ano}_{mes}_{meses_ext.get(mes, 'DESCONHECIDO')}"
            destino_final = self.diretorio_destino / pasta_conta / pasta_data / nome_novo

            contador = 1
            destino_original = destino_final
            while destino_final.exists():
                nome_base = destino_original.stem
                extensao = destino_original.suffix
                destino_final = destino_original.parent / f"{nome_base}_v{contador:02d}{extensao}"
                contador += 1

            resultado['arquivo_destino'] = str(destino_final)
            resultado['estrutura'] = f"{pasta_conta}/{pasta_data}"

            if not modo_teste:
                destino_final.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(arquivo), str(destino_final))
                resultado['acao'] = 'copiado'
            else:
                resultado['acao'] = 'simulado'

            resultado['sucesso'] = True
            self.stats['processados'] += 1
            self.stats['data_encontrada'] += 1
            self.stats['conta_encontrada'] += 1

        except Exception as e:
            resultado['erro'] = str(e)
            self.stats['erros'] += 1

        return resultado

    def organizar_arquivos(self, modo_teste: bool = True) -> Dict:
        """Organiza todos os arquivos"""
        arquivos = []
        for ext in ['*.pdf', '*.ofx']:
            arquivos.extend(self.diretorio_origem.rglob(ext))

        self.stats['total_arquivos'] = len(arquivos)
        relatorio = {
            'total_arquivos': len(arquivos),
            'processados_com_sucesso': 0,
            'erros': 0,
            'detalhes': [],
            'modo_teste': modo_teste,
            'metodo': 'LOCAL_AVANCADO',
            'inicio': datetime.now().isoformat()
        }

        for arquivo in arquivos:
            resultado = self.processar_arquivo(arquivo, modo_teste)
            relatorio['detalhes'].append(resultado)
            if resultado['sucesso']:
                relatorio['processados_com_sucesso'] += 1
            else:
                relatorio['erros'] += 1

        relatorio['fim'] = datetime.now().isoformat()
        relatorio['stats'] = self.stats
        return relatorio
