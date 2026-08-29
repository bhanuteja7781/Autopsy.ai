import json
import logging
import re
import time
import httpx
from typing import Optional, List
from google import genai
from google.genai import types
from backend.core.config import settings

logger = logging.getLogger("llm_client")

# ── Available & Verified Gemini Models (ordered: working first) ────────────────
GEMINI_EXTRACTION_MODELS = [
    "gemini-3.6-flash",               # primary high-speed extraction model
    "gemini-3.5-flash-lite",          # fast lightweight extraction
    "gemini-3.5-flash",               # larger context model
    "gemini-3.1-flash-lite",          # fallback lite
    "gemini-flash-latest",            # alias
    "gemini-flash-lite-latest",       # alias
]

GEMINI_REASONING_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
]

# ── OpenRouter Models (ordered: paid/verified first, free last) ──────────────
# Paid models confirmed WORKING with current OPENROUTER_API_KEY credits.
# Free models return 429 daily-quota-exceeded until midnight UTC.
OPENROUTER_EXTRACTION_MODELS = [
    "openai/gpt-4o-mini",                          # paid, verified OK
    "meta-llama/llama-3.3-70b-instruct",           # paid, verified OK
    "deepseek/deepseek-chat",                      # paid, verified OK
    "meta-llama/llama-3.1-8b-instruct",            # paid, verified OK
    "nvidia/nemotron-3-ultra-550b-a55b:free",      # free (quota limited)
    "nvidia/nemotron-3-super-120b-a12b:free",      # free (quota limited)
    "google/gemma-4-31b-it:free",                  # free (quota limited)
    "google/gemma-4-26b-a4b-it:free",              # free (quota limited)
]

OPENROUTER_REASONING_MODELS = [
    "openai/gpt-4o-mini",                          # paid, verified OK
    "meta-llama/llama-3.3-70b-instruct",           # paid, verified OK
    "deepseek/deepseek-chat",                      # paid, verified OK
    "meta-llama/llama-3.1-8b-instruct",            # paid, verified OK
    "nvidia/nemotron-3-ultra-550b-a55b:free",      # free (quota limited)
    "nvidia/nemotron-3-super-120b-a12b:free",      # free (quota limited)
    "google/gemma-4-26b-a4b-it:free",              # free (quota limited)
]


def clean_llm_json(raw: str) -> str:
    """Strips thinking tags, markdown code fences, and surrounding chatter."""
    if not raw:
        return ""
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"```\s*$", "", cleaned.strip(), flags=re.MULTILINE)
    return cleaned.strip()


def extract_json_array_str(text: str) -> Optional[str]:
    """Finds the outermost JSON array `[...]` in the text."""
    cleaned = clean_llm_json(text)
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    return match.group(0) if match else None


def extract_json_object_str(text: str) -> Optional[str]:
    """Finds the outermost JSON object `{...}` in the text."""
    cleaned = clean_llm_json(text)
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    return match.group(0) if match else None


# ── Google Gemini Provider ───────────────────────────────────────────────────

class GeminiClient:
    """
    Direct Google Gemini caller using official google.genai SDK.
    Supports candidate model fallback on quota / rate limit / transient errors.
    """

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or settings.GEMINI_API_KEY
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not configured in .env")
        self.client = genai.Client(api_key=key)

    def _call(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        expect: str = "array",  # 'array' | 'object'
        models: Optional[List[str]] = None,
    ) -> str:
        candidate_models = models or (
            GEMINI_EXTRACTION_MODELS if expect == "array" else GEMINI_REASONING_MODELS
        )
        failures: List[str] = []

        full_prompt = prompt
        if system_instruction:
            full_prompt = f"System Instructions:\n{system_instruction}\n\nUser Request:\n{prompt}"

        if expect == "array":
            full_prompt += "\n\nCRITICAL: Respond ONLY with a valid JSON array [...]. No other text or explanation."
        else:
            full_prompt += "\n\nCRITICAL: Respond ONLY with a valid JSON object {...}. No other text or explanation."

        gen_config = types.GenerateContentConfig(
            temperature=0.1,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        for model in candidate_models:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=full_prompt,
                    config=gen_config,
                )
                raw_text = response.text or ""
                extracted = (
                    extract_json_array_str(raw_text)
                    if expect == "array"
                    else extract_json_object_str(raw_text)
                )

                if not extracted:
                    failures.append(f"{model}: no JSON {expect} in output")
                    continue

                json.loads(extracted)  # Validate JSON parse
                logger.info("[Gemini] Success with model: %s", model)
                return extracted
            except Exception as e:
                err_str = str(e)
                failures.append(f"{model}: {err_str[:140]}")
                logger.warning("[Gemini] Model %s failed: %s", model, err_str[:140])
                continue

        raise RuntimeError(
            f"Gemini failed for candidate models:\n"
            + "\n".join(f"  • {f}" for f in failures)
        )

    def extract(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        return self._call(prompt, system_instruction, expect="array")

    def reason(self, prompt: str, system_instruction: Optional[str] = None, model: Optional[str] = None) -> str:
        models = [model] + GEMINI_REASONING_MODELS if model else GEMINI_REASONING_MODELS
        return self._call(prompt, system_instruction, expect="object", models=models)


# ── OpenRouter Provider ───────────────────────────────────────────────────────

def _make_openrouter_request(
    payload: dict,
    timeout: float = 20.0,
    max_attempts: int = 2,
) -> httpx.Response:
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://autopsy.ai",
        "X-Title": "Autopsy.ai Policy Forensics",
        "Content-Type": "application/json",
        "Connection": "close",
    }

    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(max_attempts):
        try:
            with httpx.Client(
                timeout=httpx.Timeout(connect=8.0, read=timeout, write=10.0, pool=5.0),
                http2=False,
            ) as client:
                return client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
        except (
            httpx.RemoteProtocolError,
            httpx.ConnectError,
            httpx.ReadError,
            httpx.WriteError,
            ConnectionResetError,
            OSError,
        ) as exc:
            last_exc = exc
            logger.warning(
                "[OpenRouter] Connection error on attempt %d/%d for model %s: %s",
                attempt + 1,
                max_attempts,
                payload.get("model", "?"),
                exc,
            )
            if attempt < max_attempts - 1:
                time.sleep(1.5 * (attempt + 1))
            continue
        except httpx.TimeoutException as exc:
            last_exc = exc
            logger.warning("[OpenRouter] Timeout for model %s", payload.get("model", "?"))
            break

    raise last_exc


class OpenRouterClient:
    """
    OpenRouter API caller with model cascading fallback.
    """

    def _call(
        self,
        models: list[str],
        messages: list[dict],
        expect: str,  # 'array' | 'object'
        timeout: float = 20.0,
    ) -> str:
        if not settings.OPENROUTER_API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY is not configured in .env")

        seen: set[str] = set()
        deduped: list[str] = []
        for m in models:
            if m and m not in seen:
                seen.add(m)
                deduped.append(m)

        failures: list[str] = []

        for model in deduped:
            payload: dict = {
                "model": model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 2000,
            }

            try:
                resp = _make_openrouter_request(payload, timeout=timeout)
            except Exception as exc:
                failures.append(f"{model}: {exc}")
                logger.warning("[OpenRouter] Skipping %s — connection failed: %s", model, exc)
                continue

            if resp.status_code == 429:
                err_body = resp.text
                if "free-models-per-day" in err_body:
                    logger.warning("[OpenRouter] Free-tier daily quota exhausted for %s", model)
                failures.append(f"{model}: HTTP 429 rate limited")
                continue

            if resp.status_code == 402:
                failures.append(f"{model}: HTTP 402 credits required")
                continue

            if resp.status_code not in (200, 201):
                short = resp.text[:150].replace("\n", " ")
                failures.append(f"{model}: HTTP {resp.status_code} {short}")
                logger.warning("[OpenRouter] %s returned HTTP %d", model, resp.status_code)
                continue

            try:
                choices = resp.json().get("choices", [])
                content = choices[0].get("message", {}).get("content") if choices else None
            except Exception as exc:
                failures.append(f"{model}: JSON parse error {exc}")
                continue

            if not content:
                failures.append(f"{model}: empty content in response")
                continue

            if expect == "array":
                extracted = extract_json_array_str(content)
            else:
                extracted = extract_json_object_str(content)

            if not extracted:
                failures.append(f"{model}: no valid JSON {expect} found in output")
                continue

            try:
                json.loads(extracted)
                logger.info("[OpenRouter] Success with model: %s", model)
                return extracted
            except json.JSONDecodeError as exc:
                failures.append(f"{model}: invalid JSON ({exc})")
                continue

        raise RuntimeError(
            f"OpenRouter failed for candidate models:\n"
            + "\n".join(f"  • {f}" for f in failures)
        )

    def extract(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        messages = [
            {
                "role": "system",
                "content": (system_instruction or "") + "\nRespond with a valid JSON array only. No other text.",
            },
            {"role": "user", "content": prompt},
        ]
        return self._call(
            models=OPENROUTER_EXTRACTION_MODELS,
            messages=messages,
            expect="array",
            timeout=20.0,
        )

    def reason(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        models = []
        if model and model not in models:
            models.append(model)
        for m in OPENROUTER_REASONING_MODELS:
            if m not in models:
                models.append(m)

        messages = [
            {
                "role": "system",
                "content": (system_instruction or "") + "\nRespond with a valid JSON object only. No other text.",
            },
            {"role": "user", "content": prompt + "\nReturn JSON object response."},
        ]
        return self._call(
            models=models,
            messages=messages,
            expect="object",
            timeout=22.0,
        )


# ── Dual-Provider Orchestrated LLM Facade ─────────────────────────────────────

class _ExtractionModelShim:
    """Wraps llm_client.extract() behind a .generate() interface."""
    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        return llm_client.extract(prompt, system_instruction)


class _ReasoningModelShim:
    """Wraps llm_client.reason() behind a .generate() interface."""
    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        return llm_client.reason(prompt, system_instruction, model)


class LLMClient:
    """
    Unified LLM Facade providing seamless Dual Co-operating Model execution
    with cross-provider fallback between Google Gemini and OpenRouter.
    """

    @property
    def gemini_available(self) -> bool:
        return bool(settings.GEMINI_API_KEY)

    @property
    def openrouter_available(self) -> bool:
        return bool(settings.OPENROUTER_API_KEY)

    def extract(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """
        Model 1 (Extraction):
        Primary: Google Gemini (high speed, 1M context, robust JSON schema).
        Fallback: OpenRouter models.
        """
        errors = []
        if self.gemini_available:
            try:
                return GeminiClient().extract(prompt, system_instruction)
            except Exception as e:
                logger.warning("[Extraction] Gemini failed: %s, falling back to OpenRouter...", e)
                errors.append(f"Gemini: {e}")

        if self.openrouter_available:
            try:
                return OpenRouterClient().extract(prompt, system_instruction)
            except Exception as e:
                logger.warning("[Extraction] OpenRouter failed: %s", e)
                errors.append(f"OpenRouter: {e}")

        raise RuntimeError(
            "Extraction failed across all available providers.\n"
            + "\n".join(f"  • {err}" for err in errors)
            if errors
            else "No LLM API keys configured (GEMINI_API_KEY or OPENROUTER_API_KEY required)."
        )

    def reason(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Model 2 (Reasoning):
        Primary: OpenRouter (e.g. GPT-4o-mini / LLaMA 3.3) or Gemini based on config.
        Fallback: Gemini / OpenRouter cross-provider resilience.
        """
        errors = []

        # If OpenRouter key is available and requested model is an OpenRouter model (or default)
        if self.openrouter_available:
            try:
                return OpenRouterClient().reason(prompt, system_instruction, model)
            except Exception as e:
                logger.warning("[Reasoning] OpenRouter failed: %s, attempting Gemini fallback...", e)
                errors.append(f"OpenRouter: {e}")

        if self.gemini_available:
            try:
                return GeminiClient().reason(prompt, system_instruction, model)
            except Exception as e:
                logger.warning("[Reasoning] Gemini failed: %s", e)
                errors.append(f"Gemini: {e}")

        raise RuntimeError(
            "Reasoning failed across all available providers.\n"
            + "\n".join(f"  • {err}" for err in errors)
            if errors
            else "No LLM API keys configured (GEMINI_API_KEY or OPENROUTER_API_KEY required)."
        )

    # ── Shim accessors ────────────────────────────────────────────────────────
    def get_extraction_model(self) -> _ExtractionModelShim:
        return _ExtractionModelShim()

    def get_reasoning_model(self) -> _ReasoningModelShim:
        return _ReasoningModelShim()

    # ── Direct call methods ───────────────────────────────────────────────────
    def call_gemini(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        return self.extract(prompt, system_instruction)

    def call_reasoner_llm(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model: str = settings.REASONER_MODEL,
    ) -> str:
        return self.reason(prompt, system_instruction, model)


llm_client = LLMClient()
