#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Organizador com IA (OpenRouter) - estende OrganizadorLocalAvancado.
Usa conteúdo do arquivo (PDF/OFX) + IA para detecção. Fallback local para campos null.
Incorpora lógica do RENOMEADOR-DE-EXTRATO-PRO.
"""

import re
import shutil
from pathlib import Path

from services.openrouter_service import AIServiceError, build_openrouter_service, extract_json_block

from .organizador_local_avancado import OrganizadorLocalAvancado
from .file_processor import extrair_texto
from .prompts import montar_prompt, detectar_banco_no_texto


class OrganizadorIA(OrganizadorLocalAvancado):
    def __init__(self, diretorio_origem: str, diretorio_destino: str,
                 api_key: str, modelo: str = 'openai/gpt-4o-mini'):
        super().__init__(diretorio_origem, diretorio_destino)
        self.api_key = api_key
        self.modelo = modelo
        self.ai_service = build_openrouter_service(
            api_key=api_key,
            default_model=modelo,
            referer='http://localhost:5000',
            title='Organizador Extratos Inaja',
            logger=self.logger,
            timeout_seconds=20,
            max_retries=3,
            backoff_base=1.5,
            cache_ttl_seconds=900,
        )

    def _analisar_ia(self, arquivo: Path) -> dict:
        """
        Extrai texto do arquivo (se possível) e chama OpenRouter.
        Retorna dict com mes, ano, conta, banco, tipo_conta, confianca.
        """
        texto_conteudo = extrair_texto(arquivo)
        prompt = montar_prompt(arquivo.name, texto_conteudo)

        result = {"mes": None, "ano": None, "conta": None,
                  "banco": None, "tipo_conta": None, "confianca": 0.0}
        try:
            response = self.ai_service.chat_by_task(
                task_type='extrato',
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=150,
                use_cache=True,
                metadata={'feature': 'organizador_extratos', 'arquivo': arquivo.name},
            )
            parsed = extract_json_block(response.text)
            for k in result:
                if k in parsed and parsed[k] is not None:
                    result[k] = parsed[k]
        except AIServiceError as e:
            self.logger.warning(f"[IA] Erro controlado para '{arquivo.name}': {e.user_message}")
        except Exception as e:
            self.logger.warning(f"[IA] Erro para '{arquivo.name}': {e}")

        # Fallback: detectar banco no texto extraído se IA não encontrou
        if not result.get("banco") and texto_conteudo:
            result["banco"] = detectar_banco_no_texto(texto_conteudo)

        return result

    def processar_arquivo(self, arquivo: Path, modo_teste: bool = True) -> dict:
        """Processa arquivo usando IA (com leitura de conteúdo) e fallback local."""
        dados_ia = self._analisar_ia(arquivo)

        mes = dados_ia.get("mes")
        ano = dados_ia.get("ano")
        conta_raw = dados_ia.get("conta")
        banco = dados_ia.get("banco")
        tipo_conta = dados_ia.get("tipo_conta")
        confianca = dados_ia.get("confianca", 0.0)

        # Fallback local para campos não detectados pela IA
        if not mes or not ano:
            det_data = self.detectar_data(arquivo.name, str(arquivo.parent))
            if not mes:
                mes = det_data.get("mes")
            if not ano:
                ano = det_data.get("ano")

        if not conta_raw:
            conta_raw = self.detectar_conta(arquivo.name).get("conta")

        resultado = {
            'arquivo_original': str(arquivo),
            'nome_original': arquivo.name,
            'sucesso': False,
            'erro': None,
            'detalhes': {
                'data': {'mes': mes, 'ano': ano, 'encontrado': bool(mes and ano)},
                'conta': {'conta': conta_raw, 'metodo': 'IA+LOCAL',
                          'encontrado': bool(conta_raw and len(str(conta_raw)) >= 3)},
                'banco': banco,
                'tipo_conta': tipo_conta,
                'confianca': confianca,
            }
        }

        if not mes or not ano:
            resultado['erro'] = 'Data não identificada (IA + local)'
            return resultado
        if not conta_raw:
            resultado['erro'] = 'Conta não identificada (IA + local)'
            return resultado

        conta = re.sub(r'[^\w]', '', str(conta_raw))
        if len(conta) < 3:
            resultado['erro'] = f'Conta inválida: {conta_raw}'
            return resultado

        mes = str(mes).zfill(2)
        meses_ext = {
            '01': 'JANEIRO', '02': 'FEVEREIRO', '03': 'MARÇO',
            '04': 'ABRIL', '05': 'MAIO', '06': 'JUNHO',
            '07': 'JULHO', '08': 'AGOSTO', '09': 'SETEMBRO',
            '10': 'OUTUBRO', '11': 'NOVEMBRO', '12': 'DEZEMBRO'
        }

        tipo = "PDF" if arquivo.suffix.lower() == ".pdf" else "OFX"
        nome_novo = f"{ano}-{mes}_{conta}_{tipo}{arquivo.suffix.lower()}"
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
        resultado['detalhes']['conta']['conta'] = conta

        if not modo_teste:
            destino_final.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(arquivo), str(destino_final))
            resultado['acao'] = 'copiado'
        else:
            resultado['acao'] = 'simulado'

        resultado['sucesso'] = True
        resultado['metodo'] = 'IA_OPENROUTER'
        return resultado

