# llm.py

import os
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

# Primary fast model for bulk processing
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.2,
    max_retries=3,
)

# Same model — kept separate so you can swap to a stronger one later
# (e.g. mixtral for final digest generation)
llm_final = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.4,
    max_retries=3,
)