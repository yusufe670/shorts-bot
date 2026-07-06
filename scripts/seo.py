#!/usr/bin/env python3
"""
Hikaye Shorts için SEO metadata üretici (ücretsiz, deterministik).

YouTube kuralları gözetildi:
- En fazla 15 hashtag (fazlası TÜMÜNÜ geçersiz kılar).
- İlk 3 hashtag başlığın üstünde görünür -> en güçlüleri başa koy.
- Etiketlerin toplam karakteri < 500.
- Açıklamanın İLK satırı arama için en önemli -> anahtar kelimeli hook.
"""
import re

# İlk 3 (başlık üstünde görünen) + genel havuz
HASH_PRIMARY = ["#shorts", "#story", "#storytime"]
HASH_UNIVERSAL = [
    "#shortstory", "#aistory", "#storiesforkids", "#bedtimestories",
    "#viral", "#fyp", "#foryou", "#shortsfeed", "#tale", "#animatedstory",
]

TAGS_UNIVERSAL = [
    "shorts", "short story", "story time", "storytime", "ai story",
    "animated story", "story shorts", "bedtime stories", "storytelling",
    "short film", "narrated story", "stories for kids", "moral stories",
    "cartoon story", "story shorts english",
]

GENRE = {
    "adventure": {
        "hash": ["#adventure", "#quest"],
        "tags": ["adventure story", "adventure", "kids adventure", "journey story"],
        "q": "Would you be brave enough to go? 👇",
        "blurb": "an adventure you won't want to miss",
    },
    "mystery": {
        "hash": ["#mystery", "#detective"],
        "tags": ["mystery story", "mystery", "detective story", "whodunit"],
        "q": "Did you solve it before the end? 🕵️ Comment below!",
        "blurb": "a mystery with a twist you won't see coming",
    },
    "fantasy": {
        "hash": ["#fantasy", "#magic"],
        "tags": ["fantasy story", "fantasy", "magic story", "fairytale"],
        "q": "What would you wish for? ✨ Tell me below!",
        "blurb": "a magical tale full of wonder",
    },
    "heartwarming": {
        "hash": ["#wholesome", "#kindness"],
        "tags": ["heartwarming story", "wholesome", "kindness", "feel good story"],
        "q": "Did this warm your heart too? ❤️",
        "blurb": "a heartwarming story that stays with you",
    },
    "space-scifi": {
        "hash": ["#space", "#scifi"],
        "tags": ["space story", "sci fi story", "space adventure", "robot story"],
        "q": "Would you explore the stars? 🚀 Comment below!",
        "blurb": "a space adventure beyond the stars",
    },
    "folktale": {
        "hash": ["#fairytale", "#folktale"],
        "tags": ["folktale", "fairy tale", "moral story", "legend"],
        "q": "What lesson did you take from it? 🌙",
        "blurb": "a timeless tale with a meaningful lesson",
    },
}
DEFAULT_GENRE = {
    "hash": ["#tale", "#storyshorts"],
    "tags": ["story", "short story"],
    "q": "What did you think? 👇 Comment below!",
    "blurb": "a short story you won't forget",
}

EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF"
    "\U00002190-\U000021FF\U00002300-\U000023FF\U0000FE00-\U0000FE0F\U0000200D]"
)


def _clean(text: str) -> str:
    text = EMOJI.sub("", text)
    text = re.sub(r"#\w+", "", text)
    return re.sub(r"\s+", " ", text).strip(" -–—|")


def _genre(story: dict) -> dict:
    key = (story.get("genre") or "").strip().lower().replace(" ", "-").replace("/", "-")
    for k, v in GENRE.items():
        if k in key or key in k:
            return v
    return DEFAULT_GENRE


def build_hashtags(story: dict) -> list:
    g = _genre(story)
    tags = []
    for t in HASH_PRIMARY + g["hash"] + HASH_UNIVERSAL:
        low = t.lower()
        if low not in [x.lower() for x in tags]:
            tags.append(t)
        if len(tags) >= 15:   # YouTube sınırı
            break
    return tags


def build_tags(story: dict) -> list:
    g = _genre(story)
    raw = list(story.get("tags", [])) + g["tags"] + TAGS_UNIVERSAL
    out, seen, total = [], set(), 0
    for t in raw:
        t = str(t).strip().lower()
        if not t or t in seen:
            continue
        if total + len(t) + 1 > 480:
            break
        seen.add(t)
        out.append(t)
        total += len(t) + 1
    return out


def build_title(story: dict) -> str:
    title = story["title"].strip()
    if "#shorts" not in title.lower():
        room = 100 - len(" #shorts")
        title = (title[:room].rstrip() + " #shorts")
    return title[:100]


def build_description(story: dict) -> str:
    g = _genre(story)
    hook = _clean(story["title"])
    first_scene = _clean(story["scenes"][0]["text"]) if story.get("scenes") else ""
    lines = [
        hook + " 🎬",
        "",
        f"{first_scene}",
        f"Watch till the end — {g['blurb']}.",
        "",
        f"💬 {g['q']}",
        "👉 Follow for a new AI story every few hours!",
        "🔔 Like & subscribe so you never miss one.",
        "",
        " ".join(build_hashtags(story)),
    ]
    return "\n".join(x for x in lines if x is not None).strip()


def build_seo_meta(story: dict, cfg: dict) -> dict:
    return {
        "title": build_title(story),
        "description": build_description(story),
        "tags": build_tags(story),
        "categoryId": str(cfg.get("categoryId", "24")),
        "privacyStatus": cfg.get("privacyStatus", "public"),
        "madeForKids": bool(cfg.get("madeForKids", False)),
        "defaultLanguage": cfg.get("defaultLanguage", "en"),
    }


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path
    bank = json.loads((Path(__file__).resolve().parent.parent / "content" / "stories.json").read_text(encoding="utf-8"))
    cfg = json.loads((Path(__file__).resolve().parent.parent / "config.json").read_text(encoding="utf-8"))
    i = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    print(json.dumps(build_seo_meta(bank[i], cfg), ensure_ascii=False, indent=2))
