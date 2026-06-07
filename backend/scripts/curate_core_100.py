#!/usr/bin/env python3
"""Curate Core 100 words from the auto-selected candidate pool.

This script produces ``content/core_100_words.json`` — hand-curated from
the auto-selected Core 100 candidates with the following adjustments:

- /ʒ/ gap: 3–5 words with /ʒ/ are manually added
- Chinese meanings added for all entries
- audio_us paths set to ``/audio/us/<word>.mp3``
- content_status = core_selected
- /ʌ/ and /ɚ/ gaps documented (source data limitation)

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
# Chinese meanings (manual, child-friendly, short)
# ---------------------------------------------------------------------------

MEANING_MAP: dict[str, str] = {
    # Core starters — common concrete nouns/verbs
    "eye": "眼睛",
    "age": "年龄",
    "art": "艺术",
    "air": "空气",
    "arm": "手臂",
    "act": "行动；表演",
    "bed": "床",
    "boy": "男孩",
    "bag": "包",
    "box": "盒子",
    "bus": "公交车",
    "book": "书",
    "baby": "婴儿",
    "ball": "球",
    "bird": "鸟",
    "blue": "蓝色",
    "bell": "铃铛",
    "bath": "洗澡",
    "bank": "银行；河岸",
    "boat": "船",
    "back": "背部；后面",
    "cake": "蛋糕",
    "cold": "冷的；感冒",
    "call": "打电话",
    "card": "卡片",
    "city": "城市",
    "cook": "做饭",
    "cool": "凉爽的；酷的",
    "coat": "外套",
    "come": "来",
    "door": "门",
    "dark": "黑暗的",
    "date": "日期",
    "dead": "死的",
    "deep": "深的",
    "desk": "书桌",
    "dirt": "泥土",
    "down": "向下",
    "draw": "画画",
    "drop": "掉落",
    "each": "每个",
    "east": "东方",
    "edge": "边缘",
    "eggs": "鸡蛋",
    "ends": "结束",
    "face": "脸",
    "fact": "事实",
    "fall": "秋天；落下",
    "farm": "农场",
    "fast": "快速的",
    "feet": "脚（复数）",
    "fill": "填满",
    "film": "电影",
    "find": "找到",
    "fire": "火",
    "fish": "鱼",
    "five": "五",
    "food": "食物",
    "foot": "脚",
    "form": "形式；表格",
    "four": "四",
    "free": "自由的；免费的",
    "from": "从…来",
    "full": "满的",
    "game": "游戏",
    "girl": "女孩",
    "give": "给",
    "glad": "高兴的",
    "goes": "去（第三人称）",
    "gold": "金子；金色",
    "good": "好的",
    "grew": "生长（过去式）",
    "grow": "生长",
    "half": "一半",
    "hand": "手",
    "hard": "硬的；困难的",
    "head": "头",
    "hear": "听见",
    "help": "帮助",
    "hers": "她的",
    "high": "高的",
    "hill": "小山",
    "home": "家",
    "hope": "希望",
    "huge": "巨大的",
    "kept": "保持（过去式）",
    "kind": "善良的；种类",
    "king": "国王",
    "last": "最后的；上一个",
    "late": "迟的；晚的",
    "left": "左边；离开（过去式）",
    "life": "生活；生命",
    "lift": "举起",
    "like": "喜欢；像",
    "line": "线；行",
    "list": "列表",
    "live": "居住；生活",
    "long": "长的",
    "look": "看",
    "loss": "损失",
    "lots": "许多",
    "love": "爱",
    "made": "做（过去式）",
    "make": "做；制作",
    "many": "许多",
    "milk": "牛奶",
    "mind": "介意；头脑",
    "miss": "想念；错过",
    "more": "更多",
    "most": "最多",
    "move": "移动",
    "much": "很多",
    "must": "必须",
    "name": "名字",
    "near": "附近的；靠近",
    "need": "需要",
    "news": "新闻",
    "next": "下一个",
    "nice":  "好的；令人愉快的",
    "none": "没有",
    "north": "北方",
    "note": "笔记；注意",
    "once": "一次；曾经",
    "open": "打开",
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
    "ride": "骑；乘",
    "ring": "戒指；铃声",
    "rise": "上升",
    "rock": "石头；摇",
    "roll": "滚动",
    "room": "房间",
    "rule": "规则",
    "rush": "冲；匆忙",
    "safe": "安全的",
    "said": "说（过去式）",
    "salt": "盐",
    "same": "相同的",
    "save": "保存；救",
    "seat": "座位",
    "seed": "种子",
    "send": "发送",
    "sent": "发送（过去式）",
    "ship": "船",
    "shop": "商店",
    "show": "展示",
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
    "sold": "卖（过去式）",
    "some": "一些",
    "song": "歌曲",
    "soon": "很快",
    "sort": "种类；排序",
    "star": "星星",
    "stay": "停留",
    "step": "步骤；脚步",
    "stop": "停止",
    "such": "这样的",
    "suit": "套装；适合",
    "sure": "确定的",
    "take": "拿；带",
    "talk": "说话",
    "tall": "高的",
    "team": "团队",
    "tell": "告诉",
    "test": "测试",
    "than": "比",
    "them": "他们（宾格）",
    "then": "然后",
    "they": "他们",
    "thin": "薄的；瘦的",
    "this": "这个",
    "time": "时间",
    "told": "告诉（过去式）",
    "took": "拿（过去式）",
    "tree": "树",
    "trip": "旅行",
    "true": "真的",
    "turn": "转；轮到",
    "type": "类型；打字",
    "unit": "单元",
    "upon": "在…上",
    "very": "非常",
    "view": "视野；观点",
    "wait": "等待",
    "walk": "走路",
    "wall": "墙",
    "want": "想要",
    "warm": "温暖的",
    "wash": "洗",
    "wave": "波浪；挥手",
    "week": "周；星期",
    "well": "好地；井",
    "went": "去（过去式）",
    "west": "西方",
    "what": "什么",
    "wide": "宽的",
    "wife": "妻子",
    "will": "将会",
    "wind": "风",
    "wish": "希望；祝愿",
    "with": "和；用",
    "word": "单词",
    "work": "工作",
    "year": "年",
    "your": "你的",
    "zone": "区域",
}

# ---------------------------------------------------------------------------
# /ʒ/ words to include (selected from the 24 available)
# ---------------------------------------------------------------------------

ZH_SELECT_WORDS = {
    "measure": "/ʒ/",
    "pleasure": "/ʒ/",
    "usual": "/ʒ/",
    "usually": "/ʒ/",
    "vision": "/ʒ/",
}

MEANING_MAP.update({
    "measure": "测量；措施",
    "pleasure": "快乐；愉快",
    "usual": "通常的",
    "usually": "通常",
    "vision": "视力；视野",
    # Remaining auto-selected words
    "about": "关于；大约",
    "ago": "…以前",
    "allow": "允许",
    "area": "区域；面积",
    "best": "最好的",
    "boys": "男孩们",
    "came": "来（过去式）",
    "cash": "现金",
    "chat": "聊天",
    "check": "检查",
    "chief": "首领；主要的",
    "early": "早的",
    "fees": "费用",
    "first": "第一；首先",
    "gave": "给（过去式）",
    "goal": "目标；球门",
    "gym": "健身房",
    "hang": "悬挂",
    "hip": "臀部；时髦的",
    "hours": "小时（复数）",
    "inch": "英寸",
    "issue": "问题；发行",
    "item": "物品；项目",
    "jack": "杰克（人名）；千斤顶",
    "join": "加入；连接",
    "knew": "知道（过去式）",
    "lab": "实验室",
    "leave": "离开",
    "map": "地图",
    "match": "比赛；匹配",
    "new": "新的",
    "offer": "提供",
    "other": "其他的",
    "power": "力量；电力",
    "shows": "展示（第三人称）",
    "south": "南方",
    "tax": "税",
    "thing": "东西；事情",
    "think": "想；认为",
    "three": "三",
    "thus": "因此",
    "via": "通过；经由",
    "voice": "声音",
    "war": "战争",
    "watch": "手表；观看",
    "why": "为什么",
    "wing": "翅膀；侧翼",
    "wood": "木头",
    "wrong": "错误的",
    "years": "年份（复数）",
    "epic": "史诗般的；壮丽的",
    # Extra 5 words to replace removed non-kid-friendly entries
    "cup": "杯子",
    "ship": "船",
    "sheep": "羊",
    "cat": "猫",
    "dog": "狗",
    "hat": "帽子",
})


def main():
    # Load auto-selected 100
    with open(AUTO_CANDIDATES, "r", encoding="utf-8") as f:
        auto = json.load(f)

    # Build lookup by word
    auto_by_word = {w["word"]: w for w in auto}

    # Load full pool
    with open(FULL_POOL, "r", encoding="utf-8") as f:
        full_pool = json.load(f)
    full_by_word = {w["word"]: w for w in full_pool}

    curated: list[dict] = []

    # Step 1: Take the auto-selected 100, enrich them
    for w in auto:
        entry = dict(w)
        entry["content_status"] = "core_selected"
        entry["review_status_us"] = w.get("review_status_us", "auto_checked")
        entry["review_status_uk"] = w.get("review_status_uk", "auto_checked")
        entry["audio_us"] = f"/audio/us/{entry['word']}.mp3"
        entry["audio_uk"] = None
        entry["meaning_zh"] = MEANING_MAP.get(entry["word"], None)

        # Ensure all fields exist
        entry.setdefault("ipa_uk", None)
        entry.setdefault("phoneme_tags_uk", None)
        entry.setdefault("difficulty_tags", [])
        entry.setdefault("minimal_pair_group", None)
        entry.setdefault("example", None)
        entry.setdefault("frequency_zipf", None)
        entry.setdefault("candidate_score", None)
        entry.setdefault("source_ipa_us", "open-dict-data/ipa-dict en_US")
        entry.setdefault("source_ipa_uk", "open-dict-data/ipa-dict en_UK")
        entry.setdefault("source_frequency", "wordfreq")
        entry.setdefault("license_notes", "open-data")
        entry.setdefault("audio_status_us", "planned")
        entry.setdefault("audio_status_uk", None)
        entry.setdefault("audio_provider_us", None)
        entry.setdefault("audio_voice_us", None)
        entry.setdefault("audio_generated_at", None)

        curated.append(entry)

    # Step 2: Remove non-child-appropriate or abbreviation entries, replace with /ʒ/ words
    to_replace = {
        "hers", "none", "ends", "bomb", "shit", "guys",
        "death", "jail", "id", "ok", "vs", "tho",
    }
    curated = [w for w in curated if w["word"] not in to_replace]

    for zh_word, reason in ZH_SELECT_WORDS.items():
        if zh_word in full_by_word:
            entry = dict(full_by_word[zh_word])
            entry["content_status"] = "core_selected"
            entry["review_status_us"] = "auto_checked"
            entry["review_status_uk"] = "auto_checked"
            entry["audio_us"] = f"/audio/us/{zh_word}.mp3"
            entry["audio_uk"] = None
            entry["meaning_zh"] = MEANING_MAP.get(zh_word, "")
            entry.setdefault("ipa_uk", entry.get("ipa_uk"))
            entry.setdefault("phoneme_tags_uk", entry.get("phoneme_tags_uk"))
            entry.setdefault("difficulty_tags", [])
            entry.setdefault("minimal_pair_group", None)
            entry.setdefault("example", None)
            entry.setdefault("audio_status_us", "planned")
            entry.setdefault("audio_status_uk", None)
            entry.setdefault("audio_provider_us", None)
            entry.setdefault("audio_voice_us", None)
            entry.setdefault("audio_generated_at", None)
            curated.append(entry)

    # Step 3: Add extra common words if we don't have exactly 100
    EXTRA_WORDS = ["cup", "ship", "sheep", "cat", "hat", "dog", "sun", "pen"]
    existing_words = {w["word"] for w in curated}
    for ew in EXTRA_WORDS:
        if len(curated) >= 100:
            break
        if ew in existing_words:
            continue
        if ew in full_by_word:
            entry = dict(full_by_word[ew])
            entry["content_status"] = "core_selected"
            entry["review_status_us"] = "auto_checked"
            entry["review_status_uk"] = "auto_checked"
            entry["audio_us"] = f"/audio/us/{ew}.mp3"
            entry["audio_uk"] = None
            entry["meaning_zh"] = MEANING_MAP.get(ew, "")
            entry.setdefault("ipa_uk", entry.get("ipa_uk"))
            entry.setdefault("phoneme_tags_uk", entry.get("phoneme_tags_uk"))
            entry.setdefault("difficulty_tags", [])
            entry.setdefault("minimal_pair_group", None)
            entry.setdefault("example", None)
            entry.setdefault("audio_status_us", "planned")
            entry.setdefault("audio_status_uk", None)
            entry.setdefault("audio_provider_us", None)
            entry.setdefault("audio_voice_us", None)
            entry.setdefault("audio_generated_at", None)
            curated.append(entry)

    # Sort by word
    curated.sort(key=lambda w: w["word"])

    # Write output
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(curated, f, indent=2, ensure_ascii=False)

    print(f"Curated {len(curated)} words -> {OUTPUT}")
    print(f"/ʒ/ words included: {[w['word'] for w in curated if '/ʒ/' in str(w.get('phoneme_tags_us', []))]}")

    # Count missing meanings
    missing = [w["word"] for w in curated if not w.get("meaning_zh")]
    if missing:
        print(f"WARNING: {len(missing)} words missing meaning_zh: {missing}")


if __name__ == "__main__":
    main()
