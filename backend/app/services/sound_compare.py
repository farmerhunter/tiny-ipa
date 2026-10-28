from __future__ import annotations

import json
import os
import re
from pathlib import Path

from app.services.db_store import get_word_by_id


def validate_pair_evidence(manifest: dict, supported_phones: set[str]) -> dict:
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != "tiny-ipa-sound-compare-candidate/v1"
        or manifest.get("status") != "development-only"
    ):
        raise ValueError("unexpected comparison candidate contract")
    pairs = manifest.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("comparison pairs required")
    seen_words, seen_groups = set(), set()
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ValueError("invalid comparison pair")
        group, members = pair.get("group"), pair.get("members")
        if (
            not isinstance(group, str)
            or not group
            or group in seen_groups
            or not isinstance(members, list)
            or len(members) != 2
        ):
            raise ValueError("invalid comparison group")
        seen_groups.add(group)
        sequences = []
        for member in members:
            if not isinstance(member, dict):
                raise ValueError("invalid comparison member")
            wid, phones, ipa = (
                member.get("word_id"),
                member.get("ordered_phones_us"),
                member.get("ipa_us"),
            )
            if not isinstance(wid, str) or not re.fullmatch(r"[a-z]+", wid) or wid in seen_words:
                raise ValueError("invalid comparison word")
            if (
                not isinstance(phones, list)
                or len(phones) < 2
                or any(
                    not isinstance(p, str)
                    or not re.fullmatch(r"/[^/\s]+/", p)
                    or p not in supported_phones
                    for p in phones
                )
            ):
                raise ValueError("invalid ordered phones")
            if (
                not isinstance(ipa, str)
                or ipa.replace("ɡ", "g") != "/ˈ" + "".join(p[1:-1] for p in phones) + "/"
            ):
                raise ValueError("ordered phones differ from IPA")
            seen_words.add(wid)
            sequences.append(phones)
        left, right = sequences
        index = pair.get("contrast_index")
        differences = [i for i, (a, b) in enumerate(zip(left, right)) if a != b]
        if (
            type(index) is not int
            or len(left) != len(right)
            or differences != [index]
            or index not in (0, len(left) - 1)
        ):
            raise ValueError("comparison must differ only in one initial/final supported phone")
    return manifest


def attempt_sound_compare(conn, session, item, correct_answer: str):
    if session.group_type != "minimal_pair" or item.question_type != "choose_ipa":
        return None
    unavailable = {"status": "unavailable"}
    evidence_path = os.environ.get("TINY_IPA_SOUND_COMPARE_EVIDENCE_PATH")
    if session.primary_accent != "US" or not evidence_path:
        return unavailable
    try:
        manifest = validate_pair_evidence(
            json.loads(Path(evidence_path).read_text()),
            {
                row[0]
                for row in conn.execute(
                    "SELECT id FROM phonemes WHERE accent_scope IN ('US', 'both')"
                )
            },
        )
    except (OSError, UnicodeError, ValueError):
        return unavailable
    from app.services.sessions import _minimal_pair_partners

    current = get_word_by_id(conn, item.word_id)
    partner = _minimal_pair_partners(conn, accent="US", learner_level=session.learner_level).get(
        item.word_id
    )
    if current is None or partner is None or current.ipa_us.strip() != correct_answer.strip():
        return unavailable
    for pair in manifest["pairs"]:
        members = {member["word_id"]: member for member in pair["members"]}
        if set(members) != {current.id, partner.id}:
            continue
        for word in (current, partner):
            member = members[word.id]
            if (
                word.word != member["word_id"]
                or word.ipa_us != member["ipa_us"]
                or word.minimal_pair_group != pair["group"]
                or word.content_status == "disabled"
                or word.level != current.level
            ):
                return unavailable
        index = pair["contrast_index"]
        return {
            "status": "available",
            "accent": "US",
            "current": {"word_id": current.id, "word": current.word, "ipa": current.ipa_us},
            "counterpart": {"word_id": partner.id, "word": partner.word, "ipa": partner.ipa_us},
            "contrast": {
                "position": "initial" if index == 0 else "final",
                "current_phoneme": members[current.id]["ordered_phones_us"][index],
                "counterpart_phoneme": members[partner.id]["ordered_phones_us"][index],
            },
        }
    return unavailable
