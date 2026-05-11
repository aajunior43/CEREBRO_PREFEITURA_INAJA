import hashlib
import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Iterable

import requests


class AIServiceError(Exception):
    def __init__(self, message: str, *, user_message: str | None = None, status_code: int = 500, code: str = 'ai_service_error', details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.user_message = user_message or 'O serviço de IA está indisponível no momento. Tente novamente em instantes.'
        self.status_code = status_code
        self.code = code
        self.details = details or {}

    def to_response(self) -> dict[str, Any]:
        return {'error': {'code': self.code, 'message': self.user_message, 'details': self.details}}


@dataclass(frozen=True)
class AIResponse:
    text: str
    model: str
    payload: dict[str, Any]
    usage: dict[str, Any]
    cached: bool
    latency_ms: float


@dataclass(frozen=True)
class ModelPolicy:
    primary: str
    fallbacks: tuple[str, ...]
    max_input_chars: int
    max_tokens: int
    prefer_free: bool = False


class TTLCache:
    def __init__(self, ttl_seconds: int = 600, max_entries: int = 256):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        now = time.time()
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at < now:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any):
        with self._lock:
            if len(self._store) >= self.max_entries:
                oldest_key = min(self._store, key=lambda current: self._store[current][0])
                self._store.pop(oldest_key, None)
            self._store[key] = (time.time() + self.ttl_seconds, value)


class OpenRouterService:
    _shared_rate_limit_until: dict[str, float] = {}
    _shared_rate_limit_lock = threading.Lock()

    def __init__(self, api_key: str, default_model: str, referer: str, title: str, logger: logging.Logger | None = None, timeout_seconds: int = 60, max_retries: int = 3, backoff_base: float = 1.5, cache_ttl_seconds: int = 900, default_headers: dict[str, str] | None = None, model_policies: dict[str, ModelPolicy] | None = None):
        self.api_key = (api_key or '').strip()
        self.default_model = default_model
        self.referer = referer
        self.title = title
        self.logger = logger or logging.getLogger(__name__)
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.default_headers = default_headers or {}
        self.cache = TTLCache(ttl_seconds=cache_ttl_seconds)
        self.model_policies = model_policies or build_default_model_policies(default_model)

    def chat_by_task(self, task_type: str, messages: list[dict[str, Any]], *, temperature: float = 0.2, max_tokens: int | None = None, use_cache: bool = True, response_format: dict[str, Any] | None = None, timeout_seconds: int | None = None, extra_payload: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, stream: bool = False) -> AIResponse:
        policy = self.model_policies.get(task_type) or self.model_policies['default']
        prepared_messages = self._truncate_messages(messages, policy.max_input_chars)
        models_to_try = self._build_model_chain(policy)
        final_max_tokens = min(max_tokens or policy.max_tokens, policy.max_tokens)
        payload_extra = dict(extra_payload or {})
        if response_format:
            payload_extra['response_format'] = response_format
        return self.chat_completion(messages=prepared_messages, models_to_try=models_to_try, temperature=temperature, max_tokens=final_max_tokens, use_cache=use_cache, timeout_seconds=timeout_seconds, extra_payload=payload_extra, metadata={'task_type': task_type, **(metadata or {})}, stream=stream)

    def chat_completion(self, *, messages: list[dict[str, Any]], models_to_try: Iterable[str] | None = None, temperature: float = 0.2, max_tokens: int = 1000, use_cache: bool = True, timeout_seconds: int | None = None, extra_payload: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None, stream: bool = False) -> AIResponse:
        self._validate_api_key()
        payload_extra = dict(extra_payload or {})
        models = [model for model in (models_to_try or [self.default_model]) if model] or [self.default_model]
        request_meta = metadata or {}
        cache_key = self._build_cache_key(messages, models, temperature, max_tokens, payload_extra)
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                self.logger.info('ia.cache_hit task=%s model=%s', request_meta.get('task_type', 'default'), cached.model)
                return AIResponse(cached.text, cached.model, cached.payload, cached.usage, True, 0.0)

        errors: list[AIServiceError] = []
        started_at = time.perf_counter()
        for model in models:
            if self._is_model_rate_limited(model):
                wait_seconds = self._seconds_until_model_released(model)
                errors.append(AIServiceError(
                    f'Modelo em cooldown por rate limit: {model}',
                    user_message=f'O modelo {model} está temporariamente em cooldown. Aguarde {wait_seconds}s.',
                    status_code=429,
                    code='rate_limit',
                    details={'retry_after': wait_seconds, 'model': model, 'cooldown_active': True},
                ))
                continue
            try:
                response = self._call_model(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens, timeout_seconds=timeout_seconds, extra_payload=payload_extra, stream=stream, metadata=request_meta)
                total_latency_ms = (time.perf_counter() - started_at) * 1000
                final_response = AIResponse(response.text, response.model, response.payload, response.usage, False, total_latency_ms)
                if use_cache:
                    self.cache.set(cache_key, final_response)
                return final_response
            except AIServiceError as exc:
                errors.append(exc)
                self.logger.warning('ia.fallback model=%s code=%s detail=%s', model, exc.code, exc.message)
                continue
        raise self._collapse_errors(errors)

    def list_models(self) -> list[dict[str, Any]]:
        self._validate_api_key()
        try:
            response = requests.get('https://openrouter.ai/api/v1/models', headers=self._build_headers(), timeout=min(self.timeout_seconds, 20))
            response.raise_for_status()
            data = response.json()
        except requests.Timeout as exc:
            raise AIServiceError('Timeout ao listar modelos.', user_message='A listagem de modelos demorou demais para responder.', status_code=504, code='timeout') from exc
        except requests.RequestException as exc:
            raise self._translate_request_exception(exc) from exc
        return data.get('data', []) if isinstance(data, dict) else []

    def _call_model(self, *, model: str, messages: list[dict[str, Any]], temperature: float, max_tokens: int, timeout_seconds: int | None, extra_payload: dict[str, Any], stream: bool, metadata: dict[str, Any]) -> AIResponse:
        payload = {'model': model, 'messages': messages, 'temperature': temperature, 'max_tokens': max_tokens, 'stream': stream}
        payload.update(extra_payload)
        self.logger.info('ia.request task=%s model=%s payload=%s', metadata.get('task_type', 'default'), model, json.dumps(self._safe_log_payload(payload), ensure_ascii=False))
        started_at = time.perf_counter()
        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post('https://openrouter.ai/api/v1/chat/completions', headers=self._build_headers(), json=payload, timeout=timeout_seconds or self.timeout_seconds)
                if response.status_code >= 400:
                    raise self._translate_http_error(response)
                data = response.json()
                text = extract_openrouter_text(data)
                usage = extract_usage(data)
                latency_ms = (time.perf_counter() - started_at) * 1000
                self.logger.info('ia.response task=%s model=%s latency_ms=%.1f usage=%s', metadata.get('task_type', 'default'), model, latency_ms, json.dumps(usage, ensure_ascii=False))
                return AIResponse(text=text, model=model, payload=data, usage=usage, cached=False, latency_ms=latency_ms)
            except AIServiceError as exc:
                if exc.status_code == 429:
                    self._mark_model_rate_limited(model, exc)
                if attempt >= self.max_retries or exc.status_code not in {408, 409, 425, 429, 500, 502, 503, 504}:
                    raise exc
                if exc.status_code == 429:
                    raise exc
                self._sleep_before_retry(attempt, exc.details.get('retry_after'))
            except requests.Timeout as exc:
                if attempt >= self.max_retries:
                    raise AIServiceError('Timeout ao chamar o modelo.', user_message='A IA demorou demais para responder. Tente novamente.', status_code=504, code='timeout') from exc
                self._sleep_before_retry(attempt)
            except requests.RequestException as exc:
                translated = self._translate_request_exception(exc)
                if attempt >= self.max_retries or translated.status_code < 500:
                    raise translated from exc
                self._sleep_before_retry(attempt)
            except ValueError as exc:
                raise AIServiceError(str(exc), user_message='A IA retornou uma resposta inválida. Tente novamente.', status_code=502, code='invalid_response') from exc
        raise AIServiceError('Falha inesperada ao chamar modelo.', status_code=500)

    def _build_model_chain(self, policy: ModelPolicy) -> list[str]:
        unique = []
        seen = set()
        for model in [policy.primary, *policy.fallbacks]:
            if model and model not in seen:
                seen.add(model)
                unique.append(model)
        return unique

    def _is_model_rate_limited(self, model: str) -> bool:
        now = time.time()
        with self._shared_rate_limit_lock:
            until = self._shared_rate_limit_until.get(model, 0.0)
            if until <= now:
                self._shared_rate_limit_until.pop(model, None)
                return False
            return True

    def _seconds_until_model_released(self, model: str) -> int:
        now = time.time()
        with self._shared_rate_limit_lock:
            until = self._shared_rate_limit_until.get(model, 0.0)
        return max(1, int(round(until - now))) if until > now else 0

    def _mark_model_rate_limited(self, model: str, exc: AIServiceError):
        cooldown_seconds = self._extract_retry_after_seconds(exc)
        with self._shared_rate_limit_lock:
            self._shared_rate_limit_until[model] = max(self._shared_rate_limit_until.get(model, 0.0), time.time() + cooldown_seconds)

    def _truncate_messages(self, messages: list[dict[str, Any]], max_chars: int) -> list[dict[str, Any]]:
        prepared = []
        for message in messages:
            item = dict(message)
            if isinstance(item.get('content'), str):
                item['content'] = item['content'][:max_chars]
            prepared.append(item)
        return prepared

    def _build_headers(self) -> dict[str, str]:
        headers = {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json', 'HTTP-Referer': self.referer, 'X-Title': self.title}
        headers.update(self.default_headers)
        return headers

    def _validate_api_key(self):
        if not self.api_key:
            raise AIServiceError('Chave da API OpenRouter ausente.', user_message='Chave do OpenRouter não configurada. Acesse ADM -> Configurações -> Chaves de API.', status_code=400, code='missing_api_key')

    def _build_cache_key(self, messages: list[dict[str, Any]], models: list[str], temperature: float, max_tokens: int, extra_payload: dict[str, Any]) -> str:
        canonical = json.dumps({'messages': messages, 'models': models, 'temperature': temperature, 'max_tokens': max_tokens, 'extra_payload': extra_payload}, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    def _safe_log_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        safe = dict(payload)
        safe['messages'] = [{**dict(message), 'content': (message.get('content')[:1200] if isinstance(message.get('content'), str) else message.get('content'))} for message in payload.get('messages', [])]
        return safe

    def _sleep_before_retry(self, attempt: int, retry_after: Any = None):
        if retry_after:
            try:
                time.sleep(min(float(retry_after), 10.0))
                return
            except (TypeError, ValueError):
                pass
        time.sleep(min(self.backoff_base ** attempt, 10.0))

    def _translate_http_error(self, response: requests.Response) -> AIServiceError:
        detail = parse_http_error_response(response)
        message = detail.get('error', {}).get('message') or detail.get('message') or f'Erro HTTP {response.status_code}'
        retry_after = response.headers.get('Retry-After') or response.headers.get('retry-after')
        details = {'provider_error': detail}
        if retry_after:
            details['retry_after'] = retry_after
        if response.status_code == 429:
            retry_after_seconds = self._extract_retry_after_seconds_from_message(message, retry_after=retry_after)
            details['retry_after'] = retry_after_seconds
            return AIServiceError(message, user_message=f'A IA está temporariamente sobrecarregada. Aguarde cerca de {retry_after_seconds}s e tente novamente.', status_code=429, code='rate_limit', details=details)
        if response.status_code in {400, 404, 422}:
            return AIServiceError(message, user_message='A solicitação para a IA não pôde ser processada.', status_code=response.status_code, code='invalid_request', details=details)
        if response.status_code in {401, 403}:
            return AIServiceError(message, user_message='Falha de autenticação com o provedor de IA. Verifique a chave configurada.', status_code=response.status_code, code='authentication_error', details=details)
        return AIServiceError(message, user_message='O provedor de IA apresentou instabilidade. Tente novamente em instantes.', status_code=response.status_code, code='provider_error', details=details)

    def _translate_request_exception(self, exc: requests.RequestException) -> AIServiceError:
        return AIServiceError(str(exc), user_message='Falha de comunicação com o serviço de IA. Verifique sua conexão e tente novamente.', status_code=502, code='network_error')

    def _collapse_errors(self, errors: list[AIServiceError]) -> AIServiceError:
        if not errors:
            return AIServiceError('Nenhum modelo disponível.', user_message='Nenhum modelo de IA está disponível no momento.', status_code=503, code='no_model_available')
        if all(error.code == 'rate_limit' for error in errors):
            retry_after_seconds = max((self._extract_retry_after_seconds(error) for error in errors), default=30)
            return AIServiceError('Todos os modelos retornaram limite de uso.', user_message=f'Todos os modelos gratuitos estão em cooldown ou sobrecarregados. Aguarde cerca de {retry_after_seconds}s e tente novamente.', status_code=429, code='all_models_rate_limited', details={'attempts': [error.details for error in errors], 'retry_after': retry_after_seconds})
        last = errors[-1]
        return AIServiceError(last.message, user_message=last.user_message, status_code=last.status_code, code=last.code, details={'attempts': [error.details for error in errors]})

    def _extract_retry_after_seconds(self, exc: AIServiceError) -> int:
        details = exc.details or {}
        retry_after = details.get('retry_after')
        try:
            if retry_after is not None:
                return max(1, min(int(float(retry_after)), 900))
        except (TypeError, ValueError):
            pass
        return self._extract_retry_after_seconds_from_message(exc.message)

    def _extract_retry_after_seconds_from_message(self, message: str, retry_after: Any = None) -> int:
        try:
            if retry_after is not None:
                return max(1, min(int(float(retry_after)), 900))
        except (TypeError, ValueError):
            pass
        text = (message or '').lower()
        if 'per-day' in text or 'por dia' in text:
            return 600
        if 'per-min' in text or 'por minuto' in text:
            return 90
        match = re.search(r'(\d+)\s*(s|sec|secs|seg|segundos|min|mins|minutos)', text)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            if unit.startswith('m'):
                return max(1, min(amount * 60, 900))
            return max(1, min(amount, 900))
        return 60


def build_default_model_policies(default_model: str) -> dict[str, ModelPolicy]:
    free_fallbacks = ('openrouter/free', 'google/gemma-3-27b-it:free', 'mistralai/mistral-small-3.1-24b-instruct:free', 'meta-llama/llama-3.2-3b-instruct:free')
    return {
        'default': ModelPolicy(primary=default_model, fallbacks=free_fallbacks, max_input_chars=12000, max_tokens=1200),
        'chat': ModelPolicy(primary='meta-llama/llama-3.3-70b-instruct:free', fallbacks=free_fallbacks, max_input_chars=12000, max_tokens=2000, prefer_free=True),
        'empenho': ModelPolicy(primary=default_model, fallbacks=free_fallbacks, max_input_chars=14000, max_tokens=1400),
        'auditoria_documento': ModelPolicy(primary=default_model, fallbacks=free_fallbacks, max_input_chars=15000, max_tokens=1800),
        'extrato': ModelPolicy(primary='google/gemma-3-27b-it:free', fallbacks=free_fallbacks, max_input_chars=9000, max_tokens=600, prefer_free=True),
        'renomeacao_arquivo': ModelPolicy(primary='google/gemma-3-27b-it:free', fallbacks=free_fallbacks, max_input_chars=9000, max_tokens=400, prefer_free=True),
    }


def build_openrouter_service(*, api_key: str, default_model: str, referer: str, title: str, logger: logging.Logger | None = None, timeout_seconds: int = 60, max_retries: int = 3, backoff_base: float = 1.5, cache_ttl_seconds: int = 900) -> OpenRouterService:
    return OpenRouterService(api_key=api_key, default_model=default_model, referer=referer, title=title, logger=logger, timeout_seconds=timeout_seconds, max_retries=max_retries, backoff_base=backoff_base, cache_ttl_seconds=cache_ttl_seconds)


def listar_modelos(api_key: str, timeout_seconds: int = 15, referer: str = 'https://localhost', title: str = 'CEREBRO_PREFEITURA') -> list[dict[str, Any]]:
    return build_openrouter_service(api_key=api_key, default_model='openrouter/free', referer=referer, title=title, timeout_seconds=timeout_seconds).list_models()


def chat_completion(api_key: str, model: str, messages: list[dict[str, Any]], max_tokens: int, temperature: float, referer: str, title: str, **kwargs) -> dict[str, Any]:
    service = build_openrouter_service(api_key=api_key, default_model=model, referer=referer, title=title, timeout_seconds=kwargs.pop('timeout_seconds', 60), max_retries=kwargs.pop('max_retries', 1), cache_ttl_seconds=1)
    response = service.chat_completion(messages=messages, models_to_try=[model], max_tokens=max_tokens, temperature=temperature, extra_payload=kwargs, use_cache=False)
    return response.payload


def parse_http_error(error) -> dict[str, Any]:
    if isinstance(error, requests.Response):
        return parse_http_error_response(error)
    body = ''
    headers = getattr(error, 'headers', {}) or {}
    if hasattr(error, 'read'):
        body = error.read().decode('utf-8', errors='replace')
    try:
        data = json.loads(body) if body else {}
    except Exception:
        data = {'message': body}
    retry_after = headers.get('Retry-After') or headers.get('retry-after')
    if retry_after:
        data['_retry_after'] = retry_after
    return data


def parse_http_error_response(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
        if isinstance(data, dict):
            return data
    except ValueError:
        pass
    return {'message': response.text}


def extract_openrouter_text(payload: dict[str, Any]) -> str:
    choices = payload.get('choices') or []
    if not choices:
        raise ValueError('A IA não retornou conteúdo.')
    message = choices[0].get('message') or {}
    content = message.get('content')
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'text':
                parts.append(item.get('text', ''))
        content = ''.join(parts)
    content = (content or '').strip()
    if not content:
        raise ValueError('A IA retornou conteúdo vazio.')
    return content


def extract_json_block(text: str):
    text = (text or '').strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    import re
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if match:
        return json.loads(match.group(1))
    start_obj = text.find('{')
    end_obj = text.rfind('}')
    if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
        try:
            return json.loads(text[start_obj:end_obj + 1])
        except Exception:
            pass
    start_arr = text.find('[')
    end_arr = text.rfind(']')
    if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
        return json.loads(text[start_arr:end_arr + 1])
    raise ValueError('A IA retornou um formato inválido.')


def extract_usage(payload: dict[str, Any]) -> dict[str, Any]:
    usage = payload.get('usage') or {}
    prompt_tokens = int(usage.get('prompt_tokens') or 0)
    completion_tokens = int(usage.get('completion_tokens') or 0)
    total_tokens = int(usage.get('total_tokens') or (prompt_tokens + completion_tokens))
    return {'prompt_tokens': prompt_tokens, 'completion_tokens': completion_tokens, 'total_tokens': total_tokens}
