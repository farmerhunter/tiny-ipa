# M9 UK-Ready Content Subset and Accent Coverage Report

This is the checked-in evidence artifact for issue #196. It is a content/report snapshot only; it does not enable UK grading, UK primary accent selection, UK comparison UI/API, minimal-pair runtime, or target-phoneme runtime behavior.

## Gate

- Accepted `review_status_uk` values for this report: auto_checked, reviewed
- Content-quality acceptance: Architect/content acceptance required.
- UK comparison remains display-only in later M9 work; US grading remains unchanged.

## Summary

- Source rows: 1300
- Eligible UK-ready rows: 1215
- Excluded rows: 85
- Missing UK IPA count: 85
- Missing UK phoneme tags count: 85
- Unsupported UK symbol count: 0
- Accent-difference candidates: 1170
- Minimal-pair candidates: 17
- Target phonemes covered by US tags: 41
- Target phonemes covered by UK tags: 38

## Sample Table

| word | US IPA | UK IPA | reason included | caveat |
| --- | --- | --- | --- | --- |
| about | /əˈbaʊt/ | /ɐbˈaʊt/ | IPA differs; phoneme tags differ | auto_checked; Architect pronunciation acceptance pending; no UK audio required for M9 comparison |
| academic | /ˌækəˈdɛmɪk/ | /ˌækədˈɛmɪk/ | IPA differs | auto_checked; Architect pronunciation acceptance pending; no UK audio required for M9 comparison |
| academy | /əˈkædəmi/ | /ɐkˈædəmi/ | IPA differs; phoneme tags differ | auto_checked; Architect pronunciation acceptance pending; no UK audio required for M9 comparison |
| accepted | /ækˈsɛptɪd/ | /ɐksˈɛptɪd/ | IPA differs; phoneme tags differ | auto_checked; Architect pronunciation acceptance pending; no UK audio required for M9 comparison |
| activity | /ækˈtɪvəti/ | /æktˈɪvɪti/ | IPA differs; phoneme tags differ | auto_checked; Architect pronunciation acceptance pending; no UK audio required for M9 comparison |
| advice | /ædˈvaɪs/ | /ɐdvˈaɪs/ | IPA differs; phoneme tags differ | auto_checked; Architect pronunciation acceptance pending; no UK audio required for M9 comparison |
| ago | /əˈɡoʊ/ | /ɐɡˈəʊ/ | IPA differs; phoneme tags differ | auto_checked; Architect pronunciation acceptance pending; no UK audio required for M9 comparison |
| anxiety | /æŋˈzaɪəti/ | /æŋzˈaɪəti/ | IPA differs | auto_checked; Architect pronunciation acceptance pending; no UK audio required for M9 comparison |

## Source and License Metadata

Source files:

- `content/core_1000_words.json`: 947
- `content/core_300_words.json`: 268

UK IPA sources:

- open-dict-data/ipa-dict en_UK: 1215

License notes:

- open-data (wordfreq: MIT/Apache-2.0, ipa-dict: see repo): 1215

## Review Status Coverage

- `auto_checked`: 1215
- `disabled`: 1
- `draft`: 84

## Minimal-Pair Candidate Sample

| words | contrast | basis | caveat |
| --- | --- | --- | --- |
| bed / bad | /e/, /æ/ | one phoneme-tag difference in phoneme_tags_us | mechanical candidate only; requires Architect/content review before runtime specialty practice |
| long / wrong | /l/, /r/ | one phoneme-tag difference in phoneme_tags_us | mechanical candidate only; requires Architect/content review before runtime specialty practice |
| rally / rarely | /e/, /æ/ | one phoneme-tag difference in phoneme_tags_us | mechanical candidate only; requires Architect/content review before runtime specialty practice |
| rich / reach | /iː/, /ɪ/ | one phoneme-tag difference in phoneme_tags_us | mechanical candidate only; requires Architect/content review before runtime specialty practice |
| thing / singing | /s/, /θ/ | one phoneme-tag difference in phoneme_tags_us | mechanical candidate only; requires Architect/content review before runtime specialty practice |
| thing / thin | /n/, /ŋ/ | one phoneme-tag difference in phoneme_tags_us | mechanical candidate only; requires Architect/content review before runtime specialty practice |
| wing / win | /n/, /ŋ/ | one phoneme-tag difference in phoneme_tags_us | mechanical candidate only; requires Architect/content review before runtime specialty practice |
| agree / ugly | /l/, /r/ | one phoneme-tag difference in phoneme_tags_us | mechanical candidate only; requires Architect/content review before runtime specialty practice |
| dad / dead | /e/, /æ/ | one phoneme-tag difference in phoneme_tags_us | mechanical candidate only; requires Architect/content review before runtime specialty practice |
| key / kick | /iː/, /ɪ/ | one phoneme-tag difference in phoneme_tags_us | mechanical candidate only; requires Architect/content review before runtime specialty practice |

## Target-Phoneme Candidate Coverage Sample

| phoneme | category | priority | eligible words US | eligible words UK |
| --- | --- | --- | --- | --- |
| /e/ | vowel | 1 | 191 | 182 |
| /iː/ | vowel | 1 | 369 | 324 |
| /l/ | consonant | 1 | 284 | 287 |
| /r/ | consonant | 1 | 226 | 196 |
| /tʃ/ | affricate | 1 | 33 | 35 |
| /uː/ | vowel | 1 | 75 | 81 |
| /v/ | consonant | 1 | 108 | 109 |
| /w/ | consonant | 1 | 61 | 58 |
| /æ/ | vowel | 1 | 161 | 146 |
| /ð/ | consonant | 1 | 17 | 18 |
| /ŋ/ | consonant | 1 | 74 | 74 |
| /ɪ/ | vowel | 1 | 295 | 414 |
| /ʃ/ | consonant | 1 | 47 | 47 |
| /ʊ/ | vowel | 1 | 32 | 107 |
| /ʌ/ | vowel | 1 | 13 | 86 |
| /θ/ | consonant | 1 | 26 | 26 |
| /aɪ/ | diphthong | 2 | 103 | 99 |
| /aʊ/ | diphthong | 2 | 26 | 26 |
| /b/ | consonant | 2 | 115 | 117 |
| /d/ | consonant | 2 | 225 | 224 |

## Caveats and Exclusions

- UK rows marked auto_checked are mechanically eligible for this report, but still require Architect/content-quality acceptance before UI use.
- UK audio is not required for M9 comparison display.
- Minimal-pair candidates are mechanical tag-sequence candidates, not accepted runtime metadata.
- Target-phoneme coverage is candidate coverage only; M9 runtime selection is intentionally out of scope for this issue.

Unsupported UK symbols: none.

Excluded rows sample:

| word | review_status_uk | content_status | reason excluded |
| --- | --- | --- | --- |
| river | draft | core_selected | missing ipa_uk; missing phoneme_tags_uk; review_status_uk 'draft' is not accepted |
| january | draft | core_selected | missing ipa_uk; missing phoneme_tags_uk; review_status_uk 'draft' is not accepted |
| fbi | draft | core_selected | missing ipa_uk; missing phoneme_tags_uk; review_status_uk 'draft' is not accepted |
| miami | draft | core_selected | missing ipa_uk; missing phoneme_tags_uk; review_status_uk 'draft' is not accepted |
| nigeria | draft | core_selected | missing ipa_uk; missing phoneme_tags_uk; review_status_uk 'draft' is not accepted |
| indiana | draft | core_selected | missing ipa_uk; missing phoneme_tags_uk; review_status_uk 'draft' is not accepted |
| israeli | draft | core_selected | missing ipa_uk; missing phoneme_tags_uk; review_status_uk 'draft' is not accepted |
| nba | draft | core_selected | missing ipa_uk; missing phoneme_tags_uk; review_status_uk 'draft' is not accepted |
| dna | draft | core_selected | missing ipa_uk; missing phoneme_tags_uk; review_status_uk 'draft' is not accepted |
| chinese | draft | core_selected | missing ipa_uk; missing phoneme_tags_uk; review_status_uk 'draft' is not accepted |
