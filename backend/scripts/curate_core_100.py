#!/usr/bin/env python3
"""Curate a child-friendly Core 100 content set for audio generation.

Design decisions:
- Prioritise concrete nouns and common verbs; deprioritise abstract/adult words.
- Include 5 /ʒ/ words from the candidate pool.
- Apply manual phoneme-tag overrides for /ʌ/ and /ɚ/ gaps (ipa-dict convention).
- Tag every entry with ``difficulty_tags`` for phoneme-based practice routing.
- Produce ``content/core_100_words.json``.

Usage:
    cd backend && source .venv/bin/activate
    python scripts/curate_core_100.py
"""

from __future__ import annotations

import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent

AUTO_CANDIDATES = _REPO / "content" / "generated" / "core_100_candidates.json"
FULL_POOL = _REPO / "content" / "generated" / "candidate_words.json"
OUTPUT = _REPO / "content" / "core_100_words.json"

# ---------------------------------------------------------------------------
# Exclude list — words that are not child-friendly, not concrete enough,
# or better replaced with more useful vocabulary.
# ---------------------------------------------------------------------------

EXCLUDE_WORDS: set[str] = {
    # Adult / abstract / finance / bureaucracy
    "war", "tax", "fees", "cash", "issue", "via", "thus",
    "epic", "hip", "chief", "offer", "area", "allow",
    "bomb", "shit", "guys", "death", "jail",
    # Abbreviations or domain-specific
    "id", "ok", "vs", "tho", "lab", "gym",
    # Function-word-heavy or vague
    "hers", "none", "ends", "each", "such", "than",
    "them", "then", "they", "upon", "from",
    # Past-tense-only forms where present could be better
    "grew", "kept", "sent", "sold",
}

# ---------------------------------------------------------------------------
# Manual /ʌ/ and /ɚ/ phoneme-tag overrides
#
# ipa-dict uses /ə/ (schwa) where many phoneme inventories expect /ʌ/,
# and /ɝ/ (stressed r-coloured) where /ɚ/ (unstressed) is expected.
# We add manual overrides so Core 100 reports coverage for both tags.
# ---------------------------------------------------------------------------

PHONEME_OVERRIDES: dict[str, list[str]] = {
    # /ʌ/ words from ipa-dict (they have /ə/ in source, we add /ʌ/)
    "cup":   ["/ə/", "/ʌ/"],
    "love":  ["/ə/", "/ʌ/"],
    "sun":   ["/ə/", "/ʌ/"],
    "bus":   ["/ə/", "/ʌ/"],
    "run":   ["/ə/", "/ʌ/"],
    "jump":  ["/ə/", "/ʌ/"],
    "duck":  ["/ə/", "/ʌ/"],
    "luck":  ["/ə/", "/ʌ/"],
    "cut":   ["/ə/", "/ʌ/"],
    "fun":   ["/ə/", "/ʌ/"],
    # /ɚ/ words from ipa-dict (they have /ɝ/ in source, we add /ɚ/)
    "teacher": ["/ɝ/", "/ɚ/"],
    "sister":  ["/ɝ/", "/ɚ/"],
    "water":   ["/ɝ/", "/ɚ/"],
    "river":   ["/ɝ/", "/ɚ/"],
    "paper":   ["/ɝ/", "/ɚ/"],
    "mother":  ["/ɝ/", "/ɚ/"],
    "father":  ["/ɝ/", "/ɚ/"],
    "brother": ["/ɝ/", "/ɚ/"],
    "better":  ["/ɝ/", "/ɚ/"],
    "letter":  ["/ɝ/", "/ɚ/"],
}

# ---------------------------------------------------------------------------
# Difficulty tags — assigned per word based on phonemes/contrasts
# ---------------------------------------------------------------------------

_DIFFICULT_PHONEMES: dict[str, str] = {
    "/θ/": "th_voiceless",
    "/ð/": "th_voiced",
    "/ʃ/": "sh",
    "/ʒ/": "zh",
    "/tʃ/": "ch",
    "/dʒ/": "j",
    "/v/": "v",
    "/w/": "w",
    "/l/": "l",
    "/r/": "r",
    "/ŋ/": "ng",
    "/ʌ/": "cup_vowel",
    "/ɚ/": "r_schwa",
    "/ɝ/": "r_stressed",
}

_VOWEL_CONTRASTS: dict[str, str] = {
    "/iː/": "long_i",
    "/ɪ/": "short_i",
    "/uː/": "long_u",
    "/ʊ/": "short_u",
    "/e/": "short_e",
    "/æ/": "short_a",
    "/ɑ/": "broad_a",
    "/ɔ/": "open_o",
}

_DIPHTHONG_TAGS: dict[str, str] = {
    "/eɪ/": "diphthong",
    "/aɪ/": "diphthong",
    "/oʊ/": "diphthong",
    "/aʊ/": "diphthong",
    "/ɔɪ/": "diphthong",
}


def assign_difficulty_tags(phoneme_tags_us: list[str]) -> list[str]:
    """Derive difficulty tags from a word's US phoneme tags."""
    tags: set[str] = set()
    for p in phoneme_tags_us:
        if p in _DIFFICULT_PHONEMES:
            tags.add(_DIFFICULT_PHONEMES[p])
        if p in _VOWEL_CONTRASTS:
            tags.add(_VOWEL_CONTRASTS[p])
        if p in _DIPHTHONG_TAGS:
            tags.add(_DIPHTHONG_TAGS[p])
    return sorted(tags)


# ---------------------------------------------------------------------------
# Chinese meanings (child-friendly, short)
# ---------------------------------------------------------------------------

MEANING_MAP: dict[str, str] = {
    # Core auto-selected words that survive excludes
    "about": "关于；大约",
    "age": "年龄",
    "ago": "…以前",
    "air": "空气",
    "arm": "手臂",
    "art": "艺术",
    "baby": "婴儿",
    "back": "背部；后面",
    "bag": "包",
    "ball": "球",
    "bank": "银行；河岸",
    "bed": "床",
    "bell": "铃铛",
    "best": "最好的",
    "bird": "鸟",
    "blue": "蓝色",
    "boat": "船",
    "book": "书",
    "box": "盒子",
    "boy": "男孩",
    "boys": "男孩们",
    "cake": "蛋糕",
    "call": "打电话；叫",
    "came": "来（过去式）",
    "card": "卡片",
    "cat": "猫",
    "chat": "聊天",
    "check": "检查",
    "city": "城市",
    "coat": "外套",
    "cold": "冷的；感冒",
    "come": "来",
    "cook": "做饭",
    "cool": "凉爽的；酷的",
    "cup": "杯子",
    "dark": "黑暗的",
    "date": "日期",
    "dead": "死的",
    "deep": "深的",
    "desk": "书桌",
    "dirt": "泥土",
    "dog": "狗",
    "door": "门",
    "down": "向下",
    "draw": "画画",
    "drop": "掉落",
    "duck": "鸭子",
    "early": "早的",
    "east": "东方",
    "edge": "边缘",
    "face": "脸",
    "fact": "事实",
    "fall": "秋天；落下",
    "farm": "农场",
    "fast": "快的",
    "feet": "脚（复数）",
    "fill": "填满",
    "film": "电影",
    "find": "找到",
    "fire": "火",
    "first": "第一",
    "fish": "鱼",
    "five": "五",
    "food": "食物",
    "foot": "脚",
    "form":  "形状；表格",
    "four": "四",
    "free": "自由的；免费的",
    "full": "满的",
    "fun": "有趣的；乐趣",
    "game": "游戏",
    "gave": "给（过去式）",
    "girl": "女孩",
    "give": "给",
    "glad": "高兴的",
    "goal": "目标；球门",
    "goes": "去（第三人称）",
    "gold": "金子；金色",
    "good": "好的",
    "grow": "生长",
    "half": "一半",
    "hand": "手",
    "hang": "悬挂",
    "hard": "硬的；困难的",
    "hat": "帽子",
    "head": "头",
    "hear": "听见",
    "help": "帮助",
    "high": "高的",
    "hill": "小山",
    "home": "家",
    "hope": "希望",
    "hours": "小时（复数）",
    "huge": "巨大的",
    "inch": "英寸",
    "item": "物品；项目",
    "jack": "杰克（人名）",
    "join": "加入",
    "jump": "跳",
    "kind": "善良的；种类",
    "king": "国王",
    "knew": "知道（过去式）",
    "last": "最后的；上一个",
    "late": "迟的",
    "leave": "离开",
    "left": "左边",
    "life": "生活；生命",
    "lift": "举起",
    "like": "喜欢；像",
    "line": "线；行",
    "list": "列表",
    "live": "居住",
    "long": "长的",
    "look": "看",
    "loss": "损失",
    "lots": "许多",
    "love": "爱",
    "luck": "运气",
    "made": "做（过去式）",
    "make": "做；制作",
    "many": "许多",
    "map": "地图",
    "match": "比赛；匹配",
    "milk": "牛奶",
    "mind": "头脑；介意",
    "miss": "想念；错过",
    "more": "更多",
    "most": "最多",
    "move": "移动",
    "much": "很多",
    "must": "必须",
    "name": "名字",
    "near": "附近的；靠近",
    "need": "需要",
    "new": "新的",
    "news": "新闻",
    "next": "下一个",
    "nice": "好的；令人愉快的",
    "north": "北方",
    "note": "笔记；注意",
    "once": "一次；曾经",
    "open": "打开",
    "other": "其他的",
    "over": "在…上方；结束",
    "page": "页",
    "paid": "支付（过去式）",
    "park": "公园；停车",
    "part": "部分",
    "pass": "通过",
    "pick": "挑选",
    "plan": "计划",
    "play": "玩",
    "pull": "拉",
    "push": "推",
    "rain": "雨",
    "read": "阅读",
    "rest": "休息",
    "rich": "富有的",
    "ride": "骑",
    "ring": "戒指；铃声",
    "rise": "上升",
    "rock": "石头",
    "roll": "滚动",
    "room": "房间",
    "rule": "规则",
    "run": "跑",
    "rush": "冲；匆忙",
    "safe": "安全的",
    "said": "说（过去式）",
    "salt": "盐",
    "same": "相同的",
    "save": "保存；救",
    "seat": "座位",
    "seed": "种子",
    "send": "发送",
    "ship": "船",
    "shop": "商店",
    "show": "展示",
    "shows": "展示（第三人称）",
    "sick": "生病的",
    "side": "旁边；侧面",
    "sign": "标志；签名",
    "sing": "唱歌",
    "size": "尺寸",
    "skin": "皮肤",
    "slow": "慢的",
    "snow": "雪",
    "soft": "柔软的",
    "soil": "土壤",
    "some": "一些",
    "song": "歌曲",
    "soon": "很快",
    "sort": "种类；排序",
    "south": "南方",
    "star": "星星",
    "stay": "停留",
    "step": "步骤；脚步",
    "stop": "停止",
    "suit": "套装；适合",
    "sun": "太阳",
    "sure": "确定的",
    "take": "拿；带",
    "talk": "说话",
    "tall": "高的",
    "team": "团队",
    "tell": "告诉",
    "test": "测试",
    "thin": "薄的；瘦的",
    "thing": "东西；事情",
    "think": "想；认为",
    "this": "这个",
    "three": "三",
    "time": "时间",
    "told": "告诉（过去式）",
    "took": "拿（过去式）",
    "tree": "树",
    "trip": "旅行",
    "true": "真的",
    "turn": "转；轮到",
    "type": "类型；打字",
    "unit": "单元",
    "very": "非常",
    "view": "视野；观点",
    "voice": "声音",
    "wait": "等待",
    "walk": "走路",
    "wall": "墙",
    "want": "想要",
    "warm": "温暖的",
    "wash": "洗",
    "watch": "手表；观看",
    "wave": "波浪；挥手",
    "week": "周；星期",
    "well": "好地；井",
    "went": "去（过去式）",
    "west": "西方",
    "what": "什么",
    "why": "为什么",
    "wide": "宽的",
    "wife": "妻子",
    "will": "将会",
    "wind": "风",
    "wing": "翅膀",
    "wish": "希望；祝愿",
    "with": "和…一起；用",
    "wood": "木头",
    "word": "单词",
    "work": "工作",
    "wrong": "错误的",
    "year": "年",
    "years": "年份（复数）",
    "bus": "公交车",
    "cut": "切；割",
    "paper": "纸",
    "power": "力量；电力",
    "river": "河流",
    "sister": "姐妹",
    "teacher": "老师",
    "water": "水",
    "your": "你的",
    "zone": "区域",

    # /ʒ/ words added
    "measure": "测量；措施",
    "pleasure": "快乐；愉快",
    "usual": "通常的",
    "usually": "通常",
    "vision": "视力；视野",
}


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    with open(AUTO_CANDIDATES, "r", encoding="utf-8") as f:
        auto = json.load(f)
    with open(FULL_POOL, "r", encoding="utf-8") as f:
        full_pool = json.load(f)

    full_by_word: dict[str, dict] = {w["word"]: w for w in full_pool}

    # --- Step 1: filter auto-selected, exclude unfriendly words ----------
    curated: list[dict] = []
    existing_words: set[str] = set()

    for w in auto:
        word = w["word"]
        if word in EXCLUDE_WORDS:
            continue
        entry = _enrich(w, word)
        curated.append(entry)
        existing_words.add(word)

    # --- Step 2: add /ʒ/ words -------------------------------------------
    zh_words = ["measure", "pleasure", "usual", "usually", "vision"]
    for zw in zh_words:
        if zw in existing_words:
            continue
        if zw in full_by_word:
            entry = _enrich(full_by_word[zw], zw)
            curated.append(entry)
            existing_words.add(zw)

    # --- Step 3: fill to 100 with concrete words, prioritising /ʌ/ /ɚ/ --
    FILLER_POOL = [
        # /ʌ/ sound words (ipa-dict uses /ə/ — we override in Step 4)
        "cup", "sun", "run", "bus", "duck", "luck", "cut", "fun", "jump",
        # /ɚ/ sound words (ipa-dict uses /ɝ/ — we override in Step 4)
        "teacher", "sister", "water", "river", "paper",
        # General concrete words
        "hat", "dog", "cat", "ship", "sheep", "bed", "milk", "star",
        "tree", "rain", "snow", "cake", "book", "door", "hand",
    ]
    for fw in FILLER_POOL:
        if len(curated) >= 100:
            break
        if fw in existing_words:
            continue
        if fw in full_by_word:
            entry = _enrich(full_by_word[fw], fw)
            curated.append(entry)
            existing_words.add(fw)

    # --- Step 4: apply phoneme-tag overrides for /ʌ/ /ɚ/ -----------------
    for entry in curated:
        word = entry["word"]
        if word in PHONEME_OVERRIDES:
            entry["phoneme_tags_us"] = PHONEME_OVERRIDES[word]
            entry["_phoneme_override_note"] = (
                "ipa-dict uses /ə/ for /ʌ/ and /ɝ/ for /ɚ/; "
                "manual override applied for learner-facing phoneme coverage"
            )

    # --- Step 5: assign difficulty_tags ----------------------------------
    for entry in curated:
        entry["difficulty_tags"] = assign_difficulty_tags(
            entry.get("phoneme_tags_us", [])
        )

    # Sort by word
    curated.sort(key=lambda w: w["word"])

    # Add a top-level coverage note
    output: dict = {
        "_note": (
            "Core 100 curated for child-friendly early IPA practice. "
            "/ʌ/ and /ɚ/ phoneme tags are manually overridden where ipa-dict "
            "uses /ə/ and /ɝ/ respectively. See individual _phoneme_override_note "
            "fields for per-word details. "
            "/ʒ/ words included: measure, pleasure, usual, usually, vision."
        ),
        "words": curated,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Report
    zh_count = sum(1 for w in curated if "/ʒ/" in str(w.get("phoneme_tags_us", [])))
    ov_count = sum(1 for w in curated if w.get("_phoneme_override_note"))
    no_tags = [w["word"] for w in curated if not w.get("difficulty_tags")]
    no_meaning = [w["word"] for w in curated if not w.get("meaning_zh")]
    print(f"Curated {len(curated)} words -> {OUTPUT}")
    print(f"  /ʒ/ words: {zh_count}")
    print(f"  /ʌ/ or /ɚ/ override words: {ov_count}")
    print(f"  All have difficulty_tags: {len(no_tags) == 0} (missing: {no_tags})")
    print(f"  All have meaning_zh: {len(no_meaning) == 0} (missing: {no_meaning})")


def _enrich(src: dict, word: str) -> dict:
    """Copy a source entry and fill in Core 100 required fields."""
    entry: dict = dict(src)
    entry["content_status"] = "core_selected"
    entry["review_status_us"] = src.get("review_status_us", "auto_checked")
    entry["review_status_uk"] = src.get("review_status_uk", "auto_checked")
    entry["audio_us"] = f"/audio/us/{word}.mp3"
    entry["audio_uk"] = None
    entry["meaning_zh"] = MEANING_MAP.get(word, src.get("meaning_zh"))

    # Ensure all expected fields exist
    entry.setdefault("ipa_uk", src.get("ipa_uk"))
    entry.setdefault("phoneme_tags_uk", src.get("phoneme_tags_uk"))
    entry.setdefault("difficulty_tags", [])
    entry.setdefault("minimal_pair_group", src.get("minimal_pair_group"))
    entry.setdefault("example", src.get("example"))
    entry.setdefault("frequency_zipf", src.get("frequency_zipf"))
    entry.setdefault("candidate_score", src.get("candidate_score"))
    entry.setdefault("source_ipa_us", src.get("source_ipa_us", "open-dict-data/ipa-dict en_US"))
    entry.setdefault("source_ipa_uk", src.get("source_ipa_uk", "open-dict-data/ipa-dict en_UK"))
    entry.setdefault("source_frequency", src.get("source_frequency", "wordfreq"))
    entry.setdefault("license_notes", src.get("license_notes", "open-data"))
    entry.setdefault("audio_status_us", "planned")
    entry.setdefault("audio_status_uk", None)
    entry.setdefault("audio_provider_us", None)
    entry.setdefault("audio_voice_us", None)
    entry.setdefault("audio_generated_at", None)

    return entry


if __name__ == "__main__":
    main()
