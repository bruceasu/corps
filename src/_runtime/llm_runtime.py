import os
import json
import requests
import time
from typing import Optional, List, Dict, Any
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    # Fallback for environments where openai is not yet installed
    OpenAI = None

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
            with open(self.COOLDOWN_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cooldowns, f)
        except:
            pass

    def mark_cooldown(self, provider: str, model: str):
        key = f"{provider}:{model}"
        self.cooldowns[key] = time.time()
        self._save_cooldowns()

    def get_available_models(self) -> List[Dict[str, str]]:
        now = time.time()
        available = []
        for item in self.rotation_list:
            key = f"{item['provider']}:{item['model']}"
            last_fail = self.cooldowns.get(key, 0)
            if now - last_fail > self.COOLDOWN_DURATION:
                available.append(item)
        return available

_rotator = ModelRotator()

def get_rotator():
    return _rotator

def call_anthropic(api_key: str, model: str, prompt: str, system_prompt: str = "") -> str:
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
        
    response = requests.post(url, headers=headers, json=body, timeout=120)
    response.raise_for_status()
    payload = response.json()
    
    content = payload.get("content") or []
    if not content:
        return ""
    return str(content[0].get("text") or "")

def call_gemini(api_key: str, model: str, prompt: str, system_prompt: str = "") -> str:
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
        
    response = requests.post(url, headers=headers, json=body, timeout=120)
    if response.status_code != 200:
        # Fallback for models that might not support system_instruction
        if "system_instruction" in response.text:
            new_prompt = f"System Instruction:\n{system_prompt}\n\nUser Prompt:\n{prompt}"
            body = {
                "contents": [{"role": "user", "parts": [{"text": new_prompt}]}]
            }
            response = requests.post(url, headers=headers, json=body, timeout=120)
        
    response.raise_for_status()
    payload = response.json()
    
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    if not parts:
        return ""
    return str(parts[0].get("text") or "")

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

_last_used_info = {"provider": "unknown", "model": "unknown"}

def get_last_used_model_info() -> Dict[str, str]:
    return _last_used_info

def skip_current_model():
    global _last_used_info
    if _last_used_info["provider"] != "unknown":
        _rotator.mark_cooldown(_last_used_info["provider"], _last_used_info["model"])
        return _last_used_info
    return None

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

