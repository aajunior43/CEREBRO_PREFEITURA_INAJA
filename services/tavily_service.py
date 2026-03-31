"""Serviço de busca web via Tavily Search API."""

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests


class TavilyError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class TavilyResult:
    title: str
    url: str
    content: str
    score: float


class TavilyService:
    """Wrapper para a API Tavily Search."""

    BASE_URL = "https://api.tavily.com/search"

    def __init__(
        self,
        api_key: str,
        logger: logging.Logger | None = None,
        timeout: int = 15,
    ):
        self.api_key = (api_key or "").strip()
        self.logger = logger or logging.getLogger(__name__)
        self.timeout = timeout

    def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[TavilyResult]:
        """Executa busca web e retorna resultados formatados."""
        if not self.api_key:
            raise TavilyError("Chave da API Tavily não configurada.")
        if not query:
            return []

        payload: dict[str, Any] = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": False,
            "include_raw_content": False,
        }
        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        started_at = time.perf_counter()
        try:
            resp = requests.post(
                self.BASE_URL,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            elapsed_ms = (time.perf_counter() - started_at) * 1000

            if resp.status_code >= 400:
                error_msg = self._extract_error(resp)
                raise TavilyError(
                    f"Tavily API error: {error_msg}",
                    status_code=resp.status_code,
                )

            data = resp.json()
            results = []
            for item in data.get("results", []):
                results.append(
                    TavilyResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        content=item.get("content", ""),
                        score=item.get("score", 0.0),
                    )
                )

            self.logger.info(
                "tavily.search query=%s results=%d elapsed_ms=%.1f",
                query[:80],
                len(results),
                elapsed_ms,
            )
            return results

        except requests.Timeout:
            raise TavilyError(
                "Timeout na busca Tavily.",
                status_code=504,
            )
        except requests.RequestException as exc:
            raise TavilyError(
                f"Falha de comunicação com Tavily: {exc}",
                status_code=502,
            )

    def search_as_context(
        self,
        query: str,
        max_results: int = 3,
    ) -> str:
        """Busca e retorna texto consolidado para usar como contexto da IA."""
        results = self.search(query, max_results=max_results)
        if not results:
            return ""

        lines = ["=== CONTEXTO WEB (TAVILY) ==="]
        for i, r in enumerate(results, 1):
            lines.append(f"[{i}] {r.title}")
            lines.append(f"    Fonte: {r.url}")
            lines.append(f"    {r.content}")
            lines.append("")
        return "\n".join(lines)

    def _extract_error(self, resp: requests.Response) -> str:
        try:
            data = resp.json()
            return data.get("detail") or data.get("message") or resp.text[:200]
        except Exception:
            return resp.text[:200] or f"Erro HTTP {resp.status_code}"


def build_tavily_service(
    api_key: str,
    logger: logging.Logger | None = None,
) -> TavilyService:
    return TavilyService(api_key=api_key, logger=logger)
