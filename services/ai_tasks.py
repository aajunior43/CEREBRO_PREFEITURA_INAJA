import json
from dataclasses import dataclass
from typing import Any

from services.ai_prompts import build_prompt, limit_text
from services.openrouter_service import AIServiceError, OpenRouterService, extract_json_block


@dataclass(frozen=True)
class TaskResult:
    content: str
    model: str
    cached: bool
    usage: dict[str, Any]
    provider_response: dict[str, Any]


class AITaskFacade:
    def __init__(self, service: OpenRouterService):
        self.service = service

    def gerar_texto_empenho(self, dados: dict[str, Any], acao: str = 'generate_description') -> TaskResult | dict[str, Any]:
        template_map = {
            'extract_fields': 'empenho_extract_fields',
            'generate_description': 'empenho_generate_description',
            'checklist': 'empenho_checklist',
            'improve_description': 'empenho_improve_description',
        }
        template_name = template_map.get(acao)
        if not template_name:
            raise ValueError('Ação inválida para assistente de empenho.')
        contexto = '\n'.join(self._ctx_lines(dados))
        response = self.service.chat_by_task(
            task_type='empenho',
            messages=build_prompt(template_name, contexto=contexto),
            temperature=0.3 if acao in {'generate_description', 'improve_description'} else 0.2,
            max_tokens=1400,
            use_cache=acao != 'checklist',
            metadata={'feature': 'empenho_assistente', 'action': acao},
        )
        text = response.text.strip().replace('**', '').replace('*', '')
        if acao == 'extract_fields':
            parsed = extract_json_block(text)
            if not isinstance(parsed, dict):
                raise AIServiceError('A IA retornou um formato inesperado para extração de campos.', user_message='Não foi possível interpretar a extração retornada pela IA.')
            parsed['pendencias'] = parsed.get('pendencias') if isinstance(parsed.get('pendencias'), list) else []
            return parsed
        if acao in {'generate_description', 'improve_description'}:
            text = text.upper()
            prefix = 'PELA DESPESA EMPENHADA REFERENTE A'
            if not text.startswith(prefix):
                text = f'{prefix} {text.lstrip()}'.strip()
        return TaskResult(
            content=text,
            model=response.model,
            cached=response.cached,
            usage=response.usage,
            provider_response=response.payload,
        )

    def analisar_documento(self, texto: str, use_cache: bool = True) -> TaskResult | dict[str, Any]:
        response = self.service.chat_by_task(
            task_type='auditoria_documento',
            messages=build_prompt('documento_analisar', texto=limit_text(texto, 12000)),
            temperature=0.1,
            max_tokens=1800,
            use_cache=use_cache,
            metadata={'feature': 'auditoria_documento'},
        )
        content = extract_json_block(response.text)
        return content if isinstance(content, dict) else TaskResult(response.text, response.model, response.cached, response.usage, response.payload)

    def categorizar_extrato(self, texto: str, use_cache: bool = True) -> TaskResult | dict[str, Any]:
        response = self.service.chat_by_task(
            task_type='extrato',
            messages=build_prompt('extrato_categorizar', texto=limit_text(texto, 9000)),
            temperature=0,
            max_tokens=500,
            use_cache=use_cache,
            metadata={'feature': 'categorizar_extrato'},
        )
        content = extract_json_block(response.text)
        return content if isinstance(content, dict) else TaskResult(response.text, response.model, response.cached, response.usage, response.payload)

    def sugerir_nome_arquivo(self, nome_arquivo: str, texto: str, use_cache: bool = True) -> TaskResult | dict[str, Any]:
        response = self.service.chat_by_task(
            task_type='renomeacao_arquivo',
            messages=build_prompt('arquivo_renomear', nome_arquivo=nome_arquivo, texto=limit_text(texto, 9000)),
            temperature=0,
            max_tokens=400,
            use_cache=use_cache,
            metadata={'feature': 'renomeacao_arquivo'},
        )
        content = extract_json_block(response.text)
        return content if isinstance(content, dict) else TaskResult(response.text, response.model, response.cached, response.usage, response.payload)

    def _ctx_lines(self, info: dict[str, Any]) -> list[str]:
        def clean(value: Any) -> str:
            return str(value or '').strip()

        lines = [
            '=== CONTEXTO DO EMPENHO ===',
            f"Secretaria/Setor: {clean(info.get('secretaria')) or 'Nao informado'}",
            f"Fornecedor/Credor: {clean(info.get('fornecedor')) or 'Nao informado'}",
            f"Tipo da despesa: {clean(info.get('tipo_despesa')) or 'Nao informado'}",
            f"Finalidade/necessidade: {clean(info.get('finalidade')) or 'Nao informado'}",
            f"Valor: {clean(info.get('valor')) or 'Nao informado'}",
            f"Competencia/periodo: {clean(info.get('competencia')) or 'Nao informado'}",
            f"Processo: {clean(info.get('processo')) or 'Nao informado'}",
            f"Pregao/licitacao: {clean(info.get('pregao')) or 'Nao informado'}",
            f"Contrato: {clean(info.get('contrato')) or 'Nao informado'}",
            f"Nota fiscal/OS/referencia: {clean(info.get('nota_fiscal')) or 'Nao informado'}",
        ]
        if clean(info.get('texto_base')):
            lines.extend(['', '=== TEXTO BASE / DOCUMENTO COLADO ===', clean(info.get('texto_base'))])
        if clean(info.get('descricao_atual')):
            lines.extend(['', '=== DESCRICAO ATUAL ===', clean(info.get('descricao_atual'))])
        return lines


def serialize_task_result(result: TaskResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    return {
        'content': result.content,
        'model': result.model,
        'cached': result.cached,
        'usage': result.usage,
        'provider_response': result.provider_response,
    }
