# llm.py

import os
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

# Model is configurable via env so a Groq model retirement is a one-line
# dashboard change on Render — NOT a code redeploy.
# `llama-3.3-70b-versatile` was retired by Groq; `llama-3.1-8b-instant` is a
# reliable free-tier default. Set GROQ_MODEL / GROQ_MODEL_FINAL in .env to swap.
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_MODEL_FINAL = os.getenv("GROQ_MODEL_FINAL", GROQ_MODEL)

# Primary fast model for bulk processing
llm = ChatGroq(
    model=GROQ_MODEL,
    temperature=0.2,
    max_retries=3,
)

# Same model — kept separate so you can swap to a stronger one later
# (e.g. set GROQ_MODEL_FINAL to a larger model for final digest generation).
llm_final = ChatGroq(
    model=GROQ_MODEL_FINAL,
    temperature=0.4,
    max_retries=3,
)
