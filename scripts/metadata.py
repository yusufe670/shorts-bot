#!/usr/bin/env python3
"""
Her parça için ücretsiz, LLM'siz başlık + açıklama + etiket üretir.
Deterministik: aynı part index -> aynı metadata (tekrar yüklemede tutarlı).
"""

# Dikkat çekici Türkçe "hook" şablonları. {n} parça numarası ile değişir.
HOOKS = [
    "Bunu Sonuna Kadar İzle 👀",
    "İnanamayacaksın 😱",
    "Herkes Bunu Konuşuyor",
    "Sonu Seni Şaşırtacak",
    "Bunu Kaçırma!",
    "Beklemediğin An Geldi",
    "Bir Kez İzleyince Duramayacaksın",
    "Bu Nasıl Oldu? 🤯",
    "İzleyen Herkes Şok Oldu",
    "Devamı Daha da İyi 🔥",
    "Gözlerine İnanamayacaksın",
    "Bu Anı Bekliyordun",
]

# Başlık sonuna eklenecek hashtag havuzu (rotasyonla)
HASHTAG_SETS = [
    "#shorts #keşfet #viral",
    "#shorts #fyp #trend",
    "#shorts #viral #keşfet",
    "#shorts #eğlence #fyp",
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
        pieces.append(f"{series} Bölüm {part_no}")
    if base:
        pieces.append(base)
    pieces.append(hook)

    core = " | ".join(pieces)
    title = f"{core} {hashtags}".strip()
    if len(title) > MAX_TITLE:
        # hashtag'siz dene, yine uzunsa kes
        title = core[:MAX_TITLE].rstrip()

    series_line = ""
    if series:
        series_line = f"{series} serisinin {part_no}. bölümü.\n\n"

    desc_tmpl = cfg.get(
        "description_template",
        "{title}\n\n{series}#shorts",
    )
    description = desc_tmpl.format(title=core, series=series_line)

    # Etiketler (config) + otomatik birkaç tanesi
    tags = list(cfg.get("tags", []))
    for extra in ["shorts", f"bölüm {part_no}", "türkçe shorts"]:
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
