#!/usr/bin/env python3
"""
Her parça için ücretsiz, LLM'siz başlık + açıklama + etiket üretir.
Deterministik: aynı part index -> aynı metadata (tekrar yüklemede tutarlı).
"""

# Family-friendly English attention "hooks". Rotates by part index.
HOOKS = [
    "Watch Till the End 👀",
    "You Won't Believe This! 😮",
    "Everyone's Talking About This",
    "Wait For It...",
    "Don't Miss This!",
    "This Is Amazing! 🤩",
    "So Satisfying to Watch",
    "How Did They Do That? 🤯",
    "This Made My Day 😄",
    "It Gets Even Better 🔥",
    "You'll Want to See This",
    "The Best Part Is Coming",
]

# Hashtag pool appended to the title (rotates)
HASHTAG_SETS = [
    "#shorts #viral #fun",
    "#shorts #fyp #trending",
    "#shorts #viral #explore",
    "#shorts #fun #fyp",
]

MAX_TITLE = 100  # YouTube başlık limiti


def build_metadata(index: int, cfg: dict) -> dict:
    """index: 0-tabanlı parça numarası. cfg: config.json içeriği."""
    part_no = index + 1
    base = (cfg.get("base_title") or "").strip()
    series = (cfg.get("series_name") or "").strip()

    hook = HOOKS[index % len(HOOKS)]
    hashtags = HASHTAG_SETS[index % len(HASHTAG_SETS)]

    # Başlık: [Seri Bölüm X] + Temel Başlık + Hook + hashtag
    pieces = []
    if series:
        pieces.append(f"{series} Part {part_no}")
    if base:
        pieces.append(base)
    pieces.append(hook)

    core = " | ".join(pieces)
    title = f"{core} {hashtags}".strip()
    if len(title) > MAX_TITLE:
        # try without hashtags, still too long -> cut
        title = core[:MAX_TITLE].rstrip()

    series_line = ""
    if series:
        series_line = f"Part {part_no} of the {series} series.\n\n"

    desc_tmpl = cfg.get(
        "description_template",
        "{title}\n\n{series}#shorts",
    )
    description = desc_tmpl.format(title=core, series=series_line)

    # Tags (from config) + a few automatic ones
    tags = list(cfg.get("tags", []))
    for extra in ["shorts", f"part {part_no}", "english shorts", "family friendly"]:
        if extra not in tags:
            tags.append(extra)
    # YouTube toplam etiket karakter limiti ~500; güvenli tarafta kal
    trimmed, total = [], 0
    for t in tags:
        total += len(t) + 1
        if total > 480:
            break
        trimmed.append(t)

    return {
        "title": title,
        "description": description,
        "tags": trimmed,
    }


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    cfg = json.loads((Path(__file__).resolve().parent.parent / "config.json").read_text(encoding="utf-8"))
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    print(json.dumps(build_metadata(n, cfg), ensure_ascii=False, indent=2))
