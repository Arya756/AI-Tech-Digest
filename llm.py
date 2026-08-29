# llm.py

import os
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

# Model is configurable via env so a Groq model retirement is a one-line
# dashboard change on Render — NOT a code redeploy.
# Groq retired llama-3.3-70b-versatile and llama-3.1-8b-instant. Current
# free-tier text models on this account: openai/gpt-oss-120b, openai/gpt-oss-20b,
# qwen/qwen3.6-27b, qwen/qwen3.8-27b. Default to a strong available one.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
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
