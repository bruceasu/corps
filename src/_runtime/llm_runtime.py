import os
import json
import random
import requests
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    # Fallback for environments where openai is not yet installed
    OpenAI = None


class LlmErrorKind(str, Enum):
    """Stable failure categories used by the invocation policy."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    INVALID_REQUEST = "invalid_request"
    MODEL_UNAVAILABLE = "model_unavailable"
    RATE_LIMIT = "rate_limit"
    TRANSIENT = "transient"
    CANCELLED = "cancelled"
    SAFETY = "safety"
    MALFORMED_RESPONSE = "malformed_response"
    UNKNOWN = "unknown"


class LlmInvocationError(RuntimeError):
    """An invocation error with a policy-relevant classification."""

    def __init__(self, message: str, kind: LlmErrorKind = LlmErrorKind.UNKNOWN, retry_after: Optional[float] = None):
        super().__init__(message)
        self.kind = kind
        self.retry_after = retry_after


@dataclass(frozen=True)
class LlmMessage:
    role: str
    content: str


@dataclass(frozen=True)
class GenerationProfile:
    """Provider-neutral generation settings owned by a caller's task type."""

    name: str = "default"
    temperature: float = 0.0
    max_output_tokens: Optional[int] = None
    structured_output: bool = False


@dataclass(frozen=True)
class FallbackPolicy:
    """A request must opt in before the runtime can rotate providers."""

    allow_rotation: bool = False
    max_retries: int = 0
    retry_delay_seconds: float = 0.5


@dataclass(frozen=True)
class StructuredOutputContract:
    """A provider-neutral JSON-object contract for executable LLM output."""

    name: str
    required_keys: List[str] = field(default_factory=list)
    schema: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class LlmRequest:
    provider: str
    model: str
    messages: List[LlmMessage]
    profile: GenerationProfile = field(default_factory=GenerationProfile)
    fallback: FallbackPolicy = field(default_factory=FallbackPolicy)
    output_contract: Optional[StructuredOutputContract] = None

    @classmethod
    def from_prompt(
        cls,
        provider: str,
        model: str,
        prompt: str,
        system_prompt: str = "",
        profile: Optional[GenerationProfile] = None,
        fallback: Optional[FallbackPolicy] = None,
        output_contract: Optional[StructuredOutputContract] = None,
    ) -> "LlmRequest":
        messages: List[LlmMessage] = []
        if system_prompt.strip():
            messages.append(LlmMessage("system", system_prompt))
        messages.append(LlmMessage("user", prompt))
        return cls(provider, model, messages, profile or GenerationProfile(), fallback or FallbackPolicy(), output_contract)

    @property
    def system_prompt(self) -> str:
        return "\n".join(message.content for message in self.messages if message.role == "system")

    @property
    def user_prompt(self) -> str:
        return "\n".join(message.content for message in self.messages if message.role != "system")


@dataclass
class LlmResult:
    text: str
    provider: str
    model: str
    latency_ms: int
    finish_reason: str = "unknown"
    usage: Dict[str, int] = field(default_factory=dict)
    request_id: str = ""
    retry_trace: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ProviderResponse:
    """Raw adapter result before the runtime applies invocation policy."""

    text: str
    provider: str
    model: str
    finish_reason: str = "unknown"
    usage: Dict[str, int] = field(default_factory=dict)
    request_id: str = ""


_REQUESTS_SESSION = requests.Session()
_OPENAI_CLIENTS: Dict[tuple[str, str], Any] = {}


def _timeout_seconds() -> float:
    try:
        return max(1.0, float(os.getenv("CORPS_LLM_TIMEOUT_SECONDS", "120")))
    except ValueError:
        return 120.0


def _request_headers(response: Any) -> str:
    headers = getattr(response, "headers", {}) or {}
    return str(headers.get("x-request-id") or headers.get("request-id") or "")


def _usage_dict(usage: Any) -> Dict[str, int]:
    if usage is None:
        return {}
    values: Dict[str, int] = {}
    for source, target in (("prompt_tokens", "input_tokens"), ("completion_tokens", "output_tokens"), ("total_tokens", "total_tokens")):
        value = getattr(usage, source, None)
        if value is None and isinstance(usage, dict):
            value = usage.get(source)
        if isinstance(value, int):
            values[target] = value
    return values


def classify_exception(exc: BaseException) -> LlmErrorKind:
    """Classify common provider failures without coupling callers to an SDK."""
    if isinstance(exc, KeyboardInterrupt):
        return LlmErrorKind.CANCELLED
    if isinstance(exc, requests.Timeout) or isinstance(exc, requests.ConnectionError):
        return LlmErrorKind.TRANSIENT

    status_code = getattr(exc, "status_code", None)
    if status_code in {401}:
        return LlmErrorKind.AUTHENTICATION
    if status_code in {403}:
        return LlmErrorKind.AUTHORIZATION
    if status_code == 429:
        return LlmErrorKind.RATE_LIMIT
    if status_code is not None and 500 <= status_code < 600:
        return LlmErrorKind.TRANSIENT
    if status_code in {400, 404, 422}:
        return LlmErrorKind.INVALID_REQUEST

    message = str(exc).lower()
    if "missing api key" in message or "authentication" in message or "unauthorized" in message:
        return LlmErrorKind.AUTHENTICATION
    if "forbidden" in message or "permission" in message:
        return LlmErrorKind.AUTHORIZATION
    if "rate limit" in message or "too many requests" in message:
        return LlmErrorKind.RATE_LIMIT
    if "model" in message and ("not found" in message or "unavailable" in message):
        return LlmErrorKind.MODEL_UNAVAILABLE
    if "invalid" in message or "bad request" in message:
        return LlmErrorKind.INVALID_REQUEST
    return LlmErrorKind.UNKNOWN

class ModelRotator:
    COOLDOWN_DURATION = 3600  # 1 hour
    COOLDOWN_FILE = Path.home() / ".config" / "corps" / "model_cooldowns.json"

    def __init__(self):
        self.rotation_list = [
            {"provider": "gemini", "model": "gemini-3.5-flash"},
            {"provider": "gemini", "model": "gemini-2.5-flash"},
            {"provider": "groq", "model": "qwen/qwen3-32b"},
            {"provider": "groq", "model": "llama-3.3-70b-versatile"},
            {"provider": "gemini", "model": "gemini-3.1-flash-lite"},
            {"provider": "gemini", "model": "gemma-4-31b-it"},
            {"provider": "groq", "model": "llama-3.1-8b-instant"},
            {"provider": "gemini", "model": "gemma-4-26b-it"},
            {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
        ]
        self.cooldowns = {}
        self._load_cooldowns()

    def _load_cooldowns(self):
        if self.COOLDOWN_FILE.exists():
            try:
                with open(self.COOLDOWN_FILE, "r", encoding="utf-8") as f:
                    self.cooldowns = json.load(f)
            except:
                self.cooldowns = {}
        else:
            self.cooldowns = {}

    def _save_cooldowns(self):
        try:
            self.COOLDOWN_FILE.parent.mkdir(parents=True, exist_ok=True)
            temporary_file = self.COOLDOWN_FILE.with_suffix(".tmp")
            with open(temporary_file, "w", encoding="utf-8") as f:
                json.dump(self.cooldowns, f)
            os.replace(temporary_file, self.COOLDOWN_FILE)
        except:
            pass

    def mark_cooldown(self, provider: str, model: str, error_kind: LlmErrorKind = LlmErrorKind.TRANSIENT):
        key = f"{provider}:{model}"
        self.cooldowns[key] = {"at": time.time(), "errorKind": error_kind.value}
        self._save_cooldowns()

    def get_available_models(self) -> List[Dict[str, str]]:
        now = time.time()
        available = []
        for item in self.rotation_list:
            key = f"{item['provider']}:{item['model']}"
            cooldown = self.cooldowns.get(key, 0)
            last_fail = cooldown.get("at", 0) if isinstance(cooldown, dict) else cooldown
            if now - last_fail > self.COOLDOWN_DURATION:
                available.append(item)
        return available

_rotator = ModelRotator()

def get_rotator():
    return _rotator

def call_anthropic_response(api_key: str, model: str, prompt: str, system_prompt: str = "") -> ProviderResponse:
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    body = {
        "model": model,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_prompt.strip():
        body["system"] = system_prompt
        
    response = _REQUESTS_SESSION.post(url, headers=headers, json=body, timeout=_timeout_seconds())
    response.raise_for_status()
    payload = response.json()
    
    content = payload.get("content") or []
    text = str(content[0].get("text") or "") if content else ""
    usage = payload.get("usage") or {}
    return ProviderResponse(
        text=text,
        provider="anthropic",
        model=str(payload.get("model") or model),
        finish_reason=str(payload.get("stop_reason") or "unknown"),
        usage={key: value for key, value in usage.items() if isinstance(value, int)},
        request_id=_request_headers(response),
    )


def call_anthropic(api_key: str, model: str, prompt: str, system_prompt: str = "") -> str:
    return call_anthropic_response(api_key, model, prompt, system_prompt).text

def call_gemini_response(api_key: str, model: str, prompt: str, system_prompt: str = "") -> ProviderResponse:
    # Native Gemini API via requests
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ]
    }
    if system_prompt.strip():
        body["system_instruction"] = {
            "parts": [{"text": system_prompt}]
        }
        
    response = _REQUESTS_SESSION.post(url, headers=headers, json=body, timeout=_timeout_seconds())
    if response.status_code != 200:
        # Fallback for models that might not support system_instruction
        if "system_instruction" in response.text:
            new_prompt = f"System Instruction:\n{system_prompt}\n\nUser Prompt:\n{prompt}"
            body = {
                "contents": [{"role": "user", "parts": [{"text": new_prompt}]}]
            }
            response = _REQUESTS_SESSION.post(url, headers=headers, json=body, timeout=_timeout_seconds())
        
    response.raise_for_status()
    payload = response.json()
    
    candidates = payload.get("candidates") or []
    candidate = candidates[0] if candidates else {}
    content = candidate.get("content") or {}
    parts = content.get("parts") or []
    text = str(parts[0].get("text") or "") if parts else ""
    usage = payload.get("usageMetadata") or {}
    normalized_usage = {
        "input_tokens": value for key, value in usage.items()
        if key == "promptTokenCount" and isinstance(value, int)
    }
    normalized_usage.update({
        "output_tokens": value for key, value in usage.items()
        if key == "candidatesTokenCount" and isinstance(value, int)
    })
    normalized_usage.update({
        "total_tokens": value for key, value in usage.items()
        if key == "totalTokenCount" and isinstance(value, int)
    })
    return ProviderResponse(
        text=text,
        provider="gemini",
        model=model,
        finish_reason=str(candidate.get("finishReason") or "unknown"),
        usage=normalized_usage,
        request_id=_request_headers(response),
    )


def call_gemini(api_key: str, model: str, prompt: str, system_prompt: str = "") -> str:
    return call_gemini_response(api_key, model, prompt, system_prompt).text

def _generate_single_llm(provider: str, model: str, prompt: str, system_prompt: str = "") -> str:
    provider_name = (provider or "openai").strip().lower()
    
    # 1. Handle Anthropic and Gemini natively
    if provider_name == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key.strip():
            raise ValueError("Missing ANTHROPIC_API_KEY")
        if not model:
            model = "claude-3-sonnet-20240229"
        return call_anthropic(api_key, model, prompt, system_prompt)
    
    if provider_name == "gemini":
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key.strip():
            raise ValueError("Missing GEMINI_API_KEY")
        if not model or model in ["gemini", "gemini-pro"]:
            model = "gemini-1.5-pro"
        return call_gemini(api_key, model, prompt, system_prompt)

    # 2. Handle others using OpenAI client
    if provider_name == "groq":
        api_key = os.getenv("GROQ_API_KEY", "")
        base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        if not model:
            model = "mixtral-8x7b-32768"
    elif provider_name == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        if not model:
            model = "deepseek-chat"
    elif provider_name == "ollama":
        api_key = os.getenv("OLLAMA_API_KEY", "ollama")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        # Ensure base_url has /v1 if it's the standard Ollama port
        if base_url.endswith(":11434"):
            base_url += "/v1"
        if not model:
            model = "qwen2.5:7b"
    else:
        # Default to OpenAI
        api_key = os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        if not model:
            model = "gpt-4o"

    if not api_key.strip():
        raise ValueError(f"Missing API key for provider: {provider_name}")

    if not OpenAI:
        raise ImportError("openai package is not installed")

    client = OpenAI(api_key=api_key, base_url=base_url)
    
    messages = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
    )
    
    if not response.choices:
        return ""
    return str(response.choices[0].message.content or "")


def _generate_single_response(
    provider: str,
    model: str,
    prompt: str,
    system_prompt: str = "",
    output_contract: Optional[StructuredOutputContract] = None,
) -> ProviderResponse:
    """Adapter path that retains provider metadata for normalized callers."""
    provider_name = (provider or "openai").strip().lower()
    if provider_name == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key.strip():
            raise ValueError("Missing ANTHROPIC_API_KEY")
        selected_model = model or "claude-3-sonnet-20240229"
        return call_anthropic_response(api_key, selected_model, prompt, system_prompt)
    if provider_name == "gemini":
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key.strip():
            raise ValueError("Missing GEMINI_API_KEY")
        selected_model = model if model and model not in ["gemini", "gemini-pro"] else "gemini-1.5-pro"
        return call_gemini_response(api_key, selected_model, prompt, system_prompt)

    if provider_name == "groq":
        api_key = os.getenv("GROQ_API_KEY", "")
        base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        selected_model = model or "mixtral-8x7b-32768"
    elif provider_name == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        selected_model = model or "deepseek-chat"
    elif provider_name == "ollama":
        api_key = os.getenv("OLLAMA_API_KEY", "ollama")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        if base_url.endswith(":11434"):
            base_url += "/v1"
        selected_model = model or "qwen2.5:7b"
    else:
        api_key = os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        selected_model = model or "gpt-4o"

    if not api_key.strip():
        raise ValueError(f"Missing API key for provider: {provider_name}")
    if not OpenAI:
        raise ImportError("openai package is not installed")

    client_key = (api_key, base_url)
    client = _OPENAI_CLIENTS.get(client_key)
    if client is None:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=_timeout_seconds())
        _OPENAI_CLIENTS[client_key] = client
    messages = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    create_args: Dict[str, Any] = {
        "model": selected_model,
        "messages": messages,
        "temperature": 0,
    }
    # OpenAI supports native JSON Schema constrained output. Other compatible
    # endpoints are deliberately left on the validated fallback unless their
    # capability is explicitly modelled by a future adapter.
    if provider_name == "openai" and output_contract and output_contract.schema:
        create_args["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": output_contract.name.replace(" ", "_")[:64],
                "strict": True,
                "schema": output_contract.schema,
            },
        }
    response = client.chat.completions.create(**create_args)
    choice = response.choices[0] if response.choices else None
    return ProviderResponse(
        text=str(choice.message.content or "") if choice else "",
        provider=provider_name,
        model=selected_model,
        finish_reason=str(choice.finish_reason or "unknown") if choice else "unknown",
        usage=_usage_dict(getattr(response, "usage", None)),
        request_id=str(getattr(response, "_request_id", "") or ""),
    )

_last_used_info = {"provider": "unknown", "model": "unknown"}

def get_last_used_model_info() -> Dict[str, str]:
    return _last_used_info

def skip_current_model():
    global _last_used_info
    if _last_used_info["provider"] != "unknown":
        _rotator.mark_cooldown(_last_used_info["provider"], _last_used_info["model"])
        return _last_used_info
    return None


def invoke_llm(request: LlmRequest) -> LlmResult:
    """Invoke one provider through the normalized runtime seam.

    Explicit requests stay on their requested provider. The caller must opt
    in through its fallback policy before retrying or rotating candidates.
    """
    started = time.monotonic()
    requested_rotation = request.provider == "rotation" or request.model == "rotation"
    if requested_rotation and not request.fallback.allow_rotation:
        raise LlmInvocationError(
            "Rotation requires FallbackPolicy(allow_rotation=True)",
            LlmErrorKind.INVALID_REQUEST,
        )

    candidates: List[Dict[str, str]] = []
    if not requested_rotation:
        candidates.append({"provider": request.provider, "model": request.model})
    if request.fallback.allow_rotation:
        for candidate in _rotator.get_available_models():
            if candidate not in candidates:
                candidates.append(candidate)
    if not candidates:
        raise LlmInvocationError("No eligible rotation candidates", LlmErrorKind.MODEL_UNAVAILABLE)

    retry_trace: List[Dict[str, str]] = []
    last_error: Optional[LlmInvocationError] = None
    for candidate in candidates:
        for attempt in range(request.fallback.max_retries + 1):
            try:
                provider_response = _generate_single_response(
                    candidate["provider"],
                    candidate["model"],
                    request.user_prompt,
                    request.system_prompt,
                    request.output_contract,
                )
                return LlmResult(
                    text=provider_response.text,
                    provider=provider_response.provider,
                    model=provider_response.model,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    finish_reason=provider_response.finish_reason,
                    usage=provider_response.usage,
                    request_id=provider_response.request_id,
                    retry_trace=retry_trace,
                )
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                error = exc if isinstance(exc, LlmInvocationError) else LlmInvocationError(str(exc), classify_exception(exc))
                last_error = error
                retry_trace.append({
                    "provider": candidate["provider"],
                    "model": candidate["model"],
                    "attempt": str(attempt + 1),
                    "errorKind": error.kind.value,
                })
                retryable = error.kind in {LlmErrorKind.RATE_LIMIT, LlmErrorKind.TRANSIENT}
                if retryable and attempt < request.fallback.max_retries:
                    delay = error.retry_after or request.fallback.retry_delay_seconds * (2 ** attempt)
                    time.sleep(max(0.0, delay) * random.uniform(0.5, 1.5))
                    continue
                if retryable and request.fallback.allow_rotation:
                    _rotator.mark_cooldown(candidate["provider"], candidate["model"], error.kind)
                break

        if not request.fallback.allow_rotation:
            break

    if last_error is not None:
        last_error.args = (f"{last_error} (trace: {retry_trace})",)
        raise last_error
    raise LlmInvocationError("LLM invocation failed without a provider error")


def validate_structured_output(text: str, contract: StructuredOutputContract) -> Dict[str, Any]:
    """Parse and validate an executable JSON object before callers can use it."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    try:
        value = json.loads(cleaned)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise LlmInvocationError(f"{contract.name} must be valid JSON: {exc}", LlmErrorKind.MALFORMED_RESPONSE) from exc
    if not isinstance(value, dict):
        raise LlmInvocationError(f"{contract.name} must be a JSON object", LlmErrorKind.MALFORMED_RESPONSE)
    missing = [key for key in contract.required_keys if key not in value]
    if missing:
        raise LlmInvocationError(
            f"{contract.name} is missing required keys: {', '.join(missing)}",
            LlmErrorKind.MALFORMED_RESPONSE,
        )
    if contract.schema:
        try:
            import jsonschema  # type: ignore

            jsonschema.Draft7Validator(contract.schema).validate(value)
        except ModuleNotFoundError:
            pass
        except Exception as exc:
            raise LlmInvocationError(f"{contract.name} does not match schema: {exc}", LlmErrorKind.MALFORMED_RESPONSE) from exc
    return value


def invoke_structured_llm(request: LlmRequest) -> tuple[LlmResult, Dict[str, Any]]:
    """Validate structured output and allow exactly one format-only repair."""
    if request.output_contract is None:
        raise ValueError("invoke_structured_llm requires an output contract")
    result = invoke_llm(request)
    try:
        return result, validate_structured_output(result.text, request.output_contract)
    except LlmInvocationError as validation_error:
        repair_prompt = (
            "Your previous output did not satisfy the required JSON contract. "
            f"Return only a corrected JSON object for contract '{request.output_contract.name}'. "
            f"Validation error: {validation_error}. Previous output: {result.text}"
        )
        repair_request = LlmRequest.from_prompt(
            request.provider,
            request.model,
            repair_prompt,
            system_prompt=request.system_prompt,
            profile=GenerationProfile(name="structured-repair", temperature=0.0, structured_output=True),
            fallback=request.fallback,
            output_contract=request.output_contract,
        )
        repaired_result = invoke_llm(repair_request)
        try:
            structured = validate_structured_output(repaired_result.text, request.output_contract)
        except LlmInvocationError as repair_error:
            raise LlmInvocationError(
                f"{request.output_contract.name} remained invalid after one repair: {repair_error}",
                LlmErrorKind.MALFORMED_RESPONSE,
            ) from repair_error
        repaired_result.retry_trace.append({"kind": "structured_repair", "attempt": "1"})
        return repaired_result, structured

def generate_llm_text(provider: str, model: str, prompt: str, system_prompt: str = "") -> str:
    global _last_used_info
    # Check if rotation is requested
    is_rotation = (provider == "rotation" or model == "rotation")
    
    if is_rotation:
        available_models = _rotator.get_available_models()
        if not available_models:
            raise Exception("All rotation models are currently on cooldown (1 hour) or unavailable.")
        
        last_error = None
        for m_info in available_models:
            try:
                res = _generate_single_llm(m_info["provider"], m_info["model"], prompt, system_prompt)
                _last_used_info = {"provider": m_info["provider"], "model": m_info["model"]}
                return res
            except KeyboardInterrupt:
                raise
            except Exception as e:
                # Any error triggers rotation in this mode
                error_msg = str(e)
                print(f"Error on {m_info['provider']}:{m_info['model']}: {error_msg}. Trying next available model...")
                _rotator.mark_cooldown(m_info["provider"], m_info["model"])
                last_error = e
                continue
        if last_error:
            raise last_error
    
    # Standard call: if it fails for any reason, we attempt the rotation strategy as a fallback
    try:
        res = _generate_single_llm(provider, model, prompt, system_prompt)
        _last_used_info = {"provider": provider, "model": model}
        return res
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"Call to {provider}:{model} failed: {e}. Falling back to rotation strategy...")
        # Optional: mark the current specific model as cooldown so rotation doesn't retry it immediately
        _rotator.mark_cooldown(provider, model)
        return generate_llm_text("rotation", "rotation", prompt, system_prompt)

