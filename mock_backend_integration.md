# Mock Backend — Frontend Integration Guide

**Verse:** Surah Ar-Rahman 55:1–8 (21 words, 8 ayahs)  
**Server:** `http://localhost:8000`  
**WebSocket:** `ws://localhost:8000/ws/recitation`

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [REST Endpoints](#rest-endpoints)
3. [WebSocket Message Flow](#websocket-message-flow)
4. [All Message Schemas](#all-message-schemas)
5. [Word-Feedback Status Reference](#word-feedback-status-reference)
6. [Use Case 1 — Smooth Recitation with Mistakes](#use-case-1--smooth-recitation-with-mistakes)
7. [Use Case 2 — Ayah Repetition](#use-case-2--ayah-repetition)
8. [Use Case 3 — Ayah Skip](#use-case-3--ayah-skip)
9. [Use Case 4 — Heavy Harakat Mistakes](#use-case-4--heavy-harakat-mistakes)
10. [Use Case 5 — Letter-Level Mistakes](#use-case-5--letter-level-mistakes)
11. [Session Summary & Audio Playback](#session-summary--audio-playback)
12. [Complete Integration Example (JavaScript)](#complete-integration-example-javascript)
13. [UI Rendering Checklist](#ui-rendering-checklist)

---

## Quick Start

```bash
cd mock_backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

Run a quick sanity check:

```bash
curl http://localhost:8000/health
# → {"status": "healthy"}

curl http://localhost:8000/api/verses | python3 -m json.tool | head -30
```

---

## REST Endpoints

| Method | Path | Returns |
|--------|------|---------|
| `GET` | `/health` | `{"status": "healthy"}` |
| `GET` | `/api/verses` | Verse object with all 21 words and their letter arrays |
| `GET` | `/api/recordings/{use_case}` | Static mock WAV tone (use_case 1–5, always available) |
| `GET` | `/api/session-recordings/{session_id}` | The real audio recorded during a specific session (available for the last 20 sessions) |

`session_id` comes from `recording.download_url` in `session_summary` when `recording.source == "recorded"`. If the frontend sent no audio data, this endpoint is not used and the mock WAV fallback is served instead.

### GET /api/verses — Response Shape

```json
[
  {
    "id": "55:1-8",
    "surah": 55,
    "ayah": 1,
    "text": "الرَّحْمَٰنُ عَلَّمَ الْقُرْآنَ ...",
    "words": [
      {
        "id": "55:1:1",
        "text": "الرَّحْمَٰنُ",
        "letters": ["ا","ل","ر","َّ","ح","ْ","م","َ","ٰ","ن","ُ"],
        "position": 0
      },
      ...
    ],
    "verse_boundaries": [
      {"ayah": 1, "end_word_index": 0},
      {"ayah": 2, "end_word_index": 2},
      {"ayah": 3, "end_word_index": 4},
      {"ayah": 4, "end_word_index": 6},
      {"ayah": 5, "end_word_index": 9},
      {"ayah": 6, "end_word_index": 12},
      {"ayah": 7, "end_word_index": 16},
      {"ayah": 8, "end_word_index": 20}
    ]
  }
]
```

`verse_boundaries` tells you where each ayah ends by word index (0-based).  
The full word list and their positions are in the table below.

| Position | Word ID | Arabic |
|----------|---------|--------|
| 0 | 55:1:1 | الرَّحْمَٰنُ |
| 1 | 55:2:1 | عَلَّمَ |
| 2 | 55:2:2 | الْقُرْآنَ |
| 3 | 55:3:1 | خَلَقَ |
| 4 | 55:3:2 | الْإِنسَانَ |
| 5 | 55:4:1 | عَلَّمَهُ |
| 6 | 55:4:2 | الْبَيَانَ |
| 7 | 55:5:1 | الشَّمْسُ |
| 8 | 55:5:2 | وَالْقَمَرُ |
| 9 | 55:5:3 | بِحُسْبَانٍ |
| 10 | 55:6:1 | وَالنَّجْمُ |
| 11 | 55:6:2 | وَالشَّجَرُ |
| 12 | 55:6:3 | يَسْجُدَانِ |
| 13 | 55:7:1 | وَالسَّمَاءَ |
| 14 | 55:7:2 | رَفَعَهَا |
| 15 | 55:7:3 | وَوَضَعَ |
| 16 | 55:7:4 | الْمِيزَانَ |
| 17 | 55:8:1 | أَلَّا |
| 18 | 55:8:2 | تَطْغَوْا |
| 19 | 55:8:3 | فِي |
| 20 | 55:8:4 | الْمِيزَانِ |

---

## WebSocket Message Flow

```
CLIENT                                     SERVER
──────                                     ──────

1.  Connect to ws://localhost:8000/ws/recitation

2.  Send ──{ type: "start",           ──►  Responds with  { type: "status", session_id, ... }
             verse_id: "55:1-8",
             use_case: 1 }

3.  Send ──{ type: "audio",           ──►  • Appends audio bytes to session buffer
             audio: "<base64>" }            • Responds with  { type: "feedback", chunk_index: 1, ... }

    Send ──{ type: "audio", ... }     ──►  • Appends audio bytes to session buffer
                                           • { type: "feedback", chunk_index: 2, ... }

    (repeat for each ~2-second audio chunk)

4.  Send ──{ type: "stop" }           ──►  • Flushes remaining feedback chunks
                                           • Concatenates all buffered audio bytes
                                           • Stores recording in memory (keyed by session_id)
                                           • Sends  { type: "session_summary",
                                                       recording: { source: "recorded", ... } }
                                             — or —  { recording: { source: "mock", ... } }
                                                       if no audio bytes were received
```

**Key rules:**
- One `audio` message → one `feedback` response (~400 ms simulated delay).
- The `audio` field in each message is base64-decoded and accumulated. All chunks are concatenated on `stop` to form the full recording.
- If you send more `audio` messages than there are pre-built mock chunks, extra audio is still buffered (but no more feedback is sent).
- After `stop`, the server resets and accepts a new `start` on the same connection.
- You can test without real audio: send `{ type: "audio", audio: "" }`. The summary will then use `source: "mock"` and include the static sine-wave WAV instead.

---

## All Message Schemas

### Client → Server

#### start
```json
{
  "type": "start",
  "verse_id": "55:1-8",
  "use_case": 1
}
```
`use_case`: integer 1–5.

#### audio
```json
{
  "type": "audio",
  "audio": "<base64-encoded audio chunk>",
  "chunk_index": 1
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `audio` | No | Base64-encoded raw audio bytes. If present, the server decodes and accumulates them. Accepts `""` as a no-op trigger that still advances the mock feedback sequence. |
| `chunk_index` | No | Client-supplied index for logging only; the mock drives its own sequence regardless. |
| `data` | No | Legacy alias for `audio` — both are accepted. |

The server accumulates every non-empty `audio` value in order. On `stop`, all chunks are concatenated and stored as the session recording.

#### stop
```json
{ "type": "stop" }
```

---

### Server → Client

#### status
Sent immediately after a valid `start`.

```json
{
  "type": "status",
  "session_id": "a3f1c2d4-...",
  "verse_id": "55:1-8",
  "message": "Session started. Ready to receive audio.",
  "total_words": 21,
  "total_ayahs": 8
}
```

#### feedback
Sent after each `audio` chunk. Contains the full state of the session at that point.

```json
{
  "type": "feedback",
  "session_id": "a3f1c2d4-...",
  "chunk_index": 7,
  "transcribed_text": "الرَّحْمَٰنُ عَلَّمَ الْقُرْآنَ خَلَقَ الْإِنسَانَ عَلَّمَهُ الْبَيَانَ",
  "current_ayah": 4,
  "word_cursor": 6,
  "position_in_verse": 0.33,
  "ayah_complete": true,
  "skipped_ayahs": [],
  "repeated_ayahs": [],
  "word_feedback": [ /* 21 items, see below */ ],
  "mistakes": [ /* accumulated so far */ ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `chunk_index` | int | 1-based counter for this chunk |
| `transcribed_text` | string | Cumulative transcription of all words heard so far |
| `current_ayah` | int | Ayah number the cursor is currently in (1–8) |
| `word_cursor` | int | 0-based index of the last word reached |
| `position_in_verse` | float | 0.0–1.0 fraction of the full verse completed |
| `ayah_complete` | bool | `true` when the current ayah just finished |
| `skipped_ayahs` | int[] | Ayah numbers detected as skipped (Case 3 only) |
| `repeated_ayahs` | int[] | Ayah numbers detected as repeated (Case 2 only) |
| `word_feedback` | object[] | Array of 21 word objects (all words, not just recited ones) |
| `mistakes` | object[] | Cumulative list of mistakes detected so far |

**`word_feedback` item:**
```json
{
  "word_id": "55:4:1",
  "word_text": "عَلَّمَهُ",
  "status": "diacritic_error",
  "recited_text": "عَلَّمَه",
  "letter_feedback": [
    {"position": 0, "expected_letter": "ع",  "recited_letter": "ع",  "status": "correct"},
    {"position": 7, "expected_letter": "ُ",  "recited_letter": "",   "status": "diacritic_error"}
  ]
}
```
`letter_feedback` is only present when `status` is `vowel_error` or `letter_error` or `diacritic_error` (for Cases 4 & 5).  
Words not yet reached have `status: "not_recited"` and `recited_text: null`.

**`mistakes` item:**
```json
{
  "word_id": "55:5:3",
  "word_text": "بِحُسْبَانٍ",
  "type": "diacritic_error",
  "recited_text": "بحسبان",
  "details": "Tanwīn kasra (ٍ) missing at end of word"
}
```
Mistakes with `type: "vowel_error"` or `type: "letter_error"` also include `letter_feedback`.

#### error
```json
{
  "type": "error",
  "message": "Unknown use_case '9'. Valid values: 1, 2, 3, 4, 5"
}
```

#### session_summary
Sent after `stop`. See [Session Summary & Audio Playback](#session-summary--audio-playback).

---

## Word-Feedback Status Reference

| `status` | Colour suggestion | Meaning |
|----------|------------------|---------|
| `correct` | Green | All consonants and harakat match |
| `diacritic_error` | Orange | Consonants correct; shadda / tanwin / sukun wrong or missing |
| `vowel_error` | Yellow-orange | Consonants correct; a short vowel (fatha ↔ kasra ↔ damma) wrong |
| `letter_error` | Red | A consonant letter substituted (e.g. خ → ح) |
| `incorrect` | Red | Completely different word recited |
| `not_recited` | Grey | Word not reached yet or skipped |

**Severity order (worst → best):** `letter_error` = `incorrect` > `diacritic_error` > `vowel_error` > `correct`

---

## Use Case 1 — Smooth Recitation with Mistakes

```json
{ "type": "start", "verse_id": "55:1-8", "use_case": 1 }
```

**Scenario:** User completes all 8 ayahs. Two mistakes detected mid-session.

| # | Mistake word | Status | What happened |
|---|-------------|--------|--------------|
| 1 | بِحُسْبَانٍ (pos 9) | `diacritic_error` | Tanwīn kasra (ٍ) dropped — heard as "بحسبان" |
| 2 | تَطْغَوْا (pos 18) | `incorrect` | Final waw-alif dropped — heard as "تطغو" |

**Chunk sequence (19 chunks):**

| Chunk | `word_cursor` | `current_ayah` | `ayah_complete` | New mistake added |
|-------|------------|----------------|-----------------|------------------|
| 1 | 0 | 1 | ✓ | — |
| 2 | 1 | 2 | — | — |
| 3 | 2 | 2 | ✓ | — |
| 4 | 3 | 3 | — | — |
| 5 | 4 | 3 | ✓ | — |
| 6 | 5 | 4 | — | — |
| 7 | 6 | 4 | ✓ | — |
| 8 | 7 | 5 | — | — |
| 9 | 8 | 5 | — | — |
| **10** | **9** | **5** | **✓** | **+بِحُسْبَانٍ diacritic_error** |
| 11 | 10 | 6 | — | — |
| 12 | 11 | 6 | — | — |
| 13 | 12 | 6 | ✓ | — |
| 14 | 13 | 7 | — | — |
| 15 | 14 | 7 | — | — |
| 16 | 15 | 7 | — | — |
| 17 | 16 | 7 | ✓ | — |
| **18** | **18** | **8** | **—** | **+تَطْغَوْا incorrect** |
| 19 | 20 | 8 | ✓ | — |

**Final summary:**
- `total_score`: 88
- `words_correct`: 19  `words_diacritic_error`: 1  `words_incorrect`: 1
- `completion_percentage`: 100

**What to render:**
- Highlight word 9 orange (`diacritic_error`) and word 18 red (`incorrect`) in the word grid.
- Show mistake cards when `mistakes` array grows (chunk 10 and chunk 18).
- `ayah_complete: true` → animate ayah completion indicator for ayah 5 (chunk 10) and ayah 8 (chunk 19).

---

## Use Case 2 — Ayah Repetition

```json
{ "type": "start", "verse_id": "55:1-8", "use_case": 2 }
```

**Scenario:** User recites Ayah 1 (الرَّحْمَٰنُ), pauses, then recites it again before continuing. No pronunciation mistakes.

**Key signal:** Starting from chunk 2, the feedback carries:
```json
{
  "repeated_ayahs": [1],
  "repetition_detail": [
    {
      "ayah": 1,
      "first_occurrence_chunk": 1,
      "repeat_chunk": 2,
      "recited_text": "الرحمن",
      "note": "Ayah 1 recited again from the beginning"
    }
  ]
}
```

**Chunk sequence (21 chunks):**

| Chunk | `word_cursor` | `current_ayah` | `ayah_complete` | `repeated_ayahs` |
|-------|------------|----------------|-----------------|-----------------|
| 1 | 0 | 1 | ✓ | `[]` — first clean recitation |
| **2** | **0** | **1** | **—** | **`[1]`** — repetition detected here |
| 3 | 1 | 2 | — | `[1]` |
| 4 | 2 | 2 | ✓ | `[1]` |
| 5–21 | 3 → 20 | 3 → 8 | per ayah | `[1]` throughout |

Note: `word_cursor` stays at 0 on chunks 1 and 2 because Ayah 1 is only one word.  
`transcribed_text` on chunk 2 becomes `"الرَّحْمَٰنُ الرَّحْمَٰنُ"` (word shown twice).

**Final summary:**
- `total_score`: 95 (5-point deduction for repetition)
- `words_correct`: 21  (perfect recitation, no pronunciation errors)
- `repeated_ayahs`: `[1]`
- `completion_percentage`: 100

**What to render:**
- When `repeated_ayahs` is non-empty, show a "Repetition detected" banner/toast.
- In the per-ayah score breakdown, show a note badge on Ayah 1: "Repeated once".
- `mistakes` is always empty in this case — do not show the mistakes panel.

---

## Use Case 3 — Ayah Skip

```json
{ "type": "start", "verse_id": "55:1-8", "use_case": 3 }
```

**Scenario:** User recites Ayah 1, then jumps directly to Ayah 3, skipping Ayah 2 entirely (words عَلَّمَ and الْقُرْآنَ are never heard).

**Key signal:** Starting from chunk 2, the feedback carries:
```json
{
  "skipped_ayahs": [2],
  "skip_detail": [
    {
      "ayah": 2,
      "skipped_words": [
        {"word_id": "55:2:1", "word_text": "عَلَّمَ"},
        {"word_id": "55:2:2", "word_text": "الْقُرْآنَ"}
      ],
      "detected_at_chunk": 2,
      "note": "Jump detected from ayah 1 directly to ayah 3"
    }
  ]
}
```

**Chunk sequence (19 chunks):**

| Chunk | `word_cursor` | `current_ayah` | `ayah_complete` | `skipped_ayahs` |
|-------|------------|----------------|-----------------|-----------------|
| 1 | 0 | 1 | ✓ | `[]` |
| **2** | **3** | **3** | **—** | **`[2]`** — skip detected, cursor jumps from 0 to 3 |
| 3 | 4 | 3 | ✓ | `[2]` |
| 4–19 | 5 → 20 | 4 → 8 | per ayah | `[2]` throughout |

Skipped words (positions 1 and 2) appear in `word_feedback` with `status: "not_recited"` throughout the entire session.

**Final summary:**
- `total_score`: 72
- `words_not_recited`: 2  `words_correct`: 19
- `skipped_ayahs`: `[2]`
- `completion_percentage`: 90 (Ayah 2 not attempted)
- Ayah 2 score: 0

**What to render:**
- When `skipped_ayahs` is non-empty, show a "Skip detected" warning banner.
- In the word grid, words 1 and 2 remain grey (`not_recited`) for the entire session.
- Ayah 2 in the per-ayah breakdown should show score 0 with "Skipped entirely" note.

---

## Use Case 4 — Heavy Harakat Mistakes

```json
{ "type": "start", "verse_id": "55:1-8", "use_case": 4 }
```

**Scenario:** User completes all 8 ayahs but repeatedly confuses harakat. 3 diacritic errors and 2 vowel errors.

**Mistakes summary:**

| Position | Word | Status | What happened | Chunk appears |
|----------|------|--------|--------------|--------------|
| 1 | عَلَّمَ | `diacritic_error` | Shadda on lam dropped → "عَلَمَ" | Chunk 2 |
| 5 | عَلَّمَهُ | `diacritic_error` | Damma on hā dropped → "عَلَّمَه" | Chunk 6 |
| 12 | يَسْجُدَانِ | `diacritic_error` | Kasra on nūn → fatha → "يَسْجُدَانَ" | Chunk 13 |
| 14 | رَفَعَهَا | `vowel_error` | Fatha→damma and fatha→kasra → "رُفِعَهَا" | Chunk 15 |
| 16 | الْمِيزَانَ | `vowel_error` | Kasra on mīm → fatha → "الْمَيزَانَ" | Chunk 17 |

**Mistake accumulation across chunks:**

| After chunk | `mistakes` array contains |
|-------------|--------------------------|
| 1 | `[]` |
| 2 | `[عَلَّمَ diacritic]` |
| 3–5 | `[عَلَّمَ diacritic]` |
| 6 | `[عَلَّمَ diac, عَلَّمَهُ diac]` |
| 7–12 | `[…same 2…]` |
| 13 | `[…same 2…, يَسْجُدَانِ diac]` |
| 14 | `[…same 3…]` |
| 15 | `[…same 3…, رَفَعَهَا vowel]` |
| 16 | `[…same 4…]` |
| 17 | `[…same 4…, الْمِيزَانَ vowel]` |
| 18–19 | `[all 5 mistakes]` |

**Letter-feedback example** (word عَلَّمَ, chunk 2):
```json
{
  "word_id": "55:2:1",
  "word_text": "عَلَّمَ",
  "status": "diacritic_error",
  "recited_text": "عَلَمَ",
  "letter_feedback": [
    {"position": 0, "expected_letter": "ع",  "recited_letter": "ع",  "status": "correct"},
    {"position": 1, "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
    {"position": 2, "expected_letter": "ل",  "recited_letter": "ل",  "status": "correct"},
    {"position": 3, "expected_letter": "َّ", "recited_letter": "َ",  "status": "diacritic_error"},
    {"position": 4, "expected_letter": "م",  "recited_letter": "م",  "status": "correct"},
    {"position": 5, "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"}
  ]
}
```

**Final summary:**
- `total_score`: 78
- `words_correct`: 16  `words_diacritic_error`: 3  `words_vowel_error`: 2
- `completion_percentage`: 100

**Per-ayah scores:**

| Ayah | Score | Note |
|------|-------|------|
| 1 | 100 | — |
| 2 | 70 | عَلَّمَ recited without shadda |
| 3 | 100 | — |
| 4 | 70 | عَلَّمَهُ recited without damma on hā |
| 5 | 100 | — |
| 6 | 80 | يَسْجُدَانِ — kasra on nūn changed to fatha |
| 7 | 60 | رَفَعَهَا and الْمِيزَانَ have wrong vowels |
| 8 | 100 | — |

**What to render:**
- Words 1, 5, 12 → orange badge (`diacritic_error`).
- Words 14, 16 → yellow-orange badge (`vowel_error`).
- For words with `letter_feedback`, render an expandable letter-level breakdown showing exactly which position is wrong (e.g. position 3 of عَلَّمَ shows the missing shadda).

---

## Use Case 5 — Letter-Level Mistakes

```json
{ "type": "start", "verse_id": "55:1-8", "use_case": 5 }
```

**Scenario:** User makes actual consonant substitution errors — confusing similarly-pronounced letters — plus two vowel mistakes.

**Mistakes summary:**

| Position | Word | Status | What happened | Chunk appears |
|----------|------|--------|--------------|--------------|
| 3 | خَلَقَ | `letter_error` | خ (kha) → ح (ha) → "حَلَقَ" | Chunk 4 |
| 8 | وَالْقَمَرُ | `letter_error` | ق (qāf) → غ (ghain) → "وَالْغَمَرُ" | Chunk 9 |
| 10 | وَالنَّجْمُ | `vowel_error` | Damma ُ on mīm → kasra ِ → "وَالنَّجْمِ" | Chunk 11 |
| 15 | وَوَضَعَ | `vowel_error` | Fatha َ on ḍad → kasra ِ → "وَوَضِعَ" | Chunk 16 |

**Mistake accumulation across chunks:**

| After chunk | `mistakes` array contains |
|-------------|--------------------------|
| 1–3 | `[]` |
| 4 | `[خَلَقَ letter_error]` |
| 5–8 | `[خَلَقَ letter_error]` |
| 9 | `[خَلَقَ, وَالْقَمَرُ letter_errors]` |
| 10 | `[…same 2…]` |
| 11 | `[…same 2…, وَالنَّجْمُ vowel_error]` |
| 12–15 | `[…same 3…]` |
| 16 | `[all 4 mistakes]` |
| 17–19 | `[all 4 mistakes]` |

**Letter-feedback example** (word خَلَقَ, chunk 4):
```json
{
  "word_id": "55:3:1",
  "word_text": "خَلَقَ",
  "status": "letter_error",
  "recited_text": "حَلَقَ",
  "letter_feedback": [
    {"position": 0, "expected_letter": "خ", "recited_letter": "ح", "status": "letter_error"},
    {"position": 1, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 2, "expected_letter": "ل", "recited_letter": "ل", "status": "correct"},
    {"position": 3, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 4, "expected_letter": "ق", "recited_letter": "ق", "status": "correct"},
    {"position": 5, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"}
  ]
}
```

**Letter-feedback example** (word وَالْقَمَرُ, chunk 9):
```json
{
  "word_id": "55:5:2",
  "word_text": "وَالْقَمَرُ",
  "status": "letter_error",
  "recited_text": "وَالْغَمَرُ",
  "letter_feedback": [
    {"position": 0, "expected_letter": "و", "recited_letter": "و", "status": "correct"},
    {"position": 1, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 2, "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 3, "expected_letter": "ل", "recited_letter": "ل", "status": "correct"},
    {"position": 4, "expected_letter": "ْ", "recited_letter": "ْ", "status": "correct"},
    {"position": 5, "expected_letter": "ق", "recited_letter": "غ", "status": "letter_error"},
    {"position": 6, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    ...
  ]
}
```

**Final summary:**
- `total_score`: 65
- `words_correct`: 17  `words_letter_error`: 2  `words_vowel_error`: 2
- `completion_percentage`: 100

**Per-ayah scores:**

| Ayah | Score | Note |
|------|-------|------|
| 1 | 100 | — |
| 2 | 100 | — |
| 3 | 50 | خَلَقَ — kha recited as ha |
| 4 | 100 | — |
| 5 | 67 | وَالْقَمَرُ — qāf recited as ghain |
| 6 | 80 | وَالنَّجْمُ — damma on mīm recited as kasra |
| 7 | 75 | وَوَضَعَ — fatha on ḍad recited as kasra |
| 8 | 100 | — |

**What to render:**
- Words 3 and 8 → red badge (`letter_error`) — these are the most serious mistakes.
- Words 10 and 15 → yellow-orange badge (`vowel_error`).
- For `letter_error` words, show an expanded letter-by-letter diff highlighting the wrong consonant (position 0 for خَلَقَ, position 5 for وَالْقَمَرُ).
- Show a prominent "Letter substitution" callout in the mistake card — this is different from a simple vowel/diacritic issue.

---

## Session Summary & Audio Playback

Sent when the client sends `stop`. Contains the full session report.

```json
{
  "type": "session_summary",
  "session_id": "a3f1c2d4-...",
  "verse_id": "55:1-8",
  "total_chunks": 19,
  "duration_seconds": 38,
  "full_transcription": "الرَّحْمَٰنُ عَلَّمَ الْقُرْآنَ ...",
  "total_words": 21,
  "words_correct": 19,
  "words_diacritic_error": 1,
  "words_vowel_error": 0,
  "words_letter_error": 0,
  "words_incorrect": 1,
  "words_not_recited": 0,
  "total_score": 88,
  "completion_percentage": 100,
  "skipped_ayahs": [],
  "repeated_ayahs": [],
  "skip_detail": [],
  "repetition_detail": [],
  "ayah_scores": [
    {"ayah": 1, "score": 100, "words_correct": 1, "words_errors": 0},
    ...
  ],
  "mistakes": [ /* full mistake list */ ],
  "overall_feedback": "Excellent recitation! ...",
  "recording": { ... }
}
```

### The `recording` block

The shape of `recording` depends on whether the frontend sent real audio bytes during the session.

**When real audio was sent (`source: "recorded"`):**
```json
{
  "audio_data":       "<base64-encoded bytes — format matches audio_format>",
  "audio_format":     "webm",
  "audio_size_bytes": 94208,
  "duration_seconds": 38,
  "filename":         "recitation_a3f1c2d4.webm",
  "download_url":     "/api/session-recordings/a3f1c2d4-1b2c-...",
  "source":           "recorded"
}
```

**When no audio was sent — mock fallback (`source: "mock"`):**
```json
{
  "audio_data":       "<base64-encoded 1-second sine-wave WAV>",
  "audio_format":     "wav",
  "audio_size_bytes": 32044,
  "duration_seconds": 38,
  "filename":         "recitation_case_1.wav",
  "download_url":     "/api/recordings/1",
  "source":           "mock"
}
```

| Field | Description |
|-------|-------------|
| `audio_data` | Full recording as a base64 string — decode and play directly without an extra request |
| `audio_format` | File extension: `"webm"`, `"wav"`, `"ogg"`, or `"mp3"` — use as the Blob MIME type |
| `audio_size_bytes` | Byte length of the decoded audio |
| `duration_seconds` | Approximate session duration taken from mock metadata |
| `filename` | Suggested filename for download prompts |
| `download_url` | Path to fetch/download the audio via REST (session-specific for real recordings) |
| `source` | `"recorded"` — real captured audio \| `"mock"` — static sine-wave fallback |

> **Format detection:** The server inspects the first 4 bytes of the concatenated audio. Browser `MediaRecorder` defaults to WebM/Opus, so `audio_format` will usually be `"webm"`. Always use `rec.audio_format` (not a hardcoded `"wav"`) when constructing the Blob.

### Score fields explained

| Field | What it counts |
|-------|---------------|
| `words_correct` | Words where every letter and harakat matched |
| `words_diacritic_error` | Words where shadda / tanwin / sukun was wrong or missing |
| `words_vowel_error` | Words where a short vowel (fatha/kasra/damma) was wrong |
| `words_letter_error` | Words where a consonant was substituted |
| `words_incorrect` | Words with a completely different reading |
| `words_not_recited` | Words skipped or never reached |

### Scores by use case

| Use case | `total_score` | `completion_percentage` |
|----------|--------------|------------------------|
| 1 | 88 | 100 |
| 2 | 95 | 100 |
| 3 | 72 | 90 |
| 4 | 78 | 100 |
| 5 | 65 | 100 |

### Playing back the recording

**Option A — Inline base64 (no extra request, works for both `"recorded"` and `"mock"`):**
```javascript
const rec = summary.recording;
const mimeMap = { webm: "audio/webm", wav: "audio/wav", ogg: "audio/ogg", mp3: "audio/mpeg" };
const bytes = Uint8Array.from(atob(rec.audio_data), c => c.charCodeAt(0));
const blob  = new Blob([bytes], { type: mimeMap[rec.audio_format] ?? "audio/webm" });
const audio = new Audio(URL.createObjectURL(blob));
audio.play();
console.log(`source: ${rec.source} | format: ${rec.audio_format} | ${rec.audio_size_bytes} bytes`);
```

**Option B — REST download link:**
```javascript
// Download as file
const a = document.createElement("a");
a.href = `http://localhost:8000${rec.download_url}`;
a.download = rec.filename;
a.click();

// Or set an <audio> src directly
document.getElementById("playback").src =
  `http://localhost:8000${rec.download_url}`;
```

**Option C — Check source and choose strategy:**
```javascript
if (rec.source === "recorded") {
  // Real audio from this session — play it and offer download
  showAudioPlayer(rec);
  showDownloadButton(`http://localhost:8000${rec.download_url}`, rec.filename);
} else {
  // Mock fallback — useful for UI testing but not a real recitation
  showMockAudioNote(rec);
}
```

### Mock WAV tones (when `source: "mock"`)

When the frontend sends empty `audio` fields, the summary includes a static 1-second sine-wave WAV. Each use case has a distinct pitch:

| Use case | Frequency | Note |
|----------|-----------|------|
| 1 | 440 Hz | A4 |
| 2 | 523 Hz | C5 |
| 3 | 392 Hz | G4 |
| 4 | 349 Hz | F4 |
| 5 | 294 Hz | D4 |

---

## Complete Integration Example (JavaScript)

```javascript
class RecitationSession {
  constructor(useCase = 1) {
    this.useCase   = useCase;
    this.ws        = null;
    this.sessionId = null;
    this.mistakesLog = [];

    // MediaRecorder state — for capturing real audio
    this.mediaRecorder  = null;
    this.pendingChunkB64 = null;   // base64 of the most recently captured blob
  }

  // ── Connection ────────────────────────────────────────────────────────────

  async connect() {
    // Request microphone access and start recording in 2-second slices
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.mediaRecorder = new MediaRecorder(stream);

      this.mediaRecorder.ondataavailable = async (e) => {
        if (e.data.size > 0) {
          // Convert Blob → ArrayBuffer → base64 string
          const buf = await e.data.arrayBuffer();
          const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)));
          this.pendingChunkB64 = b64;
        }
      };

      this.mediaRecorder.start(2000); // emit a blob every 2 seconds
    } catch {
      // Microphone unavailable — fall back to dummy chunks (mock WAV in summary)
      console.warn("Microphone unavailable — sending empty audio (mock WAV will be used)");
    }

    this.ws = new WebSocket("ws://localhost:8000/ws/recitation");

    this.ws.onopen = () => {
      this.ws.send(JSON.stringify({
        type: "start",
        verse_id: "55:1-8",
        use_case: this.useCase,
      }));
    };

    this.ws.onmessage = (event) => this.handleMessage(JSON.parse(event.data));
    this.ws.onerror   = (e) => console.error("WebSocket error", e);
    this.ws.onclose   = () => {
      this.mediaRecorder?.stop();
      console.log("Connection closed");
    };
  }

  // ── Message handling ──────────────────────────────────────────────────────

  handleMessage(msg) {
    switch (msg.type) {
      case "status":
        this.sessionId = msg.session_id;
        console.log(`Session ${msg.session_id} started — ${msg.total_words} words`);
        this.sendNextChunk();
        break;

      case "feedback":
        this.renderFeedback(msg);
        if (msg.word_cursor < 20) {
          this.sendNextChunk();
        }
        break;

      case "session_summary":
        this.renderSummary(msg);
        break;

      case "error":
        console.error("Server error:", msg.message);
        break;
    }
  }

  sendNextChunk() {
    // Send the most recently captured audio chunk (or an empty string as a
    // dummy trigger when the microphone is unavailable).
    const audio = this.pendingChunkB64 ?? "";
    this.pendingChunkB64 = null;   // consume it
    this.ws.send(JSON.stringify({ type: "audio", audio }));
  }

  stop() {
    this.mediaRecorder?.stop();
    this.ws.send(JSON.stringify({ type: "stop" }));
  }

  // ── Rendering ─────────────────────────────────────────────────────────────

  renderFeedback(msg) {
    console.log(
      `Chunk ${msg.chunk_index} | Ayah ${msg.current_ayah} | ` +
      `Cursor ${msg.word_cursor}/20 | ${(msg.position_in_verse * 100).toFixed(0)}%`
    );

    if (msg.ayah_complete)         console.log(`  ✓ Ayah ${msg.current_ayah} complete`);
    if (msg.skipped_ayahs?.length) console.warn(`  ⚠ Skipped:`,  msg.skipped_ayahs);
    if (msg.repeated_ayahs?.length)console.warn(`  ↩ Repeated:`, msg.repeated_ayahs);

    // Word grid — colour each word by status
    msg.word_feedback.forEach(w => {
      const colour = {
        correct:         "green",
        diacritic_error: "orange",
        vowel_error:     "yellow",
        letter_error:    "red",
        incorrect:       "red",
        not_recited:     "grey",
      }[w.status] ?? "grey";
      // updateWordCell(w.word_id, colour, w.word_text);
    });

    // New mistakes since last chunk
    const newMistakes = msg.mistakes.slice(this.mistakesLog.length);
    newMistakes.forEach(m => {
      console.warn(`  Mistake: ${m.word_text} [${m.type}] — ${m.details}`);
      m.letter_feedback
        ?.filter(lf => lf.status !== "correct")
        .forEach(lf => console.warn(
          `    pos ${lf.position}: expected '${lf.expected_letter}' ` +
          `got '${lf.recited_letter}' [${lf.status}]`
        ));
    });
    this.mistakesLog = msg.mistakes;
  }

  renderSummary(msg) {
    console.log("=== SESSION SUMMARY ===");
    console.log(`Score: ${msg.total_score} | Completion: ${msg.completion_percentage}%`);
    console.log(
      `Correct: ${msg.words_correct} | Diacritic: ${msg.words_diacritic_error} | ` +
      `Vowel: ${msg.words_vowel_error} | Letter: ${msg.words_letter_error} | ` +
      `Incorrect: ${msg.words_incorrect} | Not recited: ${msg.words_not_recited}`
    );
    if (msg.skipped_ayahs.length)  console.log("Skipped:",  msg.skipped_ayahs);
    if (msg.repeated_ayahs.length) console.log("Repeated:", msg.repeated_ayahs);

    msg.ayah_scores.forEach(a =>
      console.log(`  Ayah ${a.ayah}: ${a.score} (${a.words_correct}✓ ${a.words_errors}✗) ${a.note ?? ""}`)
    );
    console.log("Overall:", msg.overall_feedback);

    // ── Audio playback ────────────────────────────────────────────────────
    const rec = msg.recording;
    console.log(`Recording: source=${rec.source} | format=${rec.audio_format} | ` +
                `${rec.audio_size_bytes} bytes | ${rec.filename}`);

    if (rec.source === "recorded") {
      console.log("Real session audio captured — playing back now");
    } else {
      console.log("No audio was sent — playing mock sine-wave tone");
    }

    // Option A: play inline from base64 (works for both "recorded" and "mock")
    const mimeMap = { webm: "audio/webm", wav: "audio/wav", ogg: "audio/ogg", mp3: "audio/mpeg" };
    const bytes = Uint8Array.from(atob(rec.audio_data), c => c.charCodeAt(0));
    const blob  = new Blob([bytes], { type: mimeMap[rec.audio_format] ?? "audio/webm" });
    const audio = new Audio(URL.createObjectURL(blob));
    audio.play();

    // Option B: direct download via REST
    // window.open(`http://localhost:8000${rec.download_url}`);
  }
}

// ── Usage ──────────────────────────────────────────────────────────────────

// Connect with microphone access (real audio stored in summary)
const session = new RecitationSession(1);   // try use_case 1–5
session.connect();

// Send stop after all feedback is received (or wire to a UI button)
setTimeout(() => session.stop(), 15000);
```

---

## UI Rendering Checklist

Work through this list to verify your integration against each use case.

### Live session (during audio streaming)

- [ ] Word grid updates after every feedback chunk — words change from grey to their status colour
- [ ] Progress bar reflects `position_in_verse` (0.0 → 1.0)
- [ ] Ayah completion banner/animation triggers when `ayah_complete: true`
- [ ] Cumulative transcription (`transcribed_text`) updates and scrolls
- [ ] Mistake count badge increments when `mistakes` array grows
- [ ] Mistake cards appear for each new mistake (use `details` string for description)
- [ ] Words with `letter_feedback` show an expandable breakdown view
- [ ] Orange highlight for `diacritic_error`, yellow for `vowel_error`, red for `letter_error`
- [ ] **Case 2 only:** "Repetition detected" banner appears on chunk 2
- [ ] **Case 3 only:** "Skip detected" banner appears on chunk 2; words 1–2 stay grey forever

### Session summary screen

- [ ] `total_score` displayed prominently
- [ ] `completion_percentage` shown as ring/bar
- [ ] Word breakdown bars: correct / diacritic / vowel / letter / incorrect / not-recited
- [ ] Per-ayah score list with `note` text where present
- [ ] Mistakes list with `word_text`, `type`, `details`, optional `letter_feedback`
- [ ] **Case 2:** Repetition note visible on Ayah 1 row
- [ ] **Case 3:** Ayah 2 shows score 0 with "Skipped entirely" label
- [ ] Audio player uses `rec.audio_format` for the Blob MIME type (not a hardcoded `"wav"`)
- [ ] Audio player plays back `recording.audio_data` (base64 inline — no extra request)
- [ ] Download button links to `recording.download_url` with `rec.filename` as the suggested name
- [ ] When `recording.source === "recorded"` a "Your recording" label is shown; when `"mock"` a "Demo tone" notice is shown instead
- [ ] `overall_feedback` string shown as a summary paragraph
