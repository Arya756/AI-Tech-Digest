# llm.py

import os
from dotenv import load_dotenv

load_dotenv()

# LLM provider is switchable via env so a model/provider retirement is a
# one-line dashboard change on Render — NOT a code redeploy.
#   LLM_PROVIDER=gemini  -> Google Gemini Flash (fast, generous free quota)
#   LLM_PROVIDER=groq    -> Groq (openai/gpt-oss-120b etc.)
# Gemini is the default because Groq's free tier rate-limits reasoning models
# hard, which made the 52-article pipeline very slow.
#
# Models are built LAZILY (on first .invoke), never at import time, and the
# configured provider gracefully falls back to the other if its API key is
# missing. This keeps the bot alive even if an env var is forgotten on Render.

PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()

# Gemini: flash-lite for the bulk scoring pass (fast/cheap), flash for the
# higher-quality final digest + Hindi translation.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
GEMINI_MODEL_FINAL = os.getenv("GEMINI_MODEL_FINAL", "gemini-flash-latest")

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_MODEL_FINAL = os.getenv("GROQ_MODEL_FINAL", GROQ_MODEL)


def _content_to_str(content):
    """Gemini returns content as a list of parts; normalize to a plain string
    so downstream code (which expects str) never breaks on list content."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part if isinstance(part, str) else part.get("text", "")
            for part in content
        )
    return str(content)


class _StringNormalizingChatModel:
    """Wraps a chat model so .invoke() always returns an AIMessage whose
    .content is a plain string (coerces Gemini's list-of-parts content), and
    retries transient provider errors (503/429/5xx) instead of crashing."""

    def __init__(self, wrapped, max_retries: int = 4):
        self._wrapped = wrapped
        self.model = getattr(wrapped, "model", None)
        self._max_retries = max_retries

    def invoke(self, *args, **kwargs):
        import time as _time
        last_err = None
        for attempt in range(self._max_retries + 1):
            try:
                result = self._wrapped.invoke(*args, **kwargs)
                result.content = _content_to_str(result.content)
                return result
            except Exception as e:  # retry on transient provider errors
                last_err = e
                msg = str(e)
                transient = any(c in msg for c in ("503", "429", "UNAVAILABLE",
                                                   "rate", "Rate", "overloaded", "timeout", "Timeout"))
                if attempt < self._max_retries and transient:
                    _time.sleep(2 ** attempt)  # exponential backoff 1,2,4,8s
                    continue
                raise
        if last_err is not None:
            raise last_err
        raise RuntimeError("LLM invoke failed with no captured error")


def _build_gemini(model_name: str, temperature: float):
    from langchain_google_genai import ChatGoogleGenerativeAI
    return _StringNormalizingChatModel(
        ChatGoogleGenerativeAI(model=model_name, temperature=temperature, max_retries=3)
    )


def _build_groq(model_name: str, temperature: float):
    from langchain_groq import ChatGroq
    return _StringNormalizingChatModel(
        ChatGroq(model=model_name, temperature=temperature, max_retries=3)
    )


def _has_key(name: str) -> bool:
    v = os.getenv(name, "")
    return bool(v) and v not in ("", "your_key_here", "dummy")


class _LazyChatModel:
    """Resolves the real chat model on first .invoke().

    - Builds the configured provider's model; if that provider's API key is
      missing, falls back to the other provider (logs a warning) instead of
      crashing the whole bot at import time.
    - This is why a forgotten GEMINI_API_KEY on Render no longer kills startup.
    """

    def __init__(self, primary: str, model: str, model_final_temperature: float,
                 secondary: str, secondary_model: str):
        self._primary = primary
        self._model = model
        self._temp = model_final_temperature
        self._secondary = secondary
        self._secondary_model = secondary_model
        self._resolved = None

    def _resolve(self):
        if self._resolved is not None:
            return self._resolved
        order = ([self._primary, self._secondary] if self._primary != self._secondary
                 else [self._primary])
        last_err = None
        for prov in order:
            try:
                if prov == "gemini":
                    if not _has_key("GEMINI_API_KEY"):
                        print(f"⚠️ GEMINI_API_KEY missing — skipping Gemini")
                        continue
                    self._resolved = _build_gemini(self._model, self._temp)
                    print(f"✅ LLM (gemini): {self._model}")
                    return self._resolved
                else:  # groq
                    if not _has_key("GROQ_API_KEY"):
                        print(f"⚠️ GROQ_API_KEY missing — skipping Groq")
                        continue
                    self._resolved = _build_groq(self._secondary_model, self._temp)
                    print(f"✅ LLM (groq fallback): {self._secondary_model}")
                    return self._resolved
            except Exception as e:
                last_err = e
                print(f"⚠️ Failed to build {prov} model: {e}")
        if last_err is not None:
            raise RuntimeError(f"No usable LLM provider (tried {order}): {last_err}")
        raise RuntimeError(f"No usable LLM provider (tried {order}) — check API keys")

    @property
    def model(self):
        return self._model

    def invoke(self, *args, **kwargs):
        return self._resolve().invoke(*args, **kwargs)


# Module-level names consumed by summarize.py / main.py. They are lazy proxies
# that build + fall back on first use — never at import time.
llm = _LazyChatModel("gemini", GEMINI_MODEL, 0.2, "groq", GROQ_MODEL)
llm_final = _LazyChatModel("gemini", GEMINI_MODEL_FINAL, 0.4, "groq", GROQ_MODEL_FINAL)
