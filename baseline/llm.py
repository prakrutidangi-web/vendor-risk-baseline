"""
Groq free-tier LLM wrapper.

Everything that could go wrong with a free-tier API key lives in this one file:
- rate limiting (Groq's free tier enforces real RPM and RPD caps, so this
  pacer keeps you under them instead of tripping 429s)
- a soft local safety cap on total calls per day (a second guardrail below
  Groq's own daily cap, so a bug or oversized eval run stops cleanly with a
  clear message instead of burning your whole day's free quota on retries)
- retry with exponential backoff + jitter on transient errors (429/500/502/503/504
  and flaky network errors)
- automatic fallback to a different model if the primary one 404s
  (deprecated / renamed / not enabled for this key)
- a DRY_RUN mode that returns deterministic canned responses so you can prove
  the entire pipeline works before spending a single real API call

Every other file in this project calls the LLM ONLY through LLMClient below.
Never call the OpenAI-compatible client directly from a node: that's how you
lose all of the above.

Provider: Groq's API is OpenAI-protocol-compatible
(https://console.groq.com/docs/openai), so this wrapper talks to it through
the official `openai` Python SDK pointed at Groq's base URL rather than a
Groq-specific SDK. Free API keys need no credit card; get one at
https://console.groq.com/keys.

Submission by Prakruti Dangi.
"""
from __future__ import annotations

import json
import os
import re
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
    before_sleep_log,
)
import logging

load_dotenv()

logger = logging.getLogger("vendor_risk_agent.llm")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

QUOTA_STATE_FILE = Path(__file__).resolve().parent.parent / ".quota_state.json"


class TransientLLMError(Exception):
    """Raised for errors worth retrying (rate limit, server hiccup, network)."""


class ModelUnavailableError(Exception):
    """Raised when a model 404s or isn't available. Triggers a fallback, not a retry."""


class QuotaExceededError(Exception):
    """Raised when the local safety cap on daily requests would be exceeded."""


def _env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class RateLimiter:
    """Simple sliding-window limiter: never allow more than `rpm` calls in any
    rolling 60-second window. Blocks (sleeps) instead of erroring, because for
    a free-tier hackathon project waiting a few seconds is free and a 429 is
    not."""

    def __init__(self, rpm: int):
        self.rpm = max(1, rpm)
        self._timestamps: deque[float] = deque()

    def wait_for_slot(self) -> None:
        now = time.monotonic()
        while self._timestamps and now - self._timestamps[0] > 60:
            self._timestamps.popleft()
        if len(self._timestamps) >= self.rpm:
            sleep_for = 60 - (now - self._timestamps[0]) + 0.25
            if sleep_for > 0:
                logger.info(
                    "Rate limiter: at %s calls/min, sleeping %.1fs to stay under the free-tier limit",
                    self.rpm,
                    sleep_for,
                )
                time.sleep(sleep_for)
        self._timestamps.append(time.monotonic())


class DailyQuotaTracker:
    """Local, best-effort counter of calls made today, persisted to a small
    JSON file so it survives across separate `python` invocations in the same
    day. Groq's free tier itself caps you at roughly 1000 requests/day (check
    your exact limit at https://console.groq.com/settings/limits). This is
    a second, more conservative local guardrail so a bug or an oversized eval
    run can't silently burn through your whole day's allowance via retries
    before you notice."""

    def __init__(self, cap: int, state_file: Path = QUOTA_STATE_FILE):
        self.cap = cap
        self.state_file = state_file

    def _today_key(self) -> str:
        return time.strftime("%Y-%m-%d")

    def _load(self) -> dict:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def count_today(self) -> int:
        return self._load().get(self._today_key(), 0)

    def record_call(self) -> None:
        """Increment today's call count. Best-effort: if the write fails,
        this stays silent rather than crashing the run over a logging file."""
        state = self._load()
        key = self._today_key()
        state[key] = state.get(key, 0) + 1
        try:
            self.state_file.write_text(json.dumps(state))
        except OSError:
            pass

    def check_before_call(self) -> None:
        used = self.count_today()
        if used >= self.cap:
            raise QuotaExceededError(
                f"Local safety cap reached: {used}/{self.cap} calls made today "
                f"(LLM_DAILY_SAFETY_CAP in .env). This is a guardrail below "
                f"Groq's own ~1000/day free-tier limit, not Groq's real quota. "
                f"Raise the cap in .env if you know you have headroom left at "
                f"https://console.groq.com/settings/limits, or wait for the "
                f"free tier's daily reset."
            )


def extract_json(text: str) -> dict:
    """Pull a JSON object out of a model response that may be wrapped in
    ```json fences or have stray prose around it. As a last resort, falls
    back to the widest {...} span found anywhere in the text."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as e:
            raise ValueError(f"Could not parse JSON from model response: {e}\nRaw text:\n{text[:1000]}")
    raise ValueError(f"No JSON object found in model response:\n{text[:1000]}")


def _content_to_text(content) -> str:
    """Normalize a chat completion's message content to plain text. The
    OpenAI-compatible API Groq exposes returns a plain string in the common
    case, but this stays defensive against a list-of-content-blocks shape
    (seen from some providers/reasoning models) so a format change doesn't
    crash `extract_json`'s regex call."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if isinstance(item.get("text"), str):
                    parts.append(item["text"])
        return "".join(parts)
    return str(content)


@dataclass
class LLMClient:
    model: str = field(default_factory=lambda: os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"))
    fallback_models: list[str] = field(
        default_factory=lambda: [
            m.strip()
            for m in os.environ.get("GROQ_FALLBACK_MODELS", "openai/gpt-oss-20b").split(",")
            if m.strip()
        ]
    )
    base_url: str = field(default_factory=lambda: os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1"))
    rpm_limit: int = field(default_factory=lambda: _env_int("LLM_RPM_LIMIT", 25))
    max_retries: int = field(default_factory=lambda: _env_int("LLM_MAX_RETRIES", 5))
    daily_cap: int = field(default_factory=lambda: _env_int("LLM_DAILY_SAFETY_CAP", 900))
    dry_run: bool = field(default_factory=lambda: _env_bool("DRY_RUN", False))

    def __post_init__(self):
        self._rate_limiter = RateLimiter(self.rpm_limit)
        self._quota = DailyQuotaTracker(self.daily_cap)
        self._active_model = self.model
        self._model_lock = threading.Lock()
        self._client_obj: Any = None
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_calls = 0
        if not self.dry_run and not os.environ.get("GROQ_API_KEY"):
            raise RuntimeError(
                "No GROQ_API_KEY found in the environment. "
                "Copy .env.example to .env and paste in a free key from "
                "https://console.groq.com/keys, or set DRY_RUN=true in .env "
                "to test the whole pipeline offline first."
            )

    def _get_client(self):
        """Lazily construct the OpenAI-compatible client.

        Delegates 429/5xx retries to the SDK's own retry logic first, since
        it parses the API's "Please try again in Xs" hint and waits that
        exact amount instead of guessing. That matters on Groq's free tier,
        where the binding constraint is tokens-per-minute rather than
        requests-per-minute, so a burst of parallel calls can trip TPM even
        while comfortably under any RPM limit. The tenacity retry in
        `invoke_text()` remains as an outer safety net beyond that.
        """
        if self._client_obj is None:
            from openai import OpenAI

            self._client_obj = OpenAI(
                api_key=os.environ.get("GROQ_API_KEY"),
                base_url=self.base_url,
                max_retries=self.max_retries,
            )
        return self._client_obj

    def _classify_error(self, exc: Exception) -> str:
        """Classify an exception as 'retry', 'fallback', or 'fatal'.

        A daily (TPD/RPD) cap behaves differently from a per-minute
        (TPM/RPM) one: the per-minute window clears in seconds, so retrying
        the same model is the right move. A daily cap on this specific
        model, though, can take many minutes (or longer) to free up, and
        Groq scopes these quotas per model, so a different model likely has
        its own untouched budget. That's why a daily-cap error is classified
        as 'fallback' (switch models) rather than 'retry' (wait and hammer
        the same exhausted model). Network-level flakiness (a proxy hiccup,
        a DNS blip) can also leak through as a raw httpx/requests/urllib3
        exception instead of an openai.* wrapper, and is treated as worth a
        retry too.
        """
        status_code = getattr(exc, "status_code", None)
        cls_name = type(exc).__name__.upper()
        text = f"{exc}".upper()

        if status_code == 429 and ("(TPD)" in text or "(RPD)" in text or "TOKENS PER DAY" in text or "REQUESTS PER DAY" in text):
            return "fallback"
        if status_code == 429 or "RATELIMIT" in cls_name or "RATE LIMIT" in text or "RESOURCE_EXHAUSTED" in text:
            return "retry"
        if status_code in (500, 502, 503, 504) or "INTERNALSERVERERROR" in cls_name or "SERVICE UNAVAILABLE" in text or "OVERLOADED" in text or "UNAVAILABLE" in text:
            return "retry"
        if status_code == 404 or "NOTFOUNDERROR" in cls_name or "NOT_FOUND" in text or "NOT FOUND" in text or "MODEL_NOT_FOUND" in text or "DOES NOT EXIST" in text or "DECOMMISSIONED" in text:
            return "fallback"
        if "APICONNECTIONERROR" in cls_name or "APITIMEOUTERROR" in cls_name or "TIMEOUT" in text or "CONNECTION" in text:
            return "retry"
        exc_module = type(exc).__module__
        if any(k in exc_module for k in ("httpx", "requests", "urllib3", "socket")):
            return "retry"
        return "fatal"

    def _call_once(
        self,
        model_name: str,
        prompt: str,
        system: Optional[str],
        response_format: Optional[dict] = None,
    ) -> str:
        self._quota.check_before_call()
        self._rate_limiter.wait_for_slot()
        client = self._get_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.2,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        response = client.chat.completions.create(**kwargs)
        self._quota.record_call()
        self.total_calls += 1
        usage = getattr(response, "usage", None)
        if usage:
            self.total_input_tokens += getattr(usage, "prompt_tokens", 0) or 0
            self.total_output_tokens += getattr(usage, "completion_tokens", 0) or 0
        content = response.choices[0].message.content
        return _content_to_text(content)

    def invoke_text(
        self,
        prompt: str,
        system: Optional[str] = None,
        dry_run_response: str = "",
        response_format: Optional[dict] = None,
    ) -> str:
        """Call the model, trying the primary model then any fallback
        models in declared order. Retries transient errors with backoff, and
        remembers whichever model last succeeded so the next call tries
        that one first. `response_format` is passed straight through to the
        API, for example `{"type": "json_object"}` to request Groq's JSON
        object mode, which every model on the platform honors at the syntax
        level even though it doesn't enforce a specific schema."""
        if self.dry_run:
            logger.info("[DRY_RUN] returning canned response instead of calling the LLM")
            return dry_run_response

        with self._model_lock:
            start_model = self._active_model
        models_to_try = [start_model, *[m for m in self.fallback_models if m != start_model]]
        last_exc: Optional[Exception] = None

        for model_name in models_to_try:

            @retry(
                reraise=True,
                stop=stop_after_attempt(self.max_retries),
                wait=wait_exponential_jitter(initial=2, max=30),
                retry=retry_if_exception_type(TransientLLMError),
                before_sleep=before_sleep_log(logger, logging.WARNING),
            )
            def _attempt():
                try:
                    return self._call_once(model_name, prompt, system, response_format)
                except QuotaExceededError:
                    raise
                except Exception as e:
                    kind = self._classify_error(e)
                    if kind == "retry":
                        raise TransientLLMError(str(e)) from e
                    raise

            try:
                result = _attempt()
                with self._model_lock:
                    self._active_model = model_name
                return result
            except QuotaExceededError:
                raise
            except Exception as e:
                kind = self._classify_error(e)
                last_exc = e
                if kind == "fallback":
                    logger.warning(
                        "Model '%s' unavailable (%s); trying fallback model.", model_name, e
                    )
                    continue
                raise RuntimeError(
                    f"LLM call failed on model '{model_name}' after retries: {e}\n"
                    f"If this is a 429, lower LLM_RPM_LIMIT in .env or wait a few seconds. "
                    f"If this is an auth error, check GROQ_API_KEY in .env. "
                    f"You can also set DRY_RUN=true in .env to keep developing offline."
                ) from e

        raise RuntimeError(
            f"All models exhausted (tried {models_to_try}). Last error: {last_exc}. "
            f"Check https://console.groq.com/docs/models for current model IDs, "
            f"or add another model to GROQ_FALLBACK_MODELS in .env."
        )

    def invoke_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        dry_run_response: Optional[dict] = None,
        max_attempts: int = 3,
    ) -> dict:
        """Call the model and parse its response as JSON.

        Every call requests Groq's JSON object mode
        (`response_format={"type": "json_object"}`), which every model on
        the platform honors at the syntax level, so most of what used to
        come back as stray conversational prose now comes back as
        syntactically valid (if not necessarily schema-correct) JSON before
        any retry is even needed.

        When a response still doesn't parse, this distinguishes two cases
        that need opposite handling. If the response contains no `{` at
        all, there is no JSON in it to fix, so this retries the original
        prompt rather than asking the model to "correct" text that was
        never JSON to begin with; a smaller fallback model asked to fix
        nothing tends to reply with a confused refusal such as "I don't see
        any JSON text to correct", which is itself unparseable and used to
        make the whole case fail outright. If the response does contain a
        `{`, it's JSON-shaped but broken, so this asks the model to correct
        its own output instead of starting over. Either way, this stops
        after `max_attempts` calls and raises with the model's last raw
        response included, so a genuine failure stays visible rather than
        retrying forever.
        """
        if self.dry_run:
            return dry_run_response or {}

        json_prompt = (
            prompt
            + "\n\nRespond with ONLY a single valid JSON object. No prose, no markdown fences, no explanation."
        )
        json_mode = {"type": "json_object"}

        raw = self.invoke_text(json_prompt, system=system, response_format=json_mode)
        for attempt in range(max_attempts):
            try:
                return extract_json(raw)
            except ValueError:
                if attempt == max_attempts - 1:
                    break
                if "{" in raw:
                    logger.warning(
                        "Model returned JSON-shaped but unparseable output (attempt %d), asking it to reformat.",
                        attempt + 1,
                    )
                    fix_prompt = (
                        "The following text was supposed to be a single valid JSON object but is not. "
                        "Return ONLY the corrected valid JSON object, nothing else.\n\n" + raw
                    )
                    raw = self.invoke_text(fix_prompt, system=system, response_format=json_mode)
                else:
                    logger.warning(
                        "Model returned no JSON-like content at all (attempt %d), retrying the original prompt.",
                        attempt + 1,
                    )
                    raw = self.invoke_text(json_prompt, system=system, response_format=json_mode)

        raise ValueError(
            f"Model never returned a parseable JSON object after {max_attempts} attempts. "
            f"Last response:\n{raw[:1000]}"
        )


_default_client: Optional[LLMClient] = None


def get_client() -> LLMClient:
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client
