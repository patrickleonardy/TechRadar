# coding=utf-8
"""Direct, non-streaming OpenAI-compatible chat requests (no provider router)."""

import os
import time
from urllib.parse import urlsplit
from typing import Any, Dict, List

import requests


class AIClient:
    """Send chat requests only to the explicitly configured API base URL."""

    def __init__(self, config: Dict[str, Any]):
        self.model = config.get("MODEL", "")
        self.api_key = config.get("API_KEY") or os.environ.get("AI_API_KEY", "")
        self.api_base = config.get("API_BASE", "")
        self.temperature = config.get("TEMPERATURE", 1.0)
        self.max_tokens = config.get("MAX_TOKENS", 5000)
        self.timeout = config.get("TIMEOUT", 120)
        self.num_retries = config.get("NUM_RETRIES", 2)
        self.fallback_models = config.get("FALLBACK_MODELS", [])
        self.extra_params = config.get("EXTRA_PARAMS") or {}
        if not isinstance(self.extra_params, dict):
            print("[AI] Invalid extra_params; expected a dictionary. Ignoring it.")
            self.extra_params = {}

    @staticmethod
    def _model_name(model: str) -> str:
        # Preserve actual model IDs containing slashes (e.g. organization/model).
        for prefix in ("openai/", "ollama/", "deepseek/"):
            if model.startswith(prefix):
                return model[len(prefix):]
        return model

    def validate_config(self) -> tuple[bool, str]:
        if not isinstance(self.model, str) or not self._model_name(self.model).strip():
            return False, "Set ai.model to the model ID served by your endpoint."
        if not isinstance(self.api_base, str) or not self.api_base.strip():
            return False, "Set ai.api_base explicitly (e.g. http://ollama:11434/v1)."
        try:
            url = urlsplit(self.api_base)
            _ = url.port  # Validate a malformed port before making a request.
        except ValueError:
            return False, "Invalid ai.api_base URL."
        if (url.scheme not in ("http", "https") or not url.hostname
                or url.username is not None or url.password is not None
                or url.query or url.fragment):
            return False, "ai.api_base must be an HTTP(S) base URL without credentials, query or fragment."
        if self.api_key and url.scheme != "https" and url.hostname not in ("localhost", "127.0.0.1", "::1"):
            return False, "Use HTTPS for API keys, or leave ai.api_key empty for a local model."
        return True, ""

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        valid, error = self.validate_config()
        if not valid:
            raise ValueError(error)
        payload = {
            "model": self._model_name(self.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "stream": False,
        }
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        if max_tokens and max_tokens > 0:
            payload["max_tokens"] = max_tokens
        options = {**self.extra_params, **kwargs}
        # Transport and routing settings cannot be replaced via extra_params.
        reserved = {"api_key", "api_base", "base_url", "timeout", "num_retries", "fallbacks", "extra_headers", "max_tokens"}
        for key, value in options.items():
            if key not in payload and key not in reserved:
                payload[key] = value
        headers = {"Content-Type": "application/json"}
        extra_headers = options.get("extra_headers", {})
        if not isinstance(extra_headers, dict):
            raise ValueError("extra_headers must be a dictionary.")
        for key, value in extra_headers.items():
            if key.lower() in ("authorization", "host", "proxy-authorization", "content-length", "transfer-encoding"):
                raise ValueError("extra_headers cannot override authentication or routing headers.")
            headers[key] = value
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        timeout = kwargs.get("timeout", self.timeout)
        retries = max(0, int(kwargs.get("num_retries", self.num_retries)))
        models = [self.model, *self.fallback_models]
        failure = "AI endpoint request failed."
        for model in models:
            payload["model"] = self._model_name(model)
            for attempt in range(retries + 1):
                retryable = False
                try:
                    # Do not forward credentials to a redirect target or use
                    # ambient proxy/.netrc credentials from the host process.
                    with requests.Session() as session:
                        session.trust_env = False
                        with session.post(
                            self.api_base.rstrip("/") + "/chat/completions",
                            json=payload, headers=headers, timeout=timeout,
                            allow_redirects=False,
                        ) as response:
                            status = response.status_code
                            if status != 200:
                                failure = f"AI endpoint returned HTTP {status}."
                                retryable = status in (408, 429) or status >= 500
                            else:
                                try:
                                    content = response.json()["choices"][0]["message"]["content"]
                                    if isinstance(content, list):
                                        content = "\n".join(
                                            item.get("text", "") for item in content
                                            if isinstance(item, dict) and isinstance(item.get("text", ""), str)
                                        )
                                    if content is None:
                                        return ""
                                    if not isinstance(content, str):
                                        raise ValueError("Invalid content type")
                                    return content
                                except (ValueError, KeyError, IndexError, TypeError):
                                    failure = "AI endpoint returned an invalid chat response."
                except requests.RequestException:
                    # Never include server bodies or exception text: either can
                    # contain authorization headers, prompts, or other secrets.
                    failure = "AI endpoint connection failed."
                    retryable = True
                if not retryable or attempt == retries:
                    break
                time.sleep(min(2 ** attempt, 8))
        raise RuntimeError(failure) from None
