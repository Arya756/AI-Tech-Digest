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

PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()

# Groq is the primary provider: free tier gives 14K+ requests/day.
#   GROQ_MODEL            — primary model for FAST bulk article analysis/scoring.
#                          Qwen 27B: fast (~0.7s/call), no rate-limiting, gets 5+
#                          articles through. Used to rapidly filter+score all articles.
#   GROQ_MODEL_FINAL      — model for FINAL OUTPUT POLISH + Hindi translation.
#                          GPT-oss-120b (reasoning): fills blank Context/Summary/
#                          Impact fields reliably so the delivered message has substance.
#                          Also used for Hindi translation (short outputs, fine on Qwen).
#   GROQ_MODEL_BACKUP     — Groq-model fallback: if the primary Groq model fails
#                          (rate-limit / 429 / unavailable), retry the backup before
#                          falling back to an entirely different provider.
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")
GROQ_MODEL_FINAL = os.getenv("GROQ_MODEL_FINAL", "openai/gpt-oss-120b")
GROQ_MODEL_BACKUP = os.getenv("GROQ_MODEL_BACKUP", "qwen/qwen3.8-27b")

# Gemini — kept as the last-resort provider fallback across the whole provider.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
GEMINI_MODEL_FINAL = os.getenv("GEMINI_MODEL_FINAL", "gemini-flash-latest")


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
    """Resolves a usable chat model on first .invoke(), trying candidates in
    order so a single bad model or rate-limited provider never kills the bot.

    Candidates (tried in this order):
      1. Primary model on the primary provider
         (e.g. Groq Qwen 3.6-27B for article analysis / scoring).
      2. Backup model on the SAME provider (e.g. Groq Qwen 3.8-27B) — reached
         when the primary Groq model rate-limits / 429s / is unavailable.
      3. Fallback provider's model (e.g. Gemini flash-lite / flash-latest) —
         only reached when BOTH Groq models fail, so the bot still delivers
         something instead of crashing.

    A candidate whose API key is missing is skipped with a logged warning
    instead of crashing the bot at import time. This is why a forgotten
    GEMINI_API_KEY or GROQ_API_KEY no longer kills startup.
    """

    def __init__(self, primary_provider, primary_model, temp,
                 backup_model, fallback_provider, fallback_model, fallback_temp):
        # Ordered (provider, model, temperature) candidates.
        self._candidates = [
            (primary_provider, primary_model, temp),
            (primary_provider, backup_model, temp),
        ]
        if fallback_provider and fallback_model:
            self._candidates.append((fallback_provider, fallback_model, fallback_temp))
        self._model = primary_model
        self._resolved = None

    def _build(self, provider: str, model: str, temp: float):
        if provider == "groq":
            if not _has_key("GROQ_API_KEY"):
                print(f"⚠️ GROQ_API_KEY missing — skipping Groq model {model}")
                raise RuntimeError("GROQ_API_KEY missing")
            return _build_groq(model, temp)
        # gemini (or any other provider)
        else:
            if not _has_key("GEMINI_API_KEY"):
                print(f"⚠️ GEMINI_API_KEY missing — skipping Gemini model {model}")
                raise RuntimeError("GEMINI_API_KEY missing")
            return _build_gemini(model, temp)

    def _resolve(self):
        if self._resolved is not None:
            return self._resolved
        last_err = None
        for prov, model, temp in self._candidates:
            try:
                self._resolved = self._build(prov, model, temp)
                print(f"✅ LLM ({prov}): {model}  (t={temp})")
                return self._resolved
            except Exception as e:
                last_err = e
                print(f"⚠️ Failed to build {prov} model {model}: {e}")
        if last_err is not None:
            raise RuntimeError(
                f"No usable LLM after trying {len(self._candidates)} candidates: {last_err}"
            )
        raise RuntimeError("No usable LLM — check API keys")

    @property
    def model(self):
        return self._model

    def invoke(self, *args, **kwargs):
        return self._resolve().invoke(*args, **kwargs)


# Module-level names consumed by summarize.py / main.py. Lazy proxies that build
# on first use and fall back through the tier list — never at import time.
llm = _LazyChatModel(
    primary_provider="groq", primary_model=GROQ_MODEL, temp=0.2,
    backup_model=GROQ_MODEL_BACKUP,
    fallback_provider="gemini", fallback_model=GEMINI_MODEL, fallback_temp=0.2,
)
llm_final = _LazyChatModel(
    primary_provider="groq", primary_model=GROQ_MODEL_FINAL, temp=0.4,
    backup_model=GROQ_MODEL,  # cross-backup: the other 27B Qwen model
    fallback_provider="gemini", fallback_model=GEMINI_MODEL_FINAL, fallback_temp=0.4,
)
