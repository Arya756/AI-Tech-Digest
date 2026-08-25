"""
thumbnail.py — zero-cost per-article cover images for the AI Tech Digest.

Renders one 1080x1080 PNG per story using Pillow (CPU-only, no API, no paid
service) so it runs on Render's free tier. Reads the structured article dict
directly (title/source/category) — never re-parses the .txt digest.

Visuals are 100% Pillow-drawn (no external image assets, no paid gen):
  - A per-category GLYPH drawn with vector shapes (AI / research / big_tech /
    startup / hardware / other).
  - A subtle deterministic GENERATIVE BACKDROP (dot-grid + arcs) seeded by the
    story title, so every card is unique yet reproducible.
  - A richer COLOR SYSTEM: each category owns a distinct hue; priority is shown
    by background depth (CRITICAL deepest, NOTE lightest) instead of a score number.

No emoji are drawn into the image (Pillow's font won't render color emoji);
emoji stay in the Telegram caption.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_ASSETS = Path(__file__).parent / "assets"
_FONT_PATH = _ASSETS / "DejaVuSans.ttf"
_BOLD_PATH = _ASSETS / "DejaVuSans-Bold.ttf" if (_ASSETS / "DejaVuSans-Bold.ttf").exists() else _FONT_PATH

W, H = 1080, 1080

# ── Color system ─────────────────────────────────────────────────────────────
# Each category gets a distinct base hue. Priority is conveyed by background
# DEPTH (how dark/saturated), not a score number.
CATEGORY_COLORS = {
    "AI":        "#4F46E5",  # indigo
    "AI_TOOLS":  "#0EA5E9",  # sky
    "RESEARCH":  "#7C3AED",  # violet
    "BIG_TECH":  "#0D9488",  # teal
    "STARTUP":   "#DB2777",  # pink
    "HARDWARE":  "#EA580C",  # orange
    "OTHER":     "#475569",  # slate
}
# Map the digest's lowercase category keys to the palette above.
CAT_KEY_MAP = {
    "ai": "AI", "ai_tools": "AI_TOOLS", "research": "RESEARCH",
    "big_tech": "BIG_TECH", "startup": "STARTUP", "hardware": "HARDWARE",
    "other": "OTHER",
}


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _darken(rgb: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(c * factor))) for c in rgb)


def _lighten(rgb: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(c + (255 - c) * factor))) for c in rgb)


def _category_bg(category: str, score: float) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Return (bg_rgb, accent_rgb). Background depth encodes priority."""
    key = CAT_KEY_MAP.get(str(category).lower(), "OTHER")
    base = _hex_to_rgb(CATEGORY_COLORS.get(key, CATEGORY_COLORS["OTHER"]))
    # CRITICAL (>=17): deepest; IMPORTANT (>=11): mid; NOTE: lightest.
    if score >= 17:
        depth = 0.32
    elif score >= 11:
        depth = 0.45
    else:
        depth = 0.60
    bg = _darken(base, depth)
    accent = _lighten(base, 0.35)
    return bg, accent


# ── Fonts ─────────────────────────────────────────────────────────────────────
def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    return ImageFont.truetype(str(_BOLD_PATH if bold else _FONT_PATH), size)


def _wrap(text: str, font: ImageFont.ImageFont, max_w: int) -> list[str]:
    """Manual word-wrap (Pillow has no auto-wrap). Hard-splits long tokens."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        cur = ""
        for w in words:
            trial = (cur + " " + w).strip()
            if font.getlength(trial) <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                while font.getlength(w) > max_w and len(w) > 1:
                    cut = len(w)
                    while cut > 1 and font.getlength(w[:cut]) > max_w:
                        cut -= 1
                    lines.append(w[:cut])
                    w = w[cut:]
                cur = w
        if cur:
            lines.append(cur)
    return lines


# ── Generative backdrop ────────────────────────────────────────────────────────
def _draw_backdrop(d: ImageDraw.Draw, seed: str, accent: tuple[int, int, int]):
    """Deterministic dot-grid + arcs seeded by the story title."""
    h = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
    rng = [(h >> (i * 3)) % 17 for i in range(40)]  # stable pseudo-values

    # Dot grid in the upper-right, faint
    step = 86
    dots = []
    xr = W - 520
    for r in range(6):
        for c in range(6):
            ox = rng[(r * 6 + c) % len(rng)]
            dots.append((xr + c * step + (ox % 20), 120 + r * step + (ox % 16)))
    for (x, y) in dots:
        d.ellipse([x, y, x + 7, y + 7], fill=accent)

    # Concentric arcs bottom-left, faint
    cx, cy = -120, H + 120
    for i, rad in enumerate(range(260, 920, 130)):
        col = accent if i % 2 == 0 else _lighten(accent, 0.2)
        d.arc([cx - rad, cy - rad, cx + rad, cy + rad], start=20, end=120, fill=col, width=6)

    # A few stray accent ticks for texture
    for i in range(5):
        y = 200 + rng[i] * 30
        d.line([W - 60, y, W - 60 - (40 + rng[i + 5] % 60), y], fill=accent, width=4)


# ── Category glyphs (vector-drawn) ───────────────────────────────────────────────
def _glyph_ai(d: ImageDraw.Draw, cx: int, cy: int, s: int, col):
    """Neural network: 3 layers of nodes + connections."""
    layers = [3, 4, 2]
    xs = [cx - s, cx, cx + s]
    coords = []
    for li, n in enumerate(layers):
        col_y = [cy + (i - (n - 1) / 2) * (s * 0.7) for i in range(n)]
        coords.append(list(zip([xs[li]] * n, col_y)))
    # connections
    for a in coords[0]:
        for b in coords[1]:
            d.line([a, b], fill=col, width=3)
    for a in coords[1]:
        for b in coords[2]:
            d.line([a, b], fill=col, width=3)
    # nodes
    for layer in coords:
        for (x, y) in layer:
            d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=col)

def _glyph_research(d: ImageDraw.Draw, cx: int, cy: int, s: int, col):
    """Atom: nucleus + 3 elliptical orbits."""
    d.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], fill=col)
    for ang in (0, 60, 120):
        box = [cx - s, cy - s * 0.55, cx + s, cy + s * 0.55]
        d.ellipse(box, outline=col, width=5)
    d.ellipse([cx - s, cy - s * 0.55, cx + s, cy + s * 0.55], outline=col, width=5)

def _glyph_bigtech(d: ImageDraw.Draw, cx: int, cy: int, s: int, col):
    """Building: tower with windows."""
    d.rectangle([cx - s * 0.7, cy - s, cx + s * 0.7, cy + s], outline=col, width=6)
    for r in range(-2, 3):
        for c in range(-1, 2):
            wx = cx + c * (s * 0.42)
            wy = cy + r * (s * 0.38)
            d.rectangle([wx - 10, wy - 12, wx + 10, wy + 12], outline=col, width=3)

def _glyph_startup(d: ImageDraw.Draw, cx: int, cy: int, s: int, col):
    """Rocket: body + fins + window + flame."""
    d.polygon([(cx, cy - s), (cx - s * 0.5, cy + s * 0.7), (cx + s * 0.5, cy + s * 0.7)], outline=col, width=6)
    d.ellipse([cx - 14, cy - s * 0.4, cx + 14, cy - s * 0.4 + 28], outline=col, width=4)
    d.polygon([(cx - s * 0.5, cy + s * 0.7), (cx - s * 0.8, cy + s), (cx - s * 0.2, cy + s * 0.85)], fill=col)
    d.polygon([(cx + s * 0.5, cy + s * 0.7), (cx + s * 0.8, cy + s), (cx + s * 0.2, cy + s * 0.85)], fill=col)
    d.polygon([(cx - 14, cy + s * 0.7), (cx, cy + s * 1.25), (cx + 14, cy + s * 0.7)], fill=col)

def _glyph_hardware(d: ImageDraw.Draw, cx: int, cy: int, s: int, col):
    """Chip: square die + pins."""
    d.rectangle([cx - s * 0.7, cy - s * 0.7, cx + s * 0.7, cy + s * 0.7], outline=col, width=6)
    d.rectangle([cx - s * 0.35, cy - s * 0.35, cx + s * 0.35, cy + s * 0.35], outline=col, width=4)
    for i in range(-2, 3):
        off = i * (s * 0.35)
        d.line([cx + off, cy - s * 0.7, cx + off, cy - s], fill=col, width=4)
        d.line([cx + off, cy + s * 0.7, cx + off, cy + s], fill=col, width=4)
        d.line([cx - s * 0.7, cy + off, cx - s, cy + off], fill=col, width=4)
        d.line([cx + s * 0.7, cy + off, cx + s, cy + off], fill=col, width=4)

def _glyph_other(d: ImageDraw.Draw, cx: int, cy: int, s: int, col):
    """Spark: 4-point starburst."""
    pts = [(cx, cy - s), (cx + s * 0.25, cy - s * 0.25), (cx + s, cy),
           (cx + s * 0.25, cy + s * 0.25), (cx, cy + s), (cx - s * 0.25, cy + s * 0.25),
           (cx - s, cy), (cx - s * 0.25, cy - s * 0.25)]
    d.polygon(pts, outline=col, width=6)

GLYPHS = {
    "AI": _glyph_ai, "AI_TOOLS": _glyph_ai, "RESEARCH": _glyph_research,
    "BIG_TECH": _glyph_bigtech, "STARTUP": _glyph_startup,
    "HARDWARE": _glyph_hardware, "OTHER": _glyph_other,
}


# ── Topic-resonant sub-motifs (keyword → drawn illustration) ────────────────────
# Drawn ON TOP of the category glyph to make the card resonate with the specific
# story. Pure Pillow vector art — no network, no copyright risk, $0.
def _motif_phone(d: ImageDraw.Draw, cx: int, cy: int, s: int, col):
    """Smartphone outline + camera lens (Pixel / Galaxy / phone launches)."""
    d.rounded_rectangle([cx - s * 0.55, cy - s, cx + s * 0.55, cy + s], radius=28, outline=col, width=7)
    d.ellipse([cx - s * 0.22, cy - s * 0.78, cx + s * 0.22, cy - s * 0.34], outline=col, width=5)
    d.line([cx, cy - s * 0.1, cx, cy + s * 0.6], fill=col, width=4)

def _motif_chat(d: ImageDraw.Draw, cx: int, cy: int, s: int, col):
    """Chat bubble + sparkle (ChatGPT / LLM / model launches)."""
    d.rounded_rectangle([cx - s, cy - s * 0.7, cx + s, cy + s * 0.5], radius=26, outline=col, width=7)
    for dx, dy in (-s * 0.5, -s * 0.2), (0, -s * 0.2), (s * 0.5, -s * 0.2):
        d.ellipse([cx + dx - 10, cy + dy - 10, cx + dx + 10, cy + dy + 10], fill=col)
    d.polygon([(cx - s * 0.1, cy + s * 0.5), (cx - s * 0.5, cy + s), (cx + s * 0.2, cy + s * 0.55)], fill=col)
    d.line([cx + s * 0.7, cy - s * 0.9, cx + s * 0.7, cy - s * 0.4], fill=col, width=5)
    d.line([cx + s * 0.45, cy - s * 0.65, cx + s * 0.95, cy - s * 0.65], fill=col, width=5)

def _motif_scan(d: ImageDraw.Draw, cx: int, cy: int, s: int, col):
    """Medical scan frame + pulse line (radiology / health / medical AI)."""
    d.rectangle([cx - s, cy - s * 0.7, cx + s, cy + s * 0.7], outline=col, width=6)
    d.line([cx - s * 0.8, cy, cx - s * 0.3, cy], fill=col, width=4)
    d.line([cx - s * 0.3, cy, cx - s * 0.1, cy - s * 0.5], fill=col, width=4)
    d.line([cx - s * 0.1, cy - s * 0.5, cx + s * 0.15, cy + s * 0.5], fill=col, width=4)
    d.line([cx + s * 0.15, cy + s * 0.5, cx + s * 0.4, cy - s * 0.2], fill=col, width=4)
    d.line([cx + s * 0.4, cy - s * 0.2, cx + s * 0.8, cy], fill=col, width=4)

def _motif_chip(d: ImageDraw.Draw, cx: int, cy: int, s: int, col):
    """CPU/GPU die (hardware / chip / GPU news)."""
    d.rectangle([cx - s * 0.7, cy - s * 0.7, cx + s * 0.7, cy + s * 0.7], outline=col, width=7)
    d.rectangle([cx - s * 0.32, cy - s * 0.32, cx + s * 0.32, cy + s * 0.32], outline=col, width=4)
    for i in range(-2, 3):
        off = i * (s * 0.35)
        d.line([cx + off, cy - s * 0.7, cx + off, cy - s], fill=col, width=4)
        d.line([cx + off, cy + s * 0.7, cx + off, cy + s], fill=col, width=4)

def _motif_megaphone(d: ImageDraw.Draw, cx: int, cy: int, s: int, col):
    """Megaphone (ads / marketing / launches)."""
    d.polygon([(cx - s * 0.7, cy - s * 0.4), (cx + s * 0.3, cy - s * 0.8),
               (cx + s * 0.3, cy + s * 0.8), (cx - s * 0.7, cy + s * 0.4)], outline=col, width=7)
    d.line([cx + s * 0.3, cy, cx + s, cy - s * 0.5], fill=col, width=6)
    d.line([cx + s * 0.3, cy, cx + s, cy + s * 0.5], fill=col, width=6)
    d.line([cx - s * 0.7, cy, cx - s, cy], fill=col, width=6)

def _motif_rocket(d: ImageDraw.Draw, cx: int, cy: int, s: int, col):
    """Rocket (startup / funding / raise)."""
    d.polygon([(cx, cy - s), (cx - s * 0.5, cy + s * 0.7), (cx + s * 0.5, cy + s * 0.7)], outline=col, width=7)
    d.ellipse([cx - 14, cy - s * 0.4, cx + 14, cy - s * 0.4 + 28], outline=col, width=4)
    d.polygon([(cx - s * 0.5, cy + s * 0.7), (cx - s * 0.8, cy + s), (cx - s * 0.2, cy + s * 0.85)], fill=col)
    d.polygon([(cx + s * 0.5, cy + s * 0.7), (cx + s * 0.8, cy + s), (cx + s * 0.2, cy + s * 0.85)], fill=col)

def _motif_brain(d: ImageDraw.Draw, cx: int, cy: int, s: int, col):
    """Brain / nodes (research / AI breakthrough)."""
    d.ellipse([cx - s * 0.8, cy - s * 0.6, cx, cy + s * 0.6], outline=col, width=6)
    d.ellipse([cx, cy - s * 0.6, cx + s * 0.8, cy + s * 0.6], outline=col, width=6)
    for a in range(-1, 2):
        for b in range(-1, 2):
            x, y = cx + a * s * 0.4, cy + b * s * 0.35
            d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=col)

# Keyword → motif. First match in the title (case-insensitive) wins.
# Order matters: specific story-intent keywords (ads, funding, medical, chip,
# phone) are checked BEFORE the broad AI/LLM/research terms so e.g.
# "Testing ads in ChatGPT" resolves to the megaphone, not a generic chat bubble.
KEYWORD_MOTIFS = [
    (("pixel", "galaxy", "iphone", "phone", "smartphone"), _motif_phone),
    (("radiolog", "medical", "health", "clinical", "care-x", "patient"), _motif_scan),
    (("chip", "gpu", "cpu", "hardware", "processor", "silicon"), _motif_chip),
    (("ad", "ads", "marketing", "sponsor"), _motif_megaphone),
    (("startup", "funding", "raise", "seed", "series", "venture"), _motif_rocket),
    (("chatgpt", "llm", "gpt", "model", "chat bot", "chatbot", "gemini", "claude"), _motif_chat),
    (("research", "breakthrough", "paper", "study", "scientist"), _motif_brain),
]


def _pick_motif(title: str):
    t = title.lower()
    for keys, fn in KEYWORD_MOTIFS:
        if any(k in t for k in keys):
            return fn
    return None



def generate_story_thumbnail(item: dict, index: int, lang: str = "en") -> str:
    """
    Render one story to a PNG and return its path.

    item keys used: title, source, category, total_score.
    index is 1-based position in the digest.
    """
    title = str(item.get("title", "Untitled"))[:140]
    source = str(item.get("source", ""))
    category = str(item.get("category", "other"))
    score = float(item.get("total_score", 0) or 0)
    date_str = str(item.get("_date_str", ""))

    bg, accent = _category_bg(category, score)
    cat_key = CAT_KEY_MAP.get(category.lower(), "OTHER")

    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)

    pad = 70
    inner_w = W - 2 * pad

    # Generative backdrop (behind everything)
    _draw_backdrop(d, seed=title + source, accent=accent)

    # Header: #index + source
    d.text((pad, pad), f"#{index}", font=_font(64, bold=True), fill=accent)
    d.text((pad, pad + 78), source.upper(), font=_font(34), fill="#E5E7EB")
    d.rectangle([pad, pad + 130, W - pad, pad + 138], fill=accent)

    # Category glyph (upper-right focal visual)
    _glyph = GLYPHS.get(cat_key, _glyph_other)
    _glyph(d, cx=W - 230, cy=300, s=120, col=accent)

    # Topic-resonant sub-motif (chosen by title keywords) — makes the card
    # resonate with the specific story. Drawn lower-left, distinct from glyph.
    motif_fn = _pick_motif(title)
    if motif_fn:
        motif_fn(d, cx=270, cy=560, s=140, col=accent)

    # Title (largest element)
    title_font = _font(52, bold=True)
    title_lines = _wrap(title, title_font, inner_w)[:4]
    y = pad + 200
    for ln in title_lines:
        d.text((pad, y), ln, font=title_font, fill="#FFFFFF")
        y += 64

    # Bottom: category pill (no score, no URL)
    foot_y = H - pad - 70
    pill_w = 360
    d.rectangle([pad, foot_y, pad + pill_w, foot_y + 70], fill=accent)
    d.text((pad + 22, foot_y + 16), f"  {cat_key.replace('_', ' ')}",
           font=_font(34, bold=True), fill="#111111")

    out_dir = Path(__file__).parent / "digests"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"thumb_{date_str}_{lang}_{index}.png" if date_str else f"thumb_{lang}_{index}.png"
    out_path = out_dir / fname
    img.save(out_path, "PNG")
    return str(out_path)
