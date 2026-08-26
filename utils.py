"""Shared helpers: IST date-string + MarkdownV2 escaping.

PonyTail: one definition, reused everywhere (no 3× duplication of the
date format, no 2× escaping logic).
"""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

_IST = ZoneInfo("Asia/Kolkata")

# Characters that MUST be escaped in Telegram MarkdownV2.
_MD2_SPECIAL = r"_*`[]()~>#+-=|{}.!\"'"


def date_str_now() -> str:
    """Current IST digest key, e.g. '2026-08-25_PM'."""
    ist = datetime.now(_IST)
    return f"{ist.strftime('%Y-%m-%d')}_{ist.strftime('%p')}"


def esc(text: str) -> str:
    """Escape a string for Telegram MarkdownV2 (parse_mode='MarkdownV2')."""
    if not text:
        return ""
    return "".join(f"\\{c}" if c in _MD2_SPECIAL else c for c in str(text))
