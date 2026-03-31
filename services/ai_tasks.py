import json
from dataclasses import dataclass
from typing import Any

from services.ai_prompts import build_prompt, limit_text
from services.openrouter_service import (
    AIServiceError,
    OpenRouterService,
    extract_json_block,
)


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

    def gerar_texto_empenho(
        self, dados: dict[str, Any], acao: str = "generate_description"
    ) -> TaskResult | dict[str, Any]:
        if acao == "review_bundle":
            return self.revisar_empenho(dados)

        template_map = {
            "extract_fields": "empenho_extract_fields",
            "generate_description": "empenho_generate_description",
            "checklist": "empenho_checklist",
            "improve_description": "empenho_improve_description",
        }
        template_name = template_map.get(acao)
        if not template_name:
            raise ValueError("Ação inválida para assistente de empenho.")
        contexto = "\n".join(self._ctx_lines(dados))
        response = self.service.chat_by_task(
            task_type="empenho",
            messages=build_prompt(template_name, contexto=contexto),
            temperature=0.3
            if acao in {"generate_description", "improve_description"}
            else 0.2,
            max_tokens=1400,
            use_cache=acao != "checklist",
            metadata={"feature": "empenho_assistente", "action": acao},
        )
        text = response.text.strip().replace("**", "").replace("*", "")
        if acao == "extract_fields":
            parsed = extract_json_block(text)
            if not isinstance(parsed, dict):
                raise AIServiceError(
                    "A IA retornou um formato inesperado para extração de campos.",
                    user_message="Não foi possível interpretar a extração retornada pela IA.",
                )
            parsed["pendencias"] = (
                parsed.get("pendencias")
                if isinstance(parsed.get("pendencias"), list)
                else []
            )
            return parsed
        if acao == "checklist":
            parsed = extract_json_block(text)
            if isinstance(parsed, dict):
                parsed["itens"] = (
                    parsed.get("itens") if isinstance(parsed.get("itens"), list) else []
                )
                parsed["pendencias"] = (
                    parsed.get("pendencias")
                    if isinstance(parsed.get("pendencias"), list)
                    else []
                )
                return parsed
        if acao in {"generate_description", "improve_description"}:
            text = text.upper()
            prefix = "PELA DESPESA EMPENHADA REFERENTE A"
            if not text.startswith(prefix):
                text = f"{prefix} {text.lstrip()}".strip()
        return TaskResult(
            content=text,
            model=response.model,
            cached=response.cached,
            usage=response.usage,
            provider_response=response.payload,
        )

    def revisar_empenho(self, dados: dict[str, Any]) -> dict[str, Any]:
        campos = self.gerar_texto_empenho(dados, acao="extract_fields")
        checklist = self.gerar_texto_empenho(dados, acao="checklist")
        descricao_base = self.gerar_texto_empenho(dados, acao="generate_description")
        contexto_melhorado = dict(dados)
        if isinstance(descricao_base, TaskResult):
            contexto_melhorado["descricao_atual"] = descricao_base.content
        descricao_melhorada = self.gerar_texto_empenho(
            contexto_melhorado, acao="improve_description"
        )

        return {
            "campos": campos,
            "checklist": checklist
            if isinstance(checklist, dict)
            else {
                "resumo": "",
                "itens": [checklist.content]
                if isinstance(checklist, TaskResult)
                else [str(checklist)],
                "pendencias": [],
                "prioridade": "",
            },
            "descricao_base": descricao_base.content
            if isinstance(descricao_base, TaskResult)
            else descricao_base,
            "descricao_melhorada": descricao_melhorada.content
            if isinstance(descricao_melhorada, TaskResult)
            else descricao_melhorada,
            "descricao_atual": contexto_melhorado.get("descricao_atual", ""),
        }

    def analisar_documento(
        self, texto: str, use_cache: bool = True
    ) -> TaskResult | dict[str, Any]:
        response = self.service.chat_by_task(
            task_type="auditoria_documento",
            messages=build_prompt("documento_analisar", texto=limit_text(texto, 12000)),
            temperature=0.1,
            max_tokens=1800,
            use_cache=use_cache,
            metadata={"feature": "auditoria_documento"},
        )
        content = extract_json_block(response.text)
        return (
            content
            if isinstance(content, dict)
            else TaskResult(
                response.text,
                response.model,
                response.cached,
                response.usage,
                response.payload,
            )
        )

    def categorizar_extrato(
        self, texto: str, use_cache: bool = True
    ) -> TaskResult | dict[str, Any]:
        response = self.service.chat_by_task(
            task_type="extrato",
            messages=build_prompt("extrato_categorizar", texto=limit_text(texto, 9000)),
            temperature=0,
            max_tokens=500,
            use_cache=use_cache,
            metadata={"feature": "categorizar_extrato"},
        )
        content = extract_json_block(response.text)
        return (
            content
            if isinstance(content, dict)
            else TaskResult(
                response.text,
                response.model,
                response.cached,
                response.usage,
                response.payload,
            )
        )

    def classificar_despesa(
        self, item: str, use_cache: bool = True, web_context: str = ""
    ) -> TaskResult | dict[str, Any]:
        contexto_extra = ""
        if web_context:
            contexto_extra = f"\n\n{web_context}"
        response = self.service.chat_by_task(
            task_type="classificacao_despesa",
            messages=build_prompt(
                "classificador_despesa", item=limit_text(item, 2000) + contexto_extra
            ),
            temperature=0.1,
            max_tokens=800,
            use_cache=use_cache,
            metadata={"feature": "classificador_despesa"},
        )
        content = extract_json_block(response.text)
        if isinstance(content, dict):
            content["_model"] = response.model
            content["_cached"] = response.cached
            content = self._validate_classificacao(item, content)
            return content
        return TaskResult(
            response.text,
            response.model,
            response.cached,
            response.usage,
            response.payload,
        )

    def _validate_classificacao(self, item: str, result: dict) -> dict:
        """Validação e normalização pós-processamento."""
        result = self._normalize_fields(result)
        item_lower = item.lower()
        subel = result.get("subelemento_codigo", "") or ""
        grupo = (result.get("grupo", "") or "").lower()

        veiculos_keywords = [
            "carro",
            "veículo",
            "veiculo",
            "automóvel",
            "automovel",
            "caminhão",
            "caminhao",
            "moto",
            "motocicleta",
            "ambulância",
            "ambulancia",
            "ônibus",
            "onibus",
            "van",
            "caminhonete",
            "picape",
            "utilitário",
            "utilitario",
            "viatura",
        ]
        is_veiculo = any(kw in item_lower for kw in veiculos_keywords)

        combustivel_keywords = [
            "combustível",
            "combustivel",
            "gasolina",
            "diesel",
            "etanol",
            "álcool",
            "alcool",
            "lubrificante",
            "óleo",
            "oleo",
        ]
        is_combustivel = any(kw in item_lower for kw in combustivel_keywords)

        servicos_pf_keywords = [
            "diária",
            "diaria",
            "indenização",
            "indenizacao",
            "passagens",
            "hospedagem",
        ]
        is_servico_pf = any(kw in item_lower for kw in servicos_pf_keywords)

        if is_veiculo and not subel.startswith("4.4.90.52"):
            result["grupo"] = "Investimento"
            result["modalidade"] = "Aplicação Direta"
            result["elemento"] = "52"
            result["subelemento_codigo"] = "4.4.90.52"
            result["subelemento_nome"] = "Equipamentos e Material Permanente"
            result["codigo_completo"] = "4.4.90.52"
            result["justificativa"] = (
                "Veículos são bens permanentes com vida útil superior a 2 anos, "
                "não incorporados a imóveis, conforme Portaria STN nº 448/2002 e MCASP. "
                "Classificação correta: GND 4 (Investimento), Elemento 52, "
                "Subelemento 4.4.90.52 — Equipamentos e Material Permanente."
            )
            result["confianca"] = 0.95
            result["_auto_corrected"] = True

        if is_combustivel and not subel.startswith("3.3.90.30"):
            result["grupo"] = "Custeio"
            result["modalidade"] = "Aplicação Direta"
            result["elemento"] = "30"
            result["subelemento_codigo"] = "3.3.90.30"
            result["subelemento_nome"] = "Material de Consumo"
            result["codigo_completo"] = "3.3.90.30"
            result["justificativa"] = (
                "Combustíveis e lubrificantes são materiais de consumo conforme "
                "Portaria STN nº 448/2002, sendo consumidos imediatamente no uso. "
                "Classificação: GND 3 (Custeio), Elemento 30, Subelemento 3.3.90.30 — Material de Consumo."
            )
            result["confianca"] = 0.95
            result["_auto_corrected"] = True

        if is_servico_pf and not subel.startswith("3.3.90.36"):
            result["grupo"] = "Custeio"
            result["modalidade"] = "Aplicação Direta"
            result["elemento"] = "36"
            result["subelemento_codigo"] = "3.3.90.36"
            result["subelemento_nome"] = "Pessoa Física"
            result["codigo_completo"] = "3.3.90.36"
            result["justificativa"] = (
                "Diárias e indenizações a pessoa física sem vínculo empregatício "
                "são classificadas no Elemento 36. Classificação: GND 3 (Custeio), "
                "Elemento 36, Subelemento 3.3.90.36 — Serviços de Terceiros, Pessoa Física."
            )
            result["confianca"] = 0.95
            result["_auto_corrected"] = True

        return result

    def _normalize_fields(self, result: dict) -> dict:
        """Normaliza campos que a IA pode ter trocado."""
        subel = result.get("subelemento_codigo", "") or ""
        elemento = (result.get("elemento", "") or "").strip()
        grupo = (result.get("grupo", "") or "").strip()
        modalidade = (result.get("modalidade", "") or "").strip()

        # Mapa de subelemento -> valores corretos
        subel_map = {
            "3.3.90.30": {
                "grupo": "Custeio",
                "modalidade": "Aplicação Direta",
                "elemento": "30",
                "subelemento_nome": "Material de Consumo",
            },
            "3.3.90.36": {
                "grupo": "Custeio",
                "modalidade": "Aplicação Direta",
                "elemento": "36",
                "subelemento_nome": "Pessoa Física",
            },
            "3.3.90.39": {
                "grupo": "Custeio",
                "modalidade": "Aplicação Direta",
                "elemento": "39",
                "subelemento_nome": "Pessoa Jurídica",
            },
            "4.4.90.51": {
                "grupo": "Investimento",
                "modalidade": "Aplicação Direta",
                "elemento": "51",
                "subelemento_nome": "Obras e Instalações",
            },
            "4.4.90.52": {
                "grupo": "Investimento",
                "modalidade": "Aplicação Direta",
                "elemento": "52",
                "subelemento_nome": "Equipamentos e Material Permanente",
            },
        }

        # Se o subelemento está correto mas os outros campos estão trocados, normaliza
        if subel in subel_map:
            expected = subel_map[subel]
            # Verifica se os campos estão errados (ex: grupo="4", modalidade="4.4")
            if grupo in ("3", "4", "3.3", "4.4") or modalidade in (
                "3.3",
                "4.4",
                "3",
                "4",
            ):
                result["grupo"] = expected["grupo"]
                result["modalidade"] = expected["modalidade"]
                result["elemento"] = expected["elemento"]
                result["subelemento_nome"] = expected["subelemento_nome"]

        # Garante que codigo_completo == subelemento_codigo
        if subel and result.get("codigo_completo") != subel:
            result["codigo_completo"] = subel

        # Normaliza elemento para apenas 2 dígitos
        if elemento and len(elemento) > 2 and "." in elemento:
            parts = elemento.split(".")
            if len(parts) >= 4:
                result["elemento"] = parts[3]

        return result

    def sugerir_nome_arquivo(
        self, nome_arquivo: str, texto: str, use_cache: bool = True
    ) -> TaskResult | dict[str, Any]:
        response = self.service.chat_by_task(
            task_type="renomeacao_arquivo",
            messages=build_prompt(
                "arquivo_renomear",
                nome_arquivo=nome_arquivo,
                texto=limit_text(texto, 9000),
            ),
            temperature=0,
            max_tokens=400,
            use_cache=use_cache,
            metadata={"feature": "renomeacao_arquivo"},
        )
        content = extract_json_block(response.text)
        return (
            content
            if isinstance(content, dict)
            else TaskResult(
                response.text,
                response.model,
                response.cached,
                response.usage,
                response.payload,
            )
        )

    def _ctx_lines(self, info: dict[str, Any]) -> list[str]:
        def clean(value: Any) -> str:
            return str(value or "").strip()

        lines = [
            "=== CONTEXTO DO EMPENHO ===",
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
        if clean(info.get("texto_base")):
            lines.extend(
                [
                    "",
                    "=== TEXTO BASE / DOCUMENTO COLADO ===",
                    clean(info.get("texto_base")),
                ]
            )
        if clean(info.get("descricao_atual")):
            lines.extend(
                ["", "=== DESCRICAO ATUAL ===", clean(info.get("descricao_atual"))]
            )
        return lines


def serialize_task_result(result: TaskResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    return {
        "content": result.content,
        "model": result.model,
        "cached": result.cached,
        "usage": result.usage,
        "provider_response": result.provider_response,
    }
