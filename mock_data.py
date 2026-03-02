"""
Mock response data for all 9 test cases.

Case 1 – Smooth recitation:          1 vowel error + 1 letter error + 1 diacritic + 1 incorrect word
Case 2 – Repeat + mistakes:          user repeats Ayah 1 + 1 diacritic + 1 vowel error
Case 3 – Skip + mistakes:            user skips Ayah 2 + 1 diacritic + 1 letter error
Case 4 – Heavy harakat + extra:      3 diacritic + 2 vowel + 1 letter + 1 incorrect (7 mistakes)
Case 5 – Letter mistakes + extra:    2 letter + 2 vowel + 1 diacritic + 1 incorrect (6 mistakes)
Case 6 – Mixed (moderate):           1 incorrect + 1 letter + 2 diacritic + 2 vowel (6 mistakes)
Case 7 – Mixed (heavy):              2 incorrect + 1 letter + 2 diacritic + 2 vowel (7 mistakes)
Case 8 – Severe multi-type:          2 incorrect + 2 letter + 2 diacritic + 1 vowel (7 mistakes)
Case 9 – Extreme chaos:              1 incorrect + 3 letter + 2 diacritic + 2 vowel (8 mistakes)

Word-feedback status values
───────────────────────────
  "correct"        – base letters AND harakat match perfectly
  "diacritic_error"– base letters correct; a non-vowel diacritic wrong/missing
                     (shadda, tanwin, sukun …)
  "vowel_error"    – base letters correct; a short vowel wrong
                     (fatha↔kasra↔damma confused)
  "incorrect"      – wrong word entirely (base consonants differ significantly)
  "letter_error"   – a specific consonant letter substituted (e.g. خ → ح)
  "not_recited"    – word not reached yet

Summary structure
─────────────────
  Each session_summary contains:
  • "letter_mistakes"  – list of diacritic_error / vowel_error / letter_error entries,
                         each with word_position (0-based verse index) and full
                         letter_feedback array pinning the error to the exact letter pos.
  • "word_mistakes"    – list of incorrect entries, each with word_position reference.
  • "mistakes"         – flat combined list (backward-compat shorthand).
"""

import base64
import math
import struct
from typing import Any, Dict, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Word list  (Surah Ar-Rahman 55:1–8 · 21 words)
# ─────────────────────────────────────────────────────────────────────────────

WORDS = [
    {"id": "55:1:1", "text": "الرَّحْمَٰنُ"},
    {"id": "55:2:1", "text": "عَلَّمَ"},
    {"id": "55:2:2", "text": "الْقُرْآنَ"},
    {"id": "55:3:1", "text": "خَلَقَ"},
    {"id": "55:3:2", "text": "الْإِنسَانَ"},
    {"id": "55:4:1", "text": "عَلَّمَهُ"},
    {"id": "55:4:2", "text": "الْبَيَانَ"},
    {"id": "55:5:1", "text": "الشَّمْسُ"},
    {"id": "55:5:2", "text": "وَالْقَمَرُ"},
    {"id": "55:5:3", "text": "بِحُسْبَانٍ"},
    {"id": "55:6:1", "text": "وَالنَّجْمُ"},
    {"id": "55:6:2", "text": "وَالشَّجَرُ"},
    {"id": "55:6:3", "text": "يَسْجُدَانِ"},
    {"id": "55:7:1", "text": "وَالسَّمَاءَ"},
    {"id": "55:7:2", "text": "رَفَعَهَا"},
    {"id": "55:7:3", "text": "وَوَضَعَ"},
    {"id": "55:7:4", "text": "الْمِيزَانَ"},
    {"id": "55:8:1", "text": "أَلَّا"},
    {"id": "55:8:2", "text": "تَطْغَوْا"},
    {"id": "55:8:3", "text": "فِي"},
    {"id": "55:8:4", "text": "الْمِيزَانِ"},
]

# What Whisper hears for a correct recitation of each word
_RECITED = [
    "الرحمن", "علم", "القرآن", "خلق", "الانسان",
    "علمه", "البيان", "الشمس", "والقمر", "بحسبان",
    "والنجم", "والشجر", "يسجدان", "والسماء", "رفعها",
    "ووضع", "الميزان", "الا", "تطغوا", "في", "الميزان",
]


# ─────────────────────────────────────────────────────────────────────────────
# Mock WAV audio generation
# ─────────────────────────────────────────────────────────────────────────────

def _make_mock_wav(freq_hz: float = 440.0, duration_ms: int = 1000) -> str:
    """Return a base64-encoded 16 kHz mono 16-bit PCM WAV sine-wave tone."""
    sample_rate = 16000
    n_samples = int(sample_rate * duration_ms / 1000)
    amplitude = 8000

    pcm = bytearray()
    for i in range(n_samples):
        value = int(amplitude * math.sin(2.0 * math.pi * freq_hz * i / sample_rate))
        pcm += struct.pack("<h", value)

    data_size = len(pcm)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, 1,
        sample_rate, sample_rate * 2, 2, 16,
        b"data", data_size,
    )
    return base64.b64encode(header + bytes(pcm)).decode("ascii")


# Pre-computed per-case WAVs (distinct pitches A4→B3)
MOCK_WAVS: Dict[int, str] = {
    1: _make_mock_wav(440.00),   # A4
    2: _make_mock_wav(523.25),   # C5
    3: _make_mock_wav(392.00),   # G4
    4: _make_mock_wav(349.23),   # F4
    5: _make_mock_wav(293.66),   # D4
    6: _make_mock_wav(261.63),   # C4
    7: _make_mock_wav(329.63),   # E4
    8: _make_mock_wav(246.94),   # B3
    9: _make_mock_wav(220.00),   # A3
}


def _recording(case_num: int, duration_seconds: int) -> Dict[str, Any]:
    """Build the recording metadata block for a session_summary."""
    wav_b64 = MOCK_WAVS[case_num]
    size_bytes = len(base64.b64decode(wav_b64))
    return {
        "audio_data":       wav_b64,
        "audio_format":     "wav",
        "audio_size_bytes": size_bytes,
        "duration_seconds": duration_seconds,
        "filename":         f"recitation_case_{case_num}.wav",
        "download_url":     f"/api/recordings/{case_num}",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _wf(cursor: int, overrides: Optional[Dict] = None, skipped: Optional[Any] = None) -> List[Dict]:
    """Build the 21-element word_feedback list.

    cursor    – last word index reached (inclusive, 0-based)
    overrides – {index: (status, recited_text)}
                     or {index: (status, recited_text, letter_feedback)}
    skipped   – iterable of word indices that stay not_recited even if ≤ cursor
    """
    overrides = overrides or {}
    skipped = set(skipped or [])
    result = []
    for i, w in enumerate(WORDS):
        if i in skipped or i > cursor:
            result.append({
                "word_id": w["id"], "word_text": w["text"],
                "status": "not_recited", "recited_text": None,
            })
        elif i in overrides:
            ov = overrides[i]
            st, rt = ov[0], ov[1]
            lf = ov[2] if len(ov) > 2 else None
            entry: Dict[str, Any] = {
                "word_id": w["id"], "word_text": w["text"],
                "status": st, "recited_text": rt,
            }
            if lf is not None:
                entry["letter_feedback"] = lf
            result.append(entry)
        else:
            result.append({
                "word_id": w["id"], "word_text": w["text"],
                "status": "correct", "recited_text": _RECITED[i],
            })
    return result


def _txt(indices) -> str:
    """Join word texts at the given indices into a transcription string."""
    return " ".join(WORDS[i]["text"] for i in indices)


def _split_mistakes(mistakes: List[Dict]):
    """Return (letter_mistakes, word_mistakes) from a flat list."""
    letter = [m for m in mistakes if m["type"] != "incorrect"]
    word   = [m for m in mistakes if m["type"] == "incorrect"]
    return letter, word


# ─────────────────────────────────────────────────────────────────────────────
# Verse REST response  (GET /api/verses)
# ─────────────────────────────────────────────────────────────────────────────

VERSE_RESPONSE = [
    {
        "id": "55:1-8",
        "surah": 55,
        "ayah": 1,
        "text": (
            "الرَّحْمَٰنُ عَلَّمَ الْقُرْآنَ خَلَقَ الْإِنسَانَ عَلَّمَهُ الْبَيَانَ "
            "الشَّمْسُ وَالْقَمَرُ بِحُسْبَانٍ وَالنَّجْمُ وَالشَّجَرُ يَسْجُدَانِ "
            "وَالسَّمَاءَ رَفَعَهَا وَوَضَعَ الْمِيزَانَ أَلَّا تَطْغَوْا فِي الْمِيزَانِ"
        ),
        "words": [
            {"id": "55:1:1", "text": "الرَّحْمَٰنُ",  "letters": ["ا","ل","ر","َّ","ح","ْ","م","َ","ٰ","ن","ُ"],      "position": 0},
            {"id": "55:2:1", "text": "عَلَّمَ",        "letters": ["ع","َ","ل","َّ","م","َ"],                         "position": 1},
            {"id": "55:2:2", "text": "الْقُرْآنَ",     "letters": ["ا","ل","ْ","ق","ُ","ر","ْ","آ","ن","َ"],          "position": 2},
            {"id": "55:3:1", "text": "خَلَقَ",         "letters": ["خ","َ","ل","َ","ق","َ"],                         "position": 3},
            {"id": "55:3:2", "text": "الْإِنسَانَ",    "letters": ["ا","ل","ْ","إ","ِ","ن","س","َ","ا","ن","َ"],      "position": 4},
            {"id": "55:4:1", "text": "عَلَّمَهُ",      "letters": ["ع","َ","ل","َّ","م","َ","ه","ُ"],                 "position": 5},
            {"id": "55:4:2", "text": "الْبَيَانَ",     "letters": ["ا","ل","ْ","ب","َ","ي","َ","ا","ن","َ"],          "position": 6},
            {"id": "55:5:1", "text": "الشَّمْسُ",      "letters": ["ا","ل","ش","َّ","م","ْ","س","ُ"],                 "position": 7},
            {"id": "55:5:2", "text": "وَالْقَمَرُ",    "letters": ["و","َ","ا","ل","ْ","ق","َ","م","َ","ر","ُ"],      "position": 8},
            {"id": "55:5:3", "text": "بِحُسْبَانٍ",    "letters": ["ب","ِ","ح","ُ","س","ْ","ب","َ","ا","ن","ٍ"],      "position": 9},
            {"id": "55:6:1", "text": "وَالنَّجْمُ",    "letters": ["و","َ","ا","ل","ن","َّ","ج","ْ","م","ُ"],         "position": 10},
            {"id": "55:6:2", "text": "وَالشَّجَرُ",    "letters": ["و","َ","ا","ل","ش","َّ","ج","َ","ر","ُ"],         "position": 11},
            {"id": "55:6:3", "text": "يَسْجُدَانِ",    "letters": ["ي","َ","س","ْ","ج","ُ","د","َ","ا","ن","ِ"],      "position": 12},
            {"id": "55:7:1", "text": "وَالسَّمَاءَ",   "letters": ["و","َ","ا","ل","س","َّ","م","َ","ا","ء","َ"],     "position": 13},
            {"id": "55:7:2", "text": "رَفَعَهَا",      "letters": ["ر","َ","ف","َ","ع","َ","ه","َ","ا"],              "position": 14},
            {"id": "55:7:3", "text": "وَوَضَعَ",       "letters": ["و","َ","و","َ","ض","َ","ع","َ"],                  "position": 15},
            {"id": "55:7:4", "text": "الْمِيزَانَ",    "letters": ["ا","ل","ْ","م","ِ","ي","ز","َ","ا","ن","َ"],      "position": 16},
            {"id": "55:8:1", "text": "أَلَّا",         "letters": ["أ","َ","ل","َّ","ا"],                             "position": 17},
            {"id": "55:8:2", "text": "تَطْغَوْا",      "letters": ["ت","َ","ط","ْ","غ","َ","و","ْ","ا"],              "position": 18},
            {"id": "55:8:3", "text": "فِي",            "letters": ["ف","ِ","ي"],                                     "position": 19},
            {"id": "55:8:4", "text": "الْمِيزَانِ",    "letters": ["ا","ل","ْ","م","ِ","ي","ز","َ","ا","ن","ِ"],      "position": 20},
        ],
        "verse_boundaries": [
            {"ayah": 1, "end_word_index": 0},
            {"ayah": 2, "end_word_index": 2},
            {"ayah": 3, "end_word_index": 4},
            {"ayah": 4, "end_word_index": 6},
            {"ayah": 5, "end_word_index": 9},
            {"ayah": 6, "end_word_index": 12},
            {"ayah": 7, "end_word_index": 16},
            {"ayah": 8, "end_word_index": 20},
        ],
    }
]


# ─────────────────────────────────────────────────────────────────────────────
# Letter-feedback arrays
# Each entry: { position, expected_letter, recited_letter, status }
# status values: "correct" | "diacritic_error" | "vowel_error" | "letter_error"
# ─────────────────────────────────────────────────────────────────────────────
#
# Naming convention:  _LF_W{word_index}_{TYPE}_{CASE}
#   word_index  = 0-based position in WORDS
#   TYPE        = DIAC | VOWEL | LETTER
#   CASE        = case number(s) that use it
#
# Arrays shared by multiple cases are defined once and reused.

# ── word 0 · الرَّحْمَٰنُ ───────────────────────────────────────────────────
# letters: ["ا","ل","ر","َّ","ح","ْ","م","َ","ٰ","ن","ُ"]

# Cases 4, 8  – letter_error: ح (pos 4) → خ
_LF_W0_LETTER = [
    {"position": 0,  "expected_letter": "ا",  "recited_letter": "ا",  "status": "correct"},
    {"position": 1,  "expected_letter": "ل",  "recited_letter": "ل",  "status": "correct"},
    {"position": 2,  "expected_letter": "ر",  "recited_letter": "ر",  "status": "correct"},
    {"position": 3,  "expected_letter": "َّ", "recited_letter": "َّ", "status": "correct"},
    {"position": 4,  "expected_letter": "ح",  "recited_letter": "خ",  "status": "letter_error"},
    {"position": 5,  "expected_letter": "ْ",  "recited_letter": "ْ",  "status": "correct"},
    {"position": 6,  "expected_letter": "م",  "recited_letter": "م",  "status": "correct"},
    {"position": 7,  "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
    {"position": 8,  "expected_letter": "ٰ",  "recited_letter": "ٰ",  "status": "correct"},
    {"position": 9,  "expected_letter": "ن",  "recited_letter": "ن",  "status": "correct"},
    {"position": 10, "expected_letter": "ُ",  "recited_letter": "ُ",  "status": "correct"},
]

# Case 8 – diacritic_error: shadda on رَّ (pos 3) dropped → "الرَحْمَٰنُ"
_LF_W0_DIAC = [
    {"position": 0,  "expected_letter": "ا",  "recited_letter": "ا",  "status": "correct"},
    {"position": 1,  "expected_letter": "ل",  "recited_letter": "ل",  "status": "correct"},
    {"position": 2,  "expected_letter": "ر",  "recited_letter": "ر",  "status": "correct"},
    {"position": 3,  "expected_letter": "َّ", "recited_letter": "َ",  "status": "diacritic_error"},
    {"position": 4,  "expected_letter": "ح",  "recited_letter": "ح",  "status": "correct"},
    {"position": 5,  "expected_letter": "ْ",  "recited_letter": "ْ",  "status": "correct"},
    {"position": 6,  "expected_letter": "م",  "recited_letter": "م",  "status": "correct"},
    {"position": 7,  "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
    {"position": 8,  "expected_letter": "ٰ",  "recited_letter": "ٰ",  "status": "correct"},
    {"position": 9,  "expected_letter": "ن",  "recited_letter": "ن",  "status": "correct"},
    {"position": 10, "expected_letter": "ُ",  "recited_letter": "ُ",  "status": "correct"},
]

# ── word 1 · عَلَّمَ ─────────────────────────────────────────────────────────
# letters: ["ع","َ","ل","َّ","م","َ"]

# Cases 4, 5, 9  – diacritic_error: shadda on لَّ (pos 3) dropped → "عَلَمَ"
_LF_W1_DIAC = [
    {"position": 0, "expected_letter": "ع",  "recited_letter": "ع",  "status": "correct"},
    {"position": 1, "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
    {"position": 2, "expected_letter": "ل",  "recited_letter": "ل",  "status": "correct"},
    {"position": 3, "expected_letter": "َّ", "recited_letter": "َ",  "status": "diacritic_error"},
    {"position": 4, "expected_letter": "م",  "recited_letter": "م",  "status": "correct"},
    {"position": 5, "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
]

# ── word 2 · الْقُرْآنَ ───────────────────────────────────────────────────────
# letters: ["ا","ل","ْ","ق","ُ","ر","ْ","آ","ن","َ"]

# Cases 6  – diacritic_error: sukūn on رْ (pos 6) dropped → "الْقُرَآنَ"
_LF_W2_DIAC = [
    {"position": 0, "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 1, "expected_letter": "ل", "recited_letter": "ل", "status": "correct"},
    {"position": 2, "expected_letter": "ْ", "recited_letter": "ْ", "status": "correct"},
    {"position": 3, "expected_letter": "ق", "recited_letter": "ق", "status": "correct"},
    {"position": 4, "expected_letter": "ُ", "recited_letter": "ُ", "status": "correct"},
    {"position": 5, "expected_letter": "ر", "recited_letter": "ر", "status": "correct"},
    {"position": 6, "expected_letter": "ْ", "recited_letter": "",  "status": "diacritic_error"},
    {"position": 7, "expected_letter": "آ", "recited_letter": "آ", "status": "correct"},
    {"position": 8, "expected_letter": "ن", "recited_letter": "ن", "status": "correct"},
    {"position": 9, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
]

# ── word 3 · خَلَقَ ──────────────────────────────────────────────────────────
# letters: ["خ","َ","ل","َ","ق","َ"]

# Cases 1  – vowel_error: fatha on خ (pos 1) → kasra → "خِلَقَ"
_LF_W3_VOWEL = [
    {"position": 0, "expected_letter": "خ", "recited_letter": "خ", "status": "correct"},
    {"position": 1, "expected_letter": "َ", "recited_letter": "ِ", "status": "vowel_error"},
    {"position": 2, "expected_letter": "ل", "recited_letter": "ل", "status": "correct"},
    {"position": 3, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 4, "expected_letter": "ق", "recited_letter": "ق", "status": "correct"},
    {"position": 5, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
]

# Cases 5, 9  – letter_error: خ (pos 0) → ح → "حَلَقَ"
_LF_W3_LETTER = [
    {"position": 0, "expected_letter": "خ", "recited_letter": "ح", "status": "letter_error"},
    {"position": 1, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 2, "expected_letter": "ل", "recited_letter": "ل", "status": "correct"},
    {"position": 3, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 4, "expected_letter": "ق", "recited_letter": "ق", "status": "correct"},
    {"position": 5, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
]

# Case 7  – vowel_error: fatha on ل (pos 3) → damma → "خَلُقَ"
_LF_W3_VOWEL_C7 = [
    {"position": 0, "expected_letter": "خ", "recited_letter": "خ", "status": "correct"},
    {"position": 1, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 2, "expected_letter": "ل", "recited_letter": "ل", "status": "correct"},
    {"position": 3, "expected_letter": "َ", "recited_letter": "ُ", "status": "vowel_error"},
    {"position": 4, "expected_letter": "ق", "recited_letter": "ق", "status": "correct"},
    {"position": 5, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
]

# ── word 4 · الْإِنسَانَ ──────────────────────────────────────────────────────
# letters: ["ا","ل","ْ","إ","ِ","ن","س","َ","ا","ن","َ"]

# Case 9  – letter_error: ن (pos 5) → م → "الْإِمسَانَ"
_LF_W4_LETTER = [
    {"position": 0,  "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 1,  "expected_letter": "ل", "recited_letter": "ل", "status": "correct"},
    {"position": 2,  "expected_letter": "ْ", "recited_letter": "ْ", "status": "correct"},
    {"position": 3,  "expected_letter": "إ", "recited_letter": "إ", "status": "correct"},
    {"position": 4,  "expected_letter": "ِ", "recited_letter": "ِ", "status": "correct"},
    {"position": 5,  "expected_letter": "ن", "recited_letter": "م", "status": "letter_error"},
    {"position": 6,  "expected_letter": "س", "recited_letter": "س", "status": "correct"},
    {"position": 7,  "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 8,  "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 9,  "expected_letter": "ن", "recited_letter": "ن", "status": "correct"},
    {"position": 10, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
]

# ── word 5 · عَلَّمَهُ ────────────────────────────────────────────────────────
# letters: ["ع","َ","ل","َّ","م","َ","ه","ُ"]

# Cases 4  – diacritic_error: damma on هُ (pos 7) dropped → "عَلَّمَه"
_LF_W5_DIAC = [
    {"position": 0, "expected_letter": "ع",  "recited_letter": "ع",  "status": "correct"},
    {"position": 1, "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
    {"position": 2, "expected_letter": "ل",  "recited_letter": "ل",  "status": "correct"},
    {"position": 3, "expected_letter": "َّ", "recited_letter": "َّ", "status": "correct"},
    {"position": 4, "expected_letter": "م",  "recited_letter": "م",  "status": "correct"},
    {"position": 5, "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
    {"position": 6, "expected_letter": "ه",  "recited_letter": "ه",  "status": "correct"},
    {"position": 7, "expected_letter": "ُ",  "recited_letter": "",   "status": "diacritic_error"},
]

# Case 8  – letter_error: ه (pos 6) → ح → "عَلَّمَحُ"
_LF_W5_LETTER = [
    {"position": 0, "expected_letter": "ع",  "recited_letter": "ع",  "status": "correct"},
    {"position": 1, "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
    {"position": 2, "expected_letter": "ل",  "recited_letter": "ل",  "status": "correct"},
    {"position": 3, "expected_letter": "َّ", "recited_letter": "َّ", "status": "correct"},
    {"position": 4, "expected_letter": "م",  "recited_letter": "م",  "status": "correct"},
    {"position": 5, "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
    {"position": 6, "expected_letter": "ه",  "recited_letter": "ح",  "status": "letter_error"},
    {"position": 7, "expected_letter": "ُ",  "recited_letter": "ُ",  "status": "correct"},
]

# Case 9  – vowel_error: damma on هُ (pos 7) → kasra → "عَلَّمَهِ"
_LF_W5_VOWEL = [
    {"position": 0, "expected_letter": "ع",  "recited_letter": "ع",  "status": "correct"},
    {"position": 1, "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
    {"position": 2, "expected_letter": "ل",  "recited_letter": "ل",  "status": "correct"},
    {"position": 3, "expected_letter": "َّ", "recited_letter": "َّ", "status": "correct"},
    {"position": 4, "expected_letter": "م",  "recited_letter": "م",  "status": "correct"},
    {"position": 5, "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
    {"position": 6, "expected_letter": "ه",  "recited_letter": "ه",  "status": "correct"},
    {"position": 7, "expected_letter": "ُ",  "recited_letter": "ِ",  "status": "vowel_error"},
]

# ── word 6 · الْبَيَانَ ───────────────────────────────────────────────────────
# letters: ["ا","ل","ْ","ب","َ","ي","َ","ا","ن","َ"]

# Case 2  – diacritic_error: sukūn on لْ (pos 2) dropped → "الَبَيَانَ"
_LF_W6_DIAC = [
    {"position": 0, "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 1, "expected_letter": "ل", "recited_letter": "ل", "status": "correct"},
    {"position": 2, "expected_letter": "ْ", "recited_letter": "",  "status": "diacritic_error"},
    {"position": 3, "expected_letter": "ب", "recited_letter": "ب", "status": "correct"},
    {"position": 4, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 5, "expected_letter": "ي", "recited_letter": "ي", "status": "correct"},
    {"position": 6, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 7, "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 8, "expected_letter": "ن", "recited_letter": "ن", "status": "correct"},
    {"position": 9, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
]

# Cases 7  – letter_error: ب (pos 3) → ف → "الْفَيَانَ"
_LF_W6_LETTER = [
    {"position": 0, "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 1, "expected_letter": "ل", "recited_letter": "ل", "status": "correct"},
    {"position": 2, "expected_letter": "ْ", "recited_letter": "ْ", "status": "correct"},
    {"position": 3, "expected_letter": "ب", "recited_letter": "ف", "status": "letter_error"},
    {"position": 4, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 5, "expected_letter": "ي", "recited_letter": "ي", "status": "correct"},
    {"position": 6, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 7, "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 8, "expected_letter": "ن", "recited_letter": "ن", "status": "correct"},
    {"position": 9, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
]

# ── word 7 · الشَّمْسُ ────────────────────────────────────────────────────────
# letters: ["ا","ل","ش","َّ","م","ْ","س","ُ"]

# Case 1  – letter_error: س (pos 6) → ص → "الشَّمْصُ"
_LF_W7_LETTER = [
    {"position": 0, "expected_letter": "ا",  "recited_letter": "ا",  "status": "correct"},
    {"position": 1, "expected_letter": "ل",  "recited_letter": "ل",  "status": "correct"},
    {"position": 2, "expected_letter": "ش",  "recited_letter": "ش",  "status": "correct"},
    {"position": 3, "expected_letter": "َّ", "recited_letter": "َّ", "status": "correct"},
    {"position": 4, "expected_letter": "م",  "recited_letter": "م",  "status": "correct"},
    {"position": 5, "expected_letter": "ْ",  "recited_letter": "ْ",  "status": "correct"},
    {"position": 6, "expected_letter": "س",  "recited_letter": "ص",  "status": "letter_error"},
    {"position": 7, "expected_letter": "ُ",  "recited_letter": "ُ",  "status": "correct"},
]

# Cases 6  – letter_error: ش (pos 2) → ص → "الصَّمْسُ"
_LF_W7_LETTER_C6 = [
    {"position": 0, "expected_letter": "ا",  "recited_letter": "ا",  "status": "correct"},
    {"position": 1, "expected_letter": "ل",  "recited_letter": "ل",  "status": "correct"},
    {"position": 2, "expected_letter": "ش",  "recited_letter": "ص",  "status": "letter_error"},
    {"position": 3, "expected_letter": "َّ", "recited_letter": "َّ", "status": "correct"},
    {"position": 4, "expected_letter": "م",  "recited_letter": "م",  "status": "correct"},
    {"position": 5, "expected_letter": "ْ",  "recited_letter": "ْ",  "status": "correct"},
    {"position": 6, "expected_letter": "س",  "recited_letter": "س",  "status": "correct"},
    {"position": 7, "expected_letter": "ُ",  "recited_letter": "ُ",  "status": "correct"},
]

# ── word 8 · وَالْقَمَرُ ──────────────────────────────────────────────────────
# letters: ["و","َ","ا","ل","ْ","ق","َ","م","َ","ر","ُ"]

# Case 3  – diacritic_error: damma on رُ (pos 10) dropped → "وَالْقَمَر"
_LF_W8_DIAC = [
    {"position": 0,  "expected_letter": "و", "recited_letter": "و", "status": "correct"},
    {"position": 1,  "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 2,  "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 3,  "expected_letter": "ل", "recited_letter": "ل", "status": "correct"},
    {"position": 4,  "expected_letter": "ْ", "recited_letter": "ْ", "status": "correct"},
    {"position": 5,  "expected_letter": "ق", "recited_letter": "ق", "status": "correct"},
    {"position": 6,  "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 7,  "expected_letter": "م", "recited_letter": "م", "status": "correct"},
    {"position": 8,  "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 9,  "expected_letter": "ر", "recited_letter": "ر", "status": "correct"},
    {"position": 10, "expected_letter": "ُ", "recited_letter": "",  "status": "diacritic_error"},
]

# Case 5  – letter_error: ق (pos 5) → غ → "وَالْغَمَرُ"
_LF_W8_LETTER = [
    {"position": 0,  "expected_letter": "و", "recited_letter": "و", "status": "correct"},
    {"position": 1,  "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 2,  "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 3,  "expected_letter": "ل", "recited_letter": "ل", "status": "correct"},
    {"position": 4,  "expected_letter": "ْ", "recited_letter": "ْ", "status": "correct"},
    {"position": 5,  "expected_letter": "ق", "recited_letter": "غ", "status": "letter_error"},
    {"position": 6,  "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 7,  "expected_letter": "م", "recited_letter": "م", "status": "correct"},
    {"position": 8,  "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 9,  "expected_letter": "ر", "recited_letter": "ر", "status": "correct"},
    {"position": 10, "expected_letter": "ُ", "recited_letter": "ُ", "status": "correct"},
]

# Case 9  – letter_error: ق (pos 5) → ك → "وَالْكَمَرُ"
_LF_W8_LETTER_C9 = [
    {"position": 0,  "expected_letter": "و", "recited_letter": "و", "status": "correct"},
    {"position": 1,  "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 2,  "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 3,  "expected_letter": "ل", "recited_letter": "ل", "status": "correct"},
    {"position": 4,  "expected_letter": "ْ", "recited_letter": "ْ", "status": "correct"},
    {"position": 5,  "expected_letter": "ق", "recited_letter": "ك", "status": "letter_error"},
    {"position": 6,  "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 7,  "expected_letter": "م", "recited_letter": "م", "status": "correct"},
    {"position": 8,  "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 9,  "expected_letter": "ر", "recited_letter": "ر", "status": "correct"},
    {"position": 10, "expected_letter": "ُ", "recited_letter": "ُ", "status": "correct"},
]

# ── word 9 · بِحُسْبَانٍ ──────────────────────────────────────────────────────
# letters: ["ب","ِ","ح","ُ","س","ْ","ب","َ","ا","ن","ٍ"]

# Cases 7, 8  – diacritic_error: tanwīn kasra ٍ (pos 10) dropped → "بِحُسْبَانَ"
_LF_W9_DIAC = [
    {"position": 0,  "expected_letter": "ب", "recited_letter": "ب", "status": "correct"},
    {"position": 1,  "expected_letter": "ِ", "recited_letter": "ِ", "status": "correct"},
    {"position": 2,  "expected_letter": "ح", "recited_letter": "ح", "status": "correct"},
    {"position": 3,  "expected_letter": "ُ", "recited_letter": "ُ", "status": "correct"},
    {"position": 4,  "expected_letter": "س", "recited_letter": "س", "status": "correct"},
    {"position": 5,  "expected_letter": "ْ", "recited_letter": "ْ", "status": "correct"},
    {"position": 6,  "expected_letter": "ب", "recited_letter": "ب", "status": "correct"},
    {"position": 7,  "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 8,  "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 9,  "expected_letter": "ن", "recited_letter": "ن", "status": "correct"},
    {"position": 10, "expected_letter": "ٍ", "recited_letter": "",  "status": "diacritic_error"},
]

# ── word 10 · وَالنَّجْمُ ─────────────────────────────────────────────────────
# letters: ["و","َ","ا","ل","ن","َّ","ج","ْ","م","ُ"]

# Cases 2, 5  – vowel_error: damma on مُ (pos 9) → kasra → "وَالنَّجْمِ"
_LF_W10_VOWEL = [
    {"position": 0, "expected_letter": "و",  "recited_letter": "و",  "status": "correct"},
    {"position": 1, "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
    {"position": 2, "expected_letter": "ا",  "recited_letter": "ا",  "status": "correct"},
    {"position": 3, "expected_letter": "ل",  "recited_letter": "ل",  "status": "correct"},
    {"position": 4, "expected_letter": "ن",  "recited_letter": "ن",  "status": "correct"},
    {"position": 5, "expected_letter": "َّ", "recited_letter": "َّ", "status": "correct"},
    {"position": 6, "expected_letter": "ج",  "recited_letter": "ج",  "status": "correct"},
    {"position": 7, "expected_letter": "ْ",  "recited_letter": "ْ",  "status": "correct"},
    {"position": 8, "expected_letter": "م",  "recited_letter": "م",  "status": "correct"},
    {"position": 9, "expected_letter": "ُ",  "recited_letter": "ِ",  "status": "vowel_error"},
]

# Case 9  – diacritic_error: shadda on نَّ (pos 5) dropped → "وَالنَجْمُ"
_LF_W10_DIAC = [
    {"position": 0, "expected_letter": "و",  "recited_letter": "و",  "status": "correct"},
    {"position": 1, "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
    {"position": 2, "expected_letter": "ا",  "recited_letter": "ا",  "status": "correct"},
    {"position": 3, "expected_letter": "ل",  "recited_letter": "ل",  "status": "correct"},
    {"position": 4, "expected_letter": "ن",  "recited_letter": "ن",  "status": "correct"},
    {"position": 5, "expected_letter": "َّ", "recited_letter": "َ",  "status": "diacritic_error"},
    {"position": 6, "expected_letter": "ج",  "recited_letter": "ج",  "status": "correct"},
    {"position": 7, "expected_letter": "ْ",  "recited_letter": "ْ",  "status": "correct"},
    {"position": 8, "expected_letter": "م",  "recited_letter": "م",  "status": "correct"},
    {"position": 9, "expected_letter": "ُ",  "recited_letter": "ُ",  "status": "correct"},
]

# ── word 11 · وَالشَّجَرُ ─────────────────────────────────────────────────────
# letters: ["و","َ","ا","ل","ش","َّ","ج","َ","ر","ُ"]

# Cases 6  – diacritic_error: shadda on شَّ (pos 5) dropped → "وَالشَجَرُ"
_LF_W11_DIAC = [
    {"position": 0, "expected_letter": "و",  "recited_letter": "و",  "status": "correct"},
    {"position": 1, "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
    {"position": 2, "expected_letter": "ا",  "recited_letter": "ا",  "status": "correct"},
    {"position": 3, "expected_letter": "ل",  "recited_letter": "ل",  "status": "correct"},
    {"position": 4, "expected_letter": "ش",  "recited_letter": "ش",  "status": "correct"},
    {"position": 5, "expected_letter": "َّ", "recited_letter": "َ",  "status": "diacritic_error"},
    {"position": 6, "expected_letter": "ج",  "recited_letter": "ج",  "status": "correct"},
    {"position": 7, "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
    {"position": 8, "expected_letter": "ر",  "recited_letter": "ر",  "status": "correct"},
    {"position": 9, "expected_letter": "ُ",  "recited_letter": "ُ",  "status": "correct"},
]

# Case 8  – vowel_error: damma on رُ (pos 9) → fatha → "وَالشَّجَرَ"
_LF_W11_VOWEL = [
    {"position": 0, "expected_letter": "و",  "recited_letter": "و",  "status": "correct"},
    {"position": 1, "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
    {"position": 2, "expected_letter": "ا",  "recited_letter": "ا",  "status": "correct"},
    {"position": 3, "expected_letter": "ل",  "recited_letter": "ل",  "status": "correct"},
    {"position": 4, "expected_letter": "ش",  "recited_letter": "ش",  "status": "correct"},
    {"position": 5, "expected_letter": "َّ", "recited_letter": "َّ", "status": "correct"},
    {"position": 6, "expected_letter": "ج",  "recited_letter": "ج",  "status": "correct"},
    {"position": 7, "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
    {"position": 8, "expected_letter": "ر",  "recited_letter": "ر",  "status": "correct"},
    {"position": 9, "expected_letter": "ُ",  "recited_letter": "َ",  "status": "vowel_error"},
]

# ── word 12 · يَسْجُدَانِ ─────────────────────────────────────────────────────
# letters: ["ي","َ","س","ْ","ج","ُ","د","َ","ا","ن","ِ"]

# Case 4  – diacritic_error: kasra on نِ (pos 10) → fatha
_LF_W12_DIAC = [
    {"position": 0,  "expected_letter": "ي", "recited_letter": "ي", "status": "correct"},
    {"position": 1,  "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 2,  "expected_letter": "س", "recited_letter": "س", "status": "correct"},
    {"position": 3,  "expected_letter": "ْ", "recited_letter": "ْ", "status": "correct"},
    {"position": 4,  "expected_letter": "ج", "recited_letter": "ج", "status": "correct"},
    {"position": 5,  "expected_letter": "ُ", "recited_letter": "ُ", "status": "correct"},
    {"position": 6,  "expected_letter": "د", "recited_letter": "د", "status": "correct"},
    {"position": 7,  "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 8,  "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 9,  "expected_letter": "ن", "recited_letter": "ن", "status": "correct"},
    {"position": 10, "expected_letter": "ِ", "recited_letter": "َ", "status": "vowel_error"},
]

# Case 7  – diacritic_error: sukūn on سْ (pos 3) dropped → "يَسَجُدَانِ"
_LF_W12_DIAC_C7 = [
    {"position": 0,  "expected_letter": "ي", "recited_letter": "ي", "status": "correct"},
    {"position": 1,  "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 2,  "expected_letter": "س", "recited_letter": "س", "status": "correct"},
    {"position": 3,  "expected_letter": "ْ", "recited_letter": "",  "status": "diacritic_error"},
    {"position": 4,  "expected_letter": "ج", "recited_letter": "ج", "status": "correct"},
    {"position": 5,  "expected_letter": "ُ", "recited_letter": "ُ", "status": "correct"},
    {"position": 6,  "expected_letter": "د", "recited_letter": "د", "status": "correct"},
    {"position": 7,  "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 8,  "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 9,  "expected_letter": "ن", "recited_letter": "ن", "status": "correct"},
    {"position": 10, "expected_letter": "ِ", "recited_letter": "ِ", "status": "correct"},
]

# ── word 14 · رَفَعَهَا ───────────────────────────────────────────────────────
# letters: ["ر","َ","ف","َ","ع","َ","ه","َ","ا"]

# Case 4  – vowel_error: fatha→damma on رَ (pos 1) + fatha→kasra on فَ (pos 3)
_LF_W14_VOWEL = [
    {"position": 0, "expected_letter": "ر", "recited_letter": "ر", "status": "correct"},
    {"position": 1, "expected_letter": "َ", "recited_letter": "ُ", "status": "vowel_error"},
    {"position": 2, "expected_letter": "ف", "recited_letter": "ف", "status": "correct"},
    {"position": 3, "expected_letter": "َ", "recited_letter": "ِ", "status": "vowel_error"},
    {"position": 4, "expected_letter": "ع", "recited_letter": "ع", "status": "correct"},
    {"position": 5, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 6, "expected_letter": "ه", "recited_letter": "ه", "status": "correct"},
    {"position": 7, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 8, "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
]

# Case 3  – letter_error: ف (pos 2) → ق → "رَقَعَهَا"
_LF_W14_LETTER = [
    {"position": 0, "expected_letter": "ر", "recited_letter": "ر", "status": "correct"},
    {"position": 1, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 2, "expected_letter": "ف", "recited_letter": "ق", "status": "letter_error"},
    {"position": 3, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 4, "expected_letter": "ع", "recited_letter": "ع", "status": "correct"},
    {"position": 5, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 6, "expected_letter": "ه", "recited_letter": "ه", "status": "correct"},
    {"position": 7, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 8, "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
]

# Case 8  – letter_error: ع (pos 4) → غ → "رَفَغَهَا"
_LF_W14_LETTER_C8 = [
    {"position": 0, "expected_letter": "ر", "recited_letter": "ر", "status": "correct"},
    {"position": 1, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 2, "expected_letter": "ف", "recited_letter": "ف", "status": "correct"},
    {"position": 3, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 4, "expected_letter": "ع", "recited_letter": "غ", "status": "letter_error"},
    {"position": 5, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 6, "expected_letter": "ه", "recited_letter": "ه", "status": "correct"},
    {"position": 7, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 8, "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
]

# ── word 15 · وَوَضَعَ ────────────────────────────────────────────────────────
# letters: ["و","َ","و","َ","ض","َ","ع","َ"]

# Cases 5, 6, 9  – vowel_error: fatha on ضَ (pos 5) → kasra → "وَوَضِعَ"
_LF_W15_VOWEL = [
    {"position": 0, "expected_letter": "و", "recited_letter": "و", "status": "correct"},
    {"position": 1, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 2, "expected_letter": "و", "recited_letter": "و", "status": "correct"},
    {"position": 3, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 4, "expected_letter": "ض", "recited_letter": "ض", "status": "correct"},
    {"position": 5, "expected_letter": "َ", "recited_letter": "ِ", "status": "vowel_error"},
    {"position": 6, "expected_letter": "ع", "recited_letter": "ع", "status": "correct"},
    {"position": 7, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
]

# ── word 16 · الْمِيزَانَ ─────────────────────────────────────────────────────
# letters: ["ا","ل","ْ","م","ِ","ي","ز","َ","ا","ن","َ"]

# Cases 4, 9  – vowel_error: kasra on مِ (pos 4) → fatha → "الْمَيزَانَ"
_LF_W16_VOWEL = [
    {"position": 0,  "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 1,  "expected_letter": "ل", "recited_letter": "ل", "status": "correct"},
    {"position": 2,  "expected_letter": "ْ", "recited_letter": "ْ", "status": "correct"},
    {"position": 3,  "expected_letter": "م", "recited_letter": "م", "status": "correct"},
    {"position": 4,  "expected_letter": "ِ", "recited_letter": "َ", "status": "vowel_error"},
    {"position": 5,  "expected_letter": "ي", "recited_letter": "ي", "status": "correct"},
    {"position": 6,  "expected_letter": "ز", "recited_letter": "ز", "status": "correct"},
    {"position": 7,  "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 8,  "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 9,  "expected_letter": "ن", "recited_letter": "ن", "status": "correct"},
    {"position": 10, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
]

# Case 7  – vowel_error: kasra on مِ (pos 4) → damma → "الْمُيزَانَ"
_LF_W16_VOWEL_C7 = [
    {"position": 0,  "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 1,  "expected_letter": "ل", "recited_letter": "ل", "status": "correct"},
    {"position": 2,  "expected_letter": "ْ", "recited_letter": "ْ", "status": "correct"},
    {"position": 3,  "expected_letter": "م", "recited_letter": "م", "status": "correct"},
    {"position": 4,  "expected_letter": "ِ", "recited_letter": "ُ", "status": "vowel_error"},
    {"position": 5,  "expected_letter": "ي", "recited_letter": "ي", "status": "correct"},
    {"position": 6,  "expected_letter": "ز", "recited_letter": "ز", "status": "correct"},
    {"position": 7,  "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 8,  "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 9,  "expected_letter": "ن", "recited_letter": "ن", "status": "correct"},
    {"position": 10, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
]

# ── word 17 · أَلَّا ──────────────────────────────────────────────────────────
# letters: ["أ","َ","ل","َّ","ا"]

# Cases 6  – vowel_error: fatha on أَ (pos 1) → kasra → "إِلَّا"
_LF_W17_VOWEL = [
    {"position": 0, "expected_letter": "أ",  "recited_letter": "أ",  "status": "correct"},
    {"position": 1, "expected_letter": "َ",  "recited_letter": "ِ",  "status": "vowel_error"},
    {"position": 2, "expected_letter": "ل",  "recited_letter": "ل",  "status": "correct"},
    {"position": 3, "expected_letter": "َّ", "recited_letter": "َّ", "status": "correct"},
    {"position": 4, "expected_letter": "ا",  "recited_letter": "ا",  "status": "correct"},
]

# Case 9  – letter_error: ل (pos 2) → ن → "أَنَّا"
_LF_W17_LETTER = [
    {"position": 0, "expected_letter": "أ",  "recited_letter": "أ",  "status": "correct"},
    {"position": 1, "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
    {"position": 2, "expected_letter": "ل",  "recited_letter": "ن",  "status": "letter_error"},
    {"position": 3, "expected_letter": "َّ", "recited_letter": "َّ", "status": "correct"},
    {"position": 4, "expected_letter": "ا",  "recited_letter": "ا",  "status": "correct"},
]

# ── word 20 · الْمِيزَانِ ─────────────────────────────────────────────────────
# letters: ["ا","ل","ْ","م","ِ","ي","ز","َ","ا","ن","ِ"]

# Case 9  – diacritic_error: kasra on نِ (pos 10) dropped → "الْمِيزَانُ"
_LF_W20_DIAC = [
    {"position": 0,  "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 1,  "expected_letter": "ل", "recited_letter": "ل", "status": "correct"},
    {"position": 2,  "expected_letter": "ْ", "recited_letter": "ْ", "status": "correct"},
    {"position": 3,  "expected_letter": "م", "recited_letter": "م", "status": "correct"},
    {"position": 4,  "expected_letter": "ِ", "recited_letter": "ِ", "status": "correct"},
    {"position": 5,  "expected_letter": "ي", "recited_letter": "ي", "status": "correct"},
    {"position": 6,  "expected_letter": "ز", "recited_letter": "ز", "status": "correct"},
    {"position": 7,  "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 8,  "expected_letter": "ا", "recited_letter": "ا", "status": "correct"},
    {"position": 9,  "expected_letter": "ن", "recited_letter": "ن", "status": "correct"},
    {"position": 10, "expected_letter": "ِ", "recited_letter": "",  "status": "diacritic_error"},
]


# ─────────────────────────────────────────────────────────────────────────────
# Case 1 – Mixed: vowel error + letter error + diacritic error + incorrect word
#
# Mistakes:
#   Word  3  (خَلَقَ)      – vowel_error:      fatha on خ → kasra   → "خِلَقَ"
#   Word  7  (الشَّمْسُ)   – letter_error:     س (pos 6) → ص       → "الشَّمْصُ"
#   Word  9  (بِحُسْبَانٍ) – diacritic_error:  tanwīn kasra missing  → "بِحُسْبَانَ"
#   Word 18  (تَطْغَوْا)   – incorrect:        dropped ending        → "تطغو"
# ─────────────────────────────────────────────────────────────────────────────

_C1_STATUS = {
    "type": "status", "verse_id": "55:1-8",
    "message": "Session started. Ready to receive audio.",
    "total_words": 21, "total_ayahs": 8,
}

_C1_ERR = {3: "خِلَقَ", 7: "الشَّمْصُ", 9: "بِحُسْبَانَ", 18: "تطغو"}

_C1_OVR = {
    3:  ("vowel_error",     _C1_ERR[3],  _LF_W3_VOWEL),
    7:  ("letter_error",    _C1_ERR[7],  _LF_W7_LETTER),
    9:  ("diacritic_error", _C1_ERR[9],  _LF_W9_DIAC),
    18: ("incorrect",       _C1_ERR[18], None),
}

_M1_VOWEL = {
    "word_id": "55:3:1", "word_text": "خَلَقَ", "word_position": 3,
    "type": "vowel_error", "recited_text": _C1_ERR[3],
    "details": "Fatha (َ) on khā recited as kasra (ِ) — خَلَقَ became خِلَقَ",
    "letter_feedback": _LF_W3_VOWEL,
}
_M1_LETTER = {
    "word_id": "55:5:1", "word_text": "الشَّمْسُ", "word_position": 7,
    "type": "letter_error", "recited_text": _C1_ERR[7],
    "details": "سِين (س) recited as صَاد (ص) — emphatic substitution at word end",
    "letter_feedback": _LF_W7_LETTER,
}
_M1_DIAC = {
    "word_id": "55:5:3", "word_text": "بِحُسْبَانٍ", "word_position": 9,
    "type": "diacritic_error", "recited_text": _C1_ERR[9],
    "details": "Tanwīn kasra (ٍ) missing at end — nunation dropped",
    "letter_feedback": _LF_W9_DIAC,
}
_M1_INCR = {
    "word_id": "55:8:2", "word_text": "تَطْغَوْا", "word_position": 18,
    "type": "incorrect", "recited_text": _C1_ERR[18],
    "details": "Ending 'وا' dropped — تَطْغَوْا recited as تطغو",
}

_C1_ALL = [_M1_VOWEL, _M1_LETTER, _M1_DIAC, _M1_INCR]


def _c1_tx(cursor: int) -> str:
    return " ".join(_C1_ERR.get(i, WORDS[i]["text"]) for i in range(cursor + 1))


def _c1(ci, cursor, ayah, pos, complete, mistakes):
    return {
        "type": "feedback", "chunk_index": ci,
        "transcribed_text": _c1_tx(cursor),
        "current_ayah": ayah, "word_cursor": cursor,
        "position_in_verse": pos, "ayah_complete": complete,
        "skipped_ayahs": [], "repeated_ayahs": [],
        "word_feedback": _wf(cursor, _C1_OVR), "mistakes": mistakes,
    }


_C1_CHUNKS = [
    _c1(1,  0,  1, 0.05, True,  []),
    _c1(2,  1,  2, 0.10, False, []),
    _c1(3,  2,  2, 0.14, True,  []),
    _c1(4,  3,  3, 0.19, False, [_M1_VOWEL]),
    _c1(5,  4,  3, 0.24, True,  [_M1_VOWEL]),
    _c1(6,  5,  4, 0.29, False, [_M1_VOWEL]),
    _c1(7,  6,  4, 0.33, True,  [_M1_VOWEL]),
    _c1(8,  7,  5, 0.38, False, [_M1_VOWEL, _M1_LETTER]),
    _c1(9,  8,  5, 0.43, False, [_M1_VOWEL, _M1_LETTER]),
    _c1(10, 9,  5, 0.48, True,  [_M1_VOWEL, _M1_LETTER, _M1_DIAC]),
    _c1(11, 10, 6, 0.52, False, [_M1_VOWEL, _M1_LETTER, _M1_DIAC]),
    _c1(12, 11, 6, 0.57, False, [_M1_VOWEL, _M1_LETTER, _M1_DIAC]),
    _c1(13, 12, 6, 0.62, True,  [_M1_VOWEL, _M1_LETTER, _M1_DIAC]),
    _c1(14, 13, 7, 0.67, False, [_M1_VOWEL, _M1_LETTER, _M1_DIAC]),
    _c1(15, 14, 7, 0.71, False, [_M1_VOWEL, _M1_LETTER, _M1_DIAC]),
    _c1(16, 15, 7, 0.76, False, [_M1_VOWEL, _M1_LETTER, _M1_DIAC]),
    _c1(17, 16, 7, 0.81, True,  [_M1_VOWEL, _M1_LETTER, _M1_DIAC]),
    _c1(18, 17, 8, 0.86, False, [_M1_VOWEL, _M1_LETTER, _M1_DIAC]),
    _c1(19, 18, 8, 0.90, False, _C1_ALL),
    _c1(20, 19, 8, 0.95, False, _C1_ALL),
    _c1(21, 20, 8, 1.00, True,  _C1_ALL),
]

_C1_LM, _C1_WM = _split_mistakes(_C1_ALL)

_C1_SUMMARY = {
    "type": "session_summary", "verse_id": "55:1-8",
    "total_chunks": 21, "duration_seconds": 40,
    "full_transcription": _c1_tx(20),
    "total_words": 21, "words_correct": 17,
    "words_diacritic_error": 1, "words_vowel_error": 1,
    "words_letter_error": 1, "words_incorrect": 1, "words_not_recited": 0,
    "total_score": 72, "completion_percentage": 100,
    "skipped_ayahs": [], "repeated_ayahs": [],
    "skip_detail": [], "repetition_detail": [],
    "ayah_scores": [
        {"ayah": 1, "score": 100, "words_correct": 1, "words_errors": 0},
        {"ayah": 2, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 3, "score": 50,  "words_correct": 1, "words_errors": 1,
         "note": "خَلَقَ — fatha on khā recited as kasra"},
        {"ayah": 4, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 5, "score": 67,  "words_correct": 2, "words_errors": 1,
         "note": "الشَّمْصُ — sīn substituted with ṣād; بِحُسْبَانٍ tanwīn dropped"},
        {"ayah": 6, "score": 100, "words_correct": 3, "words_errors": 0},
        {"ayah": 7, "score": 100, "words_correct": 4, "words_errors": 0},
        {"ayah": 8, "score": 75,  "words_correct": 3, "words_errors": 1,
         "note": "تَطْغَوْا — ending 'وا' dropped"},
    ],
    "letter_mistakes": _C1_LM,
    "word_mistakes":   _C1_WM,
    "mistakes":        _C1_ALL,
    "overall_feedback": (
        "4 mistakes found: vowel error on خَلَقَ (fatha→kasra); "
        "سِين→صَاد substitution in الشَّمْصُ; tanwīn missing from بِحُسْبَانٍ; "
        "and تَطْغَوْا recited incorrectly. Review these words carefully."
    ),
    "recording": _recording(1, 40),
}


# ─────────────────────────────────────────────────────────────────────────────
# Case 2 – Repeat Ayah 1 + diacritic error + vowel error
#
# Mistakes (beyond repetition):
#   Word  6  (الْبَيَانَ) – diacritic_error: sukūn on لْ dropped → "الَبَيَانَ"
#   Word 10  (وَالنَّجْمُ) – vowel_error:    damma on م → kasra   → "وَالنَّجْمِ"
# ─────────────────────────────────────────────────────────────────────────────

_C2_STATUS = {
    "type": "status", "verse_id": "55:1-8",
    "message": "Session started. Ready to receive audio.",
    "total_words": 21, "total_ayahs": 8,
}

_C2_ERR = {6: "الَبَيَانَ", 10: "وَالنَّجْمِ"}

_C2_OVR = {
    6:  ("diacritic_error", _C2_ERR[6],  _LF_W6_DIAC),
    10: ("vowel_error",     _C2_ERR[10], _LF_W10_VOWEL),
}

_C2_REP_DETAIL = [{
    "ayah": 1,
    "first_occurrence_chunk": 1,
    "repeat_chunk": 2,
    "recited_text": "الرحمن",
    "note": "Ayah 1 recited again from the beginning",
}]

_M2_DIAC = {
    "word_id": "55:4:2", "word_text": "الْبَيَانَ", "word_position": 6,
    "type": "diacritic_error", "recited_text": _C2_ERR[6],
    "details": "Sukūn (ْ) missing from lam — الْبَيَانَ recited as الَبَيَانَ",
    "letter_feedback": _LF_W6_DIAC,
}
_M2_VOWEL = {
    "word_id": "55:6:1", "word_text": "وَالنَّجْمُ", "word_position": 10,
    "type": "vowel_error", "recited_text": _C2_ERR[10],
    "details": "Damma (ُ) on mīm recited as kasra (ِ) — short vowel confusion",
    "letter_feedback": _LF_W10_VOWEL,
}

_C2_ALL = [_M2_DIAC, _M2_VOWEL]

_C2_W0 = WORDS[0]["text"]
_C2_PREFIX = _C2_W0 + " " + _C2_W0


def _c2_tx(cursor: int) -> str:
    if cursor == 0:
        return _C2_PREFIX
    return _C2_PREFIX + " " + " ".join(
        _C2_ERR.get(i, WORDS[i]["text"]) for i in range(1, cursor + 1)
    )


def _c2_prog(ci, cursor, ayah, pos, complete, mistakes):
    return {
        "type": "feedback", "chunk_index": ci,
        "transcribed_text": _c2_tx(cursor),
        "current_ayah": ayah, "word_cursor": cursor,
        "position_in_verse": pos, "ayah_complete": complete,
        "skipped_ayahs": [], "repeated_ayahs": [1],
        "repetition_detail": _C2_REP_DETAIL,
        "word_feedback": _wf(cursor, _C2_OVR),
        "mistakes": mistakes,
    }


_C2_CHUNKS = [
    {
        "type": "feedback", "chunk_index": 1,
        "transcribed_text": _txt([0]), "current_ayah": 1,
        "word_cursor": 0, "position_in_verse": 0.05, "ayah_complete": True,
        "skipped_ayahs": [], "repeated_ayahs": [], "repetition_detail": [],
        "word_feedback": _wf(0), "mistakes": [],
    },
    {
        "type": "feedback", "chunk_index": 2,
        "transcribed_text": _C2_PREFIX, "current_ayah": 1,
        "word_cursor": 0, "position_in_verse": 0.05, "ayah_complete": False,
        "skipped_ayahs": [], "repeated_ayahs": [1],
        "repetition_detail": _C2_REP_DETAIL,
        "word_feedback": _wf(0), "mistakes": [],
    },
    _c2_prog(3,  1,  2, 0.10, False, []),
    _c2_prog(4,  2,  2, 0.14, True,  []),
    _c2_prog(5,  3,  3, 0.19, False, []),
    _c2_prog(6,  4,  3, 0.24, True,  []),
    _c2_prog(7,  5,  4, 0.29, False, []),
    _c2_prog(8,  6,  4, 0.33, True,  [_M2_DIAC]),
    _c2_prog(9,  7,  5, 0.38, False, [_M2_DIAC]),
    _c2_prog(10, 8,  5, 0.43, False, [_M2_DIAC]),
    _c2_prog(11, 9,  5, 0.48, True,  [_M2_DIAC]),
    _c2_prog(12, 10, 6, 0.52, False, _C2_ALL),
    _c2_prog(13, 11, 6, 0.57, False, _C2_ALL),
    _c2_prog(14, 12, 6, 0.62, True,  _C2_ALL),
    _c2_prog(15, 13, 7, 0.67, False, _C2_ALL),
    _c2_prog(16, 14, 7, 0.71, False, _C2_ALL),
    _c2_prog(17, 15, 7, 0.76, False, _C2_ALL),
    _c2_prog(18, 16, 7, 0.81, True,  _C2_ALL),
    _c2_prog(19, 17, 8, 0.86, False, _C2_ALL),
    _c2_prog(20, 18, 8, 0.90, False, _C2_ALL),
    _c2_prog(21, 20, 8, 1.00, True,  _C2_ALL),
]

_C2_LM, _C2_WM = _split_mistakes(_C2_ALL)

_C2_SUMMARY = {
    "type": "session_summary", "verse_id": "55:1-8",
    "total_chunks": 21, "duration_seconds": 42,
    "full_transcription": _c2_tx(20),
    "total_words": 21, "words_correct": 19,
    "words_diacritic_error": 1, "words_vowel_error": 1,
    "words_letter_error": 0, "words_incorrect": 0, "words_not_recited": 0,
    "total_score": 85, "completion_percentage": 100,
    "skipped_ayahs": [], "repeated_ayahs": [1],
    "skip_detail": [], "repetition_detail": _C2_REP_DETAIL,
    "ayah_scores": [
        {"ayah": 1, "score": 100, "words_correct": 1, "words_errors": 0,
         "note": "Ayah 1 repeated once"},
        {"ayah": 2, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 3, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 4, "score": 80,  "words_correct": 1, "words_errors": 1,
         "note": "الْبَيَانَ — sukūn on lam dropped"},
        {"ayah": 5, "score": 100, "words_correct": 3, "words_errors": 0},
        {"ayah": 6, "score": 80,  "words_correct": 2, "words_errors": 1,
         "note": "وَالنَّجْمُ — damma on mīm recited as kasra"},
        {"ayah": 7, "score": 100, "words_correct": 4, "words_errors": 0},
        {"ayah": 8, "score": 100, "words_correct": 4, "words_errors": 0},
    ],
    "letter_mistakes": _C2_LM,
    "word_mistakes":   _C2_WM,
    "mistakes":        _C2_ALL,
    "overall_feedback": (
        "Good recitation! Ayah 1 was repeated once. "
        "2 mistakes: sukūn dropped from الْبَيَانَ and damma→kasra on وَالنَّجْمُ. "
        "Focus on junction diacritics and final vowels."
    ),
    "recording": _recording(2, 42),
}


# ─────────────────────────────────────────────────────────────────────────────
# Case 3 – Skip Ayah 2 + diacritic error + letter error
#
# Mistakes (beyond skip):
#   Word  8  (وَالْقَمَرُ) – diacritic_error: damma on رُ dropped → "وَالْقَمَر"
#   Word 14  (رَفَعَهَا)   – letter_error:    ف (pos 2) → ق      → "رَقَعَهَا"
# ─────────────────────────────────────────────────────────────────────────────

_C3_STATUS = {
    "type": "status", "verse_id": "55:1-8",
    "message": "Session started. Ready to receive audio.",
    "total_words": 21, "total_ayahs": 8,
}

_C3_SKIP_DETAIL = [{
    "ayah": 2,
    "skipped_words": [
        {"word_id": "55:2:1", "word_text": "عَلَّمَ"},
        {"word_id": "55:2:2", "word_text": "الْقُرْآنَ"},
    ],
    "detected_at_chunk": 2,
    "note": "Jump detected from ayah 1 directly to ayah 3",
}]

_C3_SKIP_POS = {1, 2}

_C3_ERR = {8: "وَالْقَمَر", 14: "رَقَعَهَا"}

_C3_OVR = {
    8:  ("diacritic_error", _C3_ERR[8],  _LF_W8_DIAC),
    14: ("letter_error",    _C3_ERR[14], _LF_W14_LETTER),
}

_M3_DIAC = {
    "word_id": "55:5:2", "word_text": "وَالْقَمَرُ", "word_position": 8,
    "type": "diacritic_error", "recited_text": _C3_ERR[8],
    "details": "Damma (ُ) missing from rā — وَالْقَمَرُ recited without final vowel",
    "letter_feedback": _LF_W8_DIAC,
}
_M3_LETTER = {
    "word_id": "55:7:2", "word_text": "رَفَعَهَا", "word_position": 14,
    "type": "letter_error", "recited_text": _C3_ERR[14],
    "details": "فَاء (ف) recited as قَاف (ق) — labial/uvular confusion",
    "letter_feedback": _LF_W14_LETTER,
}

_C3_ALL = [_M3_DIAC, _M3_LETTER]


def _c3_tx(cursor: int) -> str:
    indices = [i for i in range(cursor + 1) if i not in _C3_SKIP_POS]
    return " ".join(_C3_ERR.get(i, WORDS[i]["text"]) for i in indices)


def _c3_prog(ci, cursor, ayah, pos, complete, mistakes):
    return {
        "type": "feedback", "chunk_index": ci,
        "transcribed_text": _c3_tx(cursor),
        "current_ayah": ayah, "word_cursor": cursor,
        "position_in_verse": pos, "ayah_complete": complete,
        "skipped_ayahs": [2], "skip_detail": _C3_SKIP_DETAIL,
        "repeated_ayahs": [],
        "word_feedback": _wf(cursor, _C3_OVR, skipped=_C3_SKIP_POS),
        "mistakes": mistakes,
    }


_C3_CHUNKS = [
    {
        "type": "feedback", "chunk_index": 1,
        "transcribed_text": _txt([0]), "current_ayah": 1,
        "word_cursor": 0, "position_in_verse": 0.05, "ayah_complete": True,
        "skipped_ayahs": [], "skip_detail": [], "repeated_ayahs": [],
        "word_feedback": _wf(0), "mistakes": [],
    },
    {
        "type": "feedback", "chunk_index": 2,
        "transcribed_text": _txt([0, 3]), "current_ayah": 3,
        "word_cursor": 3, "position_in_verse": 0.19, "ayah_complete": False,
        "skipped_ayahs": [2], "skip_detail": _C3_SKIP_DETAIL, "repeated_ayahs": [],
        "word_feedback": _wf(3, _C3_OVR, skipped=_C3_SKIP_POS), "mistakes": [],
    },
    {
        "type": "feedback", "chunk_index": 3,
        "transcribed_text": _txt([0, 3, 4]), "current_ayah": 3,
        "word_cursor": 4, "position_in_verse": 0.24, "ayah_complete": True,
        "skipped_ayahs": [2], "skip_detail": _C3_SKIP_DETAIL, "repeated_ayahs": [],
        "word_feedback": _wf(4, _C3_OVR, skipped=_C3_SKIP_POS), "mistakes": [],
    },
    _c3_prog(4,  5,  4, 0.29, False, []),
    _c3_prog(5,  6,  4, 0.33, True,  []),
    _c3_prog(6,  7,  5, 0.38, False, []),
    _c3_prog(7,  8,  5, 0.43, False, [_M3_DIAC]),
    _c3_prog(8,  9,  5, 0.48, True,  [_M3_DIAC]),
    _c3_prog(9,  10, 6, 0.52, False, [_M3_DIAC]),
    _c3_prog(10, 11, 6, 0.57, False, [_M3_DIAC]),
    _c3_prog(11, 12, 6, 0.62, True,  [_M3_DIAC]),
    _c3_prog(12, 13, 7, 0.67, False, [_M3_DIAC]),
    _c3_prog(13, 14, 7, 0.71, False, _C3_ALL),
    _c3_prog(14, 15, 7, 0.76, False, _C3_ALL),
    _c3_prog(15, 16, 7, 0.81, True,  _C3_ALL),
    _c3_prog(16, 17, 8, 0.86, False, _C3_ALL),
    _c3_prog(17, 18, 8, 0.90, False, _C3_ALL),
    _c3_prog(18, 19, 8, 0.95, False, _C3_ALL),
    _c3_prog(19, 20, 8, 1.00, True,  _C3_ALL),
]

_C3_LM, _C3_WM = _split_mistakes(_C3_ALL)

_C3_SUMMARY = {
    "type": "session_summary", "verse_id": "55:1-8",
    "total_chunks": 19, "duration_seconds": 38,
    "full_transcription": _c3_tx(20),
    "total_words": 21, "words_correct": 17,
    "words_diacritic_error": 1, "words_vowel_error": 0,
    "words_letter_error": 1, "words_incorrect": 0, "words_not_recited": 2,
    "total_score": 65, "completion_percentage": 90,
    "skipped_ayahs": [2], "repeated_ayahs": [],
    "skip_detail": _C3_SKIP_DETAIL, "repetition_detail": [],
    "ayah_scores": [
        {"ayah": 1, "score": 100, "words_correct": 1, "words_errors": 0},
        {"ayah": 2, "score": 0,   "words_correct": 0, "words_errors": 0,
         "note": "Skipped entirely"},
        {"ayah": 3, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 4, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 5, "score": 67,  "words_correct": 2, "words_errors": 1,
         "note": "وَالْقَمَرُ — damma on rā dropped"},
        {"ayah": 6, "score": 100, "words_correct": 3, "words_errors": 0},
        {"ayah": 7, "score": 75,  "words_correct": 3, "words_errors": 1,
         "note": "رَفَعَهَا — fā recited as qāf"},
        {"ayah": 8, "score": 100, "words_correct": 4, "words_errors": 0},
    ],
    "letter_mistakes": _C3_LM,
    "word_mistakes":   _C3_WM,
    "mistakes":        _C3_ALL,
    "overall_feedback": (
        "Ayah 2 (عَلَّمَ الْقُرْآنَ) was skipped. "
        "2 additional mistakes: damma dropped from وَالْقَمَرُ and "
        "فَاء substituted with قَاف in رَفَعَهَا. "
        "Memorise ayah 2 and review these letter/diacritic errors."
    ),
    "recording": _recording(3, 38),
}


# ─────────────────────────────────────────────────────────────────────────────
# Case 4 – Heavy harakat + letter error + incorrect word  (7 mistakes)
#
# Mistakes:
#   Word  0  (الرَّحْمَٰنُ) – letter_error:     ح (pos 4) → خ         → "الرَّخْمَٰنُ"
#   Word  1  (عَلَّمَ)      – diacritic_error:  shadda on ل missing    → "عَلَمَ"
#   Word  5  (عَلَّمَهُ)    – diacritic_error:  damma on ه missing     → "عَلَّمَه"
#   Word 12  (يَسْجُدَانِ)  – diacritic_error:  kasra on ن → fatha     → "يَسْجُدَانَ"
#   Word 14  (رَفَعَهَا)    – vowel_error:       fatha→damma + fatha→kasra → "رُفِعَهَا"
#   Word 16  (الْمِيزَانَ)  – vowel_error:       kasra on م → fatha    → "الْمَيزَانَ"
#   Word 18  (تَطْغَوْا)    – incorrect:         ending dropped        → "تطغو"
# ─────────────────────────────────────────────────────────────────────────────

_C4_STATUS = {
    "type": "status", "verse_id": "55:1-8",
    "message": "Session started. Ready to receive audio.",
    "total_words": 21, "total_ayahs": 8,
}

_C4_ERR = {
    0:  "الرَّخْمَٰنُ",
    1:  "عَلَمَ",
    5:  "عَلَّمَه",
    12: "يَسْجُدَانَ",
    14: "رُفِعَهَا",
    16: "الْمَيزَانَ",
    18: "تطغو",
}

_C4_OVR = {
    0:  ("letter_error",    _C4_ERR[0],  _LF_W0_LETTER),
    1:  ("diacritic_error", _C4_ERR[1],  _LF_W1_DIAC),
    5:  ("diacritic_error", _C4_ERR[5],  _LF_W5_DIAC),
    12: ("diacritic_error", _C4_ERR[12], _LF_W12_DIAC),
    14: ("vowel_error",     _C4_ERR[14], _LF_W14_VOWEL),
    16: ("vowel_error",     _C4_ERR[16], _LF_W16_VOWEL),
    18: ("incorrect",       _C4_ERR[18], None),
}

_M4_LETTER = {
    "word_id": "55:1:1", "word_text": "الرَّحْمَٰنُ", "word_position": 0,
    "type": "letter_error", "recited_text": _C4_ERR[0],
    "details": "حَاء (ح) recited as خَاء (خ) — pharyngeal/velar confusion",
    "letter_feedback": _LF_W0_LETTER,
}
_M4_DIAC1 = {
    "word_id": "55:2:1", "word_text": "عَلَّمَ", "word_position": 1,
    "type": "diacritic_error", "recited_text": _C4_ERR[1],
    "details": "Shadda (ّ) missing on lam — عَلَّمَ shortened to عَلَمَ",
    "letter_feedback": _LF_W1_DIAC,
}
_M4_DIAC2 = {
    "word_id": "55:4:1", "word_text": "عَلَّمَهُ", "word_position": 5,
    "type": "diacritic_error", "recited_text": _C4_ERR[5],
    "details": "Damma (ُ) missing on hā — word ends without final vowel",
    "letter_feedback": _LF_W5_DIAC,
}
_M4_DIAC3 = {
    "word_id": "55:6:3", "word_text": "يَسْجُدَانِ", "word_position": 12,
    "type": "diacritic_error", "recited_text": _C4_ERR[12],
    "details": "Kasra (ِ) on nūn recited as fatha (َ) — ending changed",
    "letter_feedback": _LF_W12_DIAC,
}
_M4_VOWEL1 = {
    "word_id": "55:7:2", "word_text": "رَفَعَهَا", "word_position": 14,
    "type": "vowel_error", "recited_text": _C4_ERR[14],
    "details": "Fatha (َ) on rā→damma (ُ); fatha on fā→kasra (ِ) — double vowel error",
    "letter_feedback": _LF_W14_VOWEL,
}
_M4_VOWEL2 = {
    "word_id": "55:7:4", "word_text": "الْمِيزَانَ", "word_position": 16,
    "type": "vowel_error", "recited_text": _C4_ERR[16],
    "details": "Kasra (ِ) on mīm recited as fatha (َ) — vowel of mīm changed",
    "letter_feedback": _LF_W16_VOWEL,
}
_M4_INCR = {
    "word_id": "55:8:2", "word_text": "تَطْغَوْا", "word_position": 18,
    "type": "incorrect", "recited_text": _C4_ERR[18],
    "details": "Ending 'وا' dropped — تَطْغَوْا recited as تطغو",
}

_C4_ALL = [_M4_LETTER, _M4_DIAC1, _M4_DIAC2, _M4_DIAC3, _M4_VOWEL1, _M4_VOWEL2, _M4_INCR]


def _c4_tx(cursor: int) -> str:
    return " ".join(_C4_ERR.get(i, WORDS[i]["text"]) for i in range(cursor + 1))


def _c4(ci, cursor, ayah, pos, complete, mistakes):
    return {
        "type": "feedback", "chunk_index": ci,
        "transcribed_text": _c4_tx(cursor),
        "current_ayah": ayah, "word_cursor": cursor,
        "position_in_verse": pos, "ayah_complete": complete,
        "skipped_ayahs": [], "repeated_ayahs": [],
        "word_feedback": _wf(cursor, _C4_OVR), "mistakes": mistakes,
    }


_C4_CHUNKS = [
    _c4(1,  0,  1, 0.05, True,  [_M4_LETTER]),
    _c4(2,  1,  2, 0.10, False, [_M4_LETTER, _M4_DIAC1]),
    _c4(3,  2,  2, 0.14, True,  [_M4_LETTER, _M4_DIAC1]),
    _c4(4,  3,  3, 0.19, False, [_M4_LETTER, _M4_DIAC1]),
    _c4(5,  4,  3, 0.24, True,  [_M4_LETTER, _M4_DIAC1]),
    _c4(6,  5,  4, 0.29, False, [_M4_LETTER, _M4_DIAC1, _M4_DIAC2]),
    _c4(7,  6,  4, 0.33, True,  [_M4_LETTER, _M4_DIAC1, _M4_DIAC2]),
    _c4(8,  7,  5, 0.38, False, [_M4_LETTER, _M4_DIAC1, _M4_DIAC2]),
    _c4(9,  8,  5, 0.43, False, [_M4_LETTER, _M4_DIAC1, _M4_DIAC2]),
    _c4(10, 9,  5, 0.48, True,  [_M4_LETTER, _M4_DIAC1, _M4_DIAC2]),
    _c4(11, 10, 6, 0.52, False, [_M4_LETTER, _M4_DIAC1, _M4_DIAC2]),
    _c4(12, 11, 6, 0.57, False, [_M4_LETTER, _M4_DIAC1, _M4_DIAC2]),
    _c4(13, 12, 6, 0.62, True,  [_M4_LETTER, _M4_DIAC1, _M4_DIAC2, _M4_DIAC3]),
    _c4(14, 13, 7, 0.67, False, [_M4_LETTER, _M4_DIAC1, _M4_DIAC2, _M4_DIAC3]),
    _c4(15, 14, 7, 0.71, False, [_M4_LETTER, _M4_DIAC1, _M4_DIAC2, _M4_DIAC3, _M4_VOWEL1]),
    _c4(16, 15, 7, 0.76, False, [_M4_LETTER, _M4_DIAC1, _M4_DIAC2, _M4_DIAC3, _M4_VOWEL1]),
    _c4(17, 16, 7, 0.81, True,  [_M4_LETTER, _M4_DIAC1, _M4_DIAC2, _M4_DIAC3, _M4_VOWEL1, _M4_VOWEL2]),
    _c4(18, 17, 8, 0.86, False, [_M4_LETTER, _M4_DIAC1, _M4_DIAC2, _M4_DIAC3, _M4_VOWEL1, _M4_VOWEL2]),
    _c4(19, 18, 8, 0.90, False, _C4_ALL),
    _c4(20, 19, 8, 0.95, False, _C4_ALL),
    _c4(21, 20, 8, 1.00, True,  _C4_ALL),
]

_C4_LM, _C4_WM = _split_mistakes(_C4_ALL)

_C4_SUMMARY = {
    "type": "session_summary", "verse_id": "55:1-8",
    "total_chunks": 21, "duration_seconds": 40,
    "full_transcription": _c4_tx(20),
    "total_words": 21, "words_correct": 14,
    "words_diacritic_error": 3, "words_vowel_error": 2,
    "words_letter_error": 1, "words_incorrect": 1, "words_not_recited": 0,
    "total_score": 62, "completion_percentage": 100,
    "skipped_ayahs": [], "repeated_ayahs": [],
    "skip_detail": [], "repetition_detail": [],
    "ayah_scores": [
        {"ayah": 1, "score": 50,  "words_correct": 0, "words_errors": 1,
         "note": "الرَّحْمَٰنُ — ح recited as خ"},
        {"ayah": 2, "score": 50,  "words_correct": 1, "words_errors": 1,
         "note": "عَلَّمَ — shadda on lam missing"},
        {"ayah": 3, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 4, "score": 50,  "words_correct": 1, "words_errors": 1,
         "note": "عَلَّمَهُ — damma on hā missing"},
        {"ayah": 5, "score": 100, "words_correct": 3, "words_errors": 0},
        {"ayah": 6, "score": 67,  "words_correct": 2, "words_errors": 1,
         "note": "يَسْجُدَانِ — kasra on nūn changed to fatha"},
        {"ayah": 7, "score": 50,  "words_correct": 2, "words_errors": 2,
         "note": "رَفَعَهَا and الْمِيزَانَ have wrong vowels"},
        {"ayah": 8, "score": 75,  "words_correct": 3, "words_errors": 1,
         "note": "تَطْغَوْا — ending dropped"},
    ],
    "letter_mistakes": _C4_LM,
    "word_mistakes":   _C4_WM,
    "mistakes":        _C4_ALL,
    "overall_feedback": (
        "7 mistakes: ح→خ in الرَّحْمَٰنُ (letter); "
        "shadda missing in عَلَّمَ; damma missing in عَلَّمَهُ; "
        "kasra→fatha in يَسْجُدَانِ (3 diacritic errors); "
        "double vowel error in رَفَعَهَا; kasra→fatha in الْمِيزَانَ (2 vowel errors); "
        "and تَطْغَوْا recited incorrectly. Significant harakat work needed."
    ),
    "recording": _recording(4, 40),
}


# ─────────────────────────────────────────────────────────────────────────────
# Case 5 – Letter mistakes + diacritic + incorrect  (6 mistakes)
#
# Mistakes:
#   Word  1  (عَلَّمَ)      – diacritic_error: shadda on ل missing    → "عَلَمَ"
#   Word  3  (خَلَقَ)       – letter_error:    خ (pos 0) → ح          → "حَلَقَ"
#   Word  8  (وَالْقَمَرُ)  – letter_error:    ق (pos 5) → غ          → "وَالْغَمَرُ"
#   Word 10  (وَالنَّجْمُ)  – vowel_error:     damma on م → kasra     → "وَالنَّجْمِ"
#   Word 15  (وَوَضَعَ)     – vowel_error:     fatha on ض → kasra     → "وَوَضِعَ"
#   Word 17  (أَلَّا)       – incorrect:       hamza dropped          → "اللا"
# ─────────────────────────────────────────────────────────────────────────────

_C5_STATUS = {
    "type": "status", "verse_id": "55:1-8",
    "message": "Session started. Ready to receive audio.",
    "total_words": 21, "total_ayahs": 8,
}

_C5_ERR = {
    1:  "عَلَمَ",
    3:  "حَلَقَ",
    8:  "وَالْغَمَرُ",
    10: "وَالنَّجْمِ",
    15: "وَوَضِعَ",
    17: "اللا",
}

_C5_OVR = {
    1:  ("diacritic_error", _C5_ERR[1],  _LF_W1_DIAC),
    3:  ("letter_error",    _C5_ERR[3],  _LF_W3_LETTER),
    8:  ("letter_error",    _C5_ERR[8],  _LF_W8_LETTER),
    10: ("vowel_error",     _C5_ERR[10], _LF_W10_VOWEL),
    15: ("vowel_error",     _C5_ERR[15], _LF_W15_VOWEL),
    17: ("incorrect",       _C5_ERR[17], None),
}

_M5_DIAC = {
    "word_id": "55:2:1", "word_text": "عَلَّمَ", "word_position": 1,
    "type": "diacritic_error", "recited_text": _C5_ERR[1],
    "details": "Shadda (ّ) missing on lam — عَلَّمَ shortened to عَلَمَ",
    "letter_feedback": _LF_W1_DIAC,
}
_M5_LETTER1 = {
    "word_id": "55:3:1", "word_text": "خَلَقَ", "word_position": 3,
    "type": "letter_error", "recited_text": _C5_ERR[3],
    "details": "خَاء (خ) recited as حَاء (ح) — velar fricative vs pharyngeal",
    "letter_feedback": _LF_W3_LETTER,
}
_M5_LETTER2 = {
    "word_id": "55:5:2", "word_text": "وَالْقَمَرُ", "word_position": 8,
    "type": "letter_error", "recited_text": _C5_ERR[8],
    "details": "قَاف (ق) recited as غَيْن (غ) — uvular stop vs voiced velar fricative",
    "letter_feedback": _LF_W8_LETTER,
}
_M5_VOWEL1 = {
    "word_id": "55:6:1", "word_text": "وَالنَّجْمُ", "word_position": 10,
    "type": "vowel_error", "recited_text": _C5_ERR[10],
    "details": "Damma (ُ) on mīm recited as kasra (ِ) — vowel harmony error",
    "letter_feedback": _LF_W10_VOWEL,
}
_M5_VOWEL2 = {
    "word_id": "55:7:3", "word_text": "وَوَضَعَ", "word_position": 15,
    "type": "vowel_error", "recited_text": _C5_ERR[15],
    "details": "Fatha (َ) on ḍād recited as kasra (ِ) — vowel of ḍād changed",
    "letter_feedback": _LF_W15_VOWEL,
}
_M5_INCR = {
    "word_id": "55:8:1", "word_text": "أَلَّا", "word_position": 17,
    "type": "incorrect", "recited_text": _C5_ERR[17],
    "details": "Hamza dropped — أَلَّا recited as اللا",
}

_C5_ALL = [_M5_DIAC, _M5_LETTER1, _M5_LETTER2, _M5_VOWEL1, _M5_VOWEL2, _M5_INCR]


def _c5_tx(cursor: int) -> str:
    return " ".join(_C5_ERR.get(i, WORDS[i]["text"]) for i in range(cursor + 1))


def _c5(ci, cursor, ayah, pos, complete, mistakes):
    return {
        "type": "feedback", "chunk_index": ci,
        "transcribed_text": _c5_tx(cursor),
        "current_ayah": ayah, "word_cursor": cursor,
        "position_in_verse": pos, "ayah_complete": complete,
        "skipped_ayahs": [], "repeated_ayahs": [],
        "word_feedback": _wf(cursor, _C5_OVR), "mistakes": mistakes,
    }


_C5_CHUNKS = [
    _c5(1,  0,  1, 0.05, True,  []),
    _c5(2,  1,  2, 0.10, False, [_M5_DIAC]),
    _c5(3,  2,  2, 0.14, True,  [_M5_DIAC]),
    _c5(4,  3,  3, 0.19, False, [_M5_DIAC, _M5_LETTER1]),
    _c5(5,  4,  3, 0.24, True,  [_M5_DIAC, _M5_LETTER1]),
    _c5(6,  5,  4, 0.29, False, [_M5_DIAC, _M5_LETTER1]),
    _c5(7,  6,  4, 0.33, True,  [_M5_DIAC, _M5_LETTER1]),
    _c5(8,  7,  5, 0.38, False, [_M5_DIAC, _M5_LETTER1]),
    _c5(9,  8,  5, 0.43, False, [_M5_DIAC, _M5_LETTER1, _M5_LETTER2]),
    _c5(10, 9,  5, 0.48, True,  [_M5_DIAC, _M5_LETTER1, _M5_LETTER2]),
    _c5(11, 10, 6, 0.52, False, [_M5_DIAC, _M5_LETTER1, _M5_LETTER2, _M5_VOWEL1]),
    _c5(12, 11, 6, 0.57, False, [_M5_DIAC, _M5_LETTER1, _M5_LETTER2, _M5_VOWEL1]),
    _c5(13, 12, 6, 0.62, True,  [_M5_DIAC, _M5_LETTER1, _M5_LETTER2, _M5_VOWEL1]),
    _c5(14, 13, 7, 0.67, False, [_M5_DIAC, _M5_LETTER1, _M5_LETTER2, _M5_VOWEL1]),
    _c5(15, 14, 7, 0.71, False, [_M5_DIAC, _M5_LETTER1, _M5_LETTER2, _M5_VOWEL1]),
    _c5(16, 15, 7, 0.76, False, [_M5_DIAC, _M5_LETTER1, _M5_LETTER2, _M5_VOWEL1, _M5_VOWEL2]),
    _c5(17, 16, 7, 0.81, True,  [_M5_DIAC, _M5_LETTER1, _M5_LETTER2, _M5_VOWEL1, _M5_VOWEL2]),
    _c5(18, 17, 8, 0.86, False, _C5_ALL),
    _c5(19, 18, 8, 0.90, False, _C5_ALL),
    _c5(20, 19, 8, 0.95, False, _C5_ALL),
    _c5(21, 20, 8, 1.00, True,  _C5_ALL),
]

_C5_LM, _C5_WM = _split_mistakes(_C5_ALL)

_C5_SUMMARY = {
    "type": "session_summary", "verse_id": "55:1-8",
    "total_chunks": 21, "duration_seconds": 40,
    "full_transcription": _c5_tx(20),
    "total_words": 21, "words_correct": 15,
    "words_diacritic_error": 1, "words_vowel_error": 2,
    "words_letter_error": 2, "words_incorrect": 1, "words_not_recited": 0,
    "total_score": 58, "completion_percentage": 100,
    "skipped_ayahs": [], "repeated_ayahs": [],
    "skip_detail": [], "repetition_detail": [],
    "ayah_scores": [
        {"ayah": 1, "score": 100, "words_correct": 1, "words_errors": 0},
        {"ayah": 2, "score": 50,  "words_correct": 1, "words_errors": 1,
         "note": "عَلَّمَ — shadda missing"},
        {"ayah": 3, "score": 50,  "words_correct": 1, "words_errors": 1,
         "note": "خَلَقَ — khā recited as ḥā"},
        {"ayah": 4, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 5, "score": 67,  "words_correct": 2, "words_errors": 1,
         "note": "وَالْقَمَرُ — qāf recited as ghain"},
        {"ayah": 6, "score": 67,  "words_correct": 2, "words_errors": 1,
         "note": "وَالنَّجْمُ — damma on mīm recited as kasra"},
        {"ayah": 7, "score": 75,  "words_correct": 3, "words_errors": 1,
         "note": "وَوَضَعَ — fatha on ḍād recited as kasra"},
        {"ayah": 8, "score": 75,  "words_correct": 3, "words_errors": 1,
         "note": "أَلَّا — hamza dropped"},
    ],
    "letter_mistakes": _C5_LM,
    "word_mistakes":   _C5_WM,
    "mistakes":        _C5_ALL,
    "overall_feedback": (
        "6 mistakes: shadda dropped from عَلَّمَ; "
        "خ→ح in خَلَقَ and ق→غ in وَالْقَمَرُ (2 letter errors); "
        "damma→kasra in وَالنَّجْمُ and fatha→kasra in وَوَضَعَ (2 vowel errors); "
        "and hamza dropped from أَلَّا. Focus on letter precision and nunation."
    ),
    "recording": _recording(5, 40),
}


# ─────────────────────────────────────────────────────────────────────────────
# Case 6 – Mixed moderate: 1 incorrect + 1 letter + 2 diacritic + 2 vowel  (6 mistakes)
#
# Mistakes:
#   Word  2  (الْقُرْآنَ)  – diacritic_error: sukūn on رْ dropped    → "الْقُرَآنَ"
#   Word  4  (الْإِنسَانَ) – incorrect:       truncated               → "الانس"
#   Word  7  (الشَّمْسُ)   – letter_error:    ش (pos 2) → ص          → "الصَّمْسُ"
#   Word 11  (وَالشَّجَرُ) – diacritic_error: shadda on شَّ dropped   → "وَالشَجَرُ"
#   Word 15  (وَوَضَعَ)    – vowel_error:     fatha on ض → kasra     → "وَوَضِعَ"
#   Word 17  (أَلَّا)      – vowel_error:     fatha on أ → kasra     → "إِلَّا"
# ─────────────────────────────────────────────────────────────────────────────

_C6_STATUS = {
    "type": "status", "verse_id": "55:1-8",
    "message": "Session started. Ready to receive audio.",
    "total_words": 21, "total_ayahs": 8,
}

_C6_ERR = {
    2:  "الْقُرَآنَ",
    4:  "الانس",
    7:  "الصَّمْسُ",
    11: "وَالشَجَرُ",
    15: "وَوَضِعَ",
    17: "إِلَّا",
}

_C6_OVR = {
    2:  ("diacritic_error", _C6_ERR[2],  _LF_W2_DIAC),
    4:  ("incorrect",       _C6_ERR[4],  None),
    7:  ("letter_error",    _C6_ERR[7],  _LF_W7_LETTER_C6),
    11: ("diacritic_error", _C6_ERR[11], _LF_W11_DIAC),
    15: ("vowel_error",     _C6_ERR[15], _LF_W15_VOWEL),
    17: ("vowel_error",     _C6_ERR[17], _LF_W17_VOWEL),
}

_M6_DIAC1 = {
    "word_id": "55:2:2", "word_text": "الْقُرْآنَ", "word_position": 2,
    "type": "diacritic_error", "recited_text": _C6_ERR[2],
    "details": "Sukūn (ْ) missing from rā — الْقُرْآنَ recited without sukūn on rā",
    "letter_feedback": _LF_W2_DIAC,
}
_M6_INCR = {
    "word_id": "55:3:2", "word_text": "الْإِنسَانَ", "word_position": 4,
    "type": "incorrect", "recited_text": _C6_ERR[4],
    "details": "Word truncated — 'الانس' recited instead of الْإِنسَانَ",
}
_M6_LETTER = {
    "word_id": "55:5:1", "word_text": "الشَّمْسُ", "word_position": 7,
    "type": "letter_error", "recited_text": _C6_ERR[7],
    "details": "شِين (ش) recited as صَاد (ص) — emphatic substitution at word start",
    "letter_feedback": _LF_W7_LETTER_C6,
}
_M6_DIAC2 = {
    "word_id": "55:6:2", "word_text": "وَالشَّجَرُ", "word_position": 11,
    "type": "diacritic_error", "recited_text": _C6_ERR[11],
    "details": "Shadda (ّ) missing on shin — وَالشَّجَرُ shortened to وَالشَجَرُ",
    "letter_feedback": _LF_W11_DIAC,
}
_M6_VOWEL1 = {
    "word_id": "55:7:3", "word_text": "وَوَضَعَ", "word_position": 15,
    "type": "vowel_error", "recited_text": _C6_ERR[15],
    "details": "Fatha (َ) on ḍād recited as kasra (ِ) — وَوَضَعَ became وَوَضِعَ",
    "letter_feedback": _LF_W15_VOWEL,
}
_M6_VOWEL2 = {
    "word_id": "55:8:1", "word_text": "أَلَّا", "word_position": 17,
    "type": "vowel_error", "recited_text": _C6_ERR[17],
    "details": "Fatha (َ) on hamza recited as kasra (ِ) — أَلَّا became إِلَّا",
    "letter_feedback": _LF_W17_VOWEL,
}

_C6_ALL = [_M6_DIAC1, _M6_INCR, _M6_LETTER, _M6_DIAC2, _M6_VOWEL1, _M6_VOWEL2]


def _c6_tx(cursor: int) -> str:
    return " ".join(_C6_ERR.get(i, WORDS[i]["text"]) for i in range(cursor + 1))


def _c6(ci, cursor, ayah, pos, complete, mistakes):
    return {
        "type": "feedback", "chunk_index": ci,
        "transcribed_text": _c6_tx(cursor),
        "current_ayah": ayah, "word_cursor": cursor,
        "position_in_verse": pos, "ayah_complete": complete,
        "skipped_ayahs": [], "repeated_ayahs": [],
        "word_feedback": _wf(cursor, _C6_OVR), "mistakes": mistakes,
    }


_C6_CHUNKS = [
    _c6(1,  0,  1, 0.05, True,  []),
    _c6(2,  1,  2, 0.10, False, []),
    _c6(3,  2,  2, 0.14, True,  [_M6_DIAC1]),
    _c6(4,  3,  3, 0.19, False, [_M6_DIAC1]),
    _c6(5,  4,  3, 0.24, True,  [_M6_DIAC1, _M6_INCR]),
    _c6(6,  5,  4, 0.29, False, [_M6_DIAC1, _M6_INCR]),
    _c6(7,  6,  4, 0.33, True,  [_M6_DIAC1, _M6_INCR]),
    _c6(8,  7,  5, 0.38, False, [_M6_DIAC1, _M6_INCR, _M6_LETTER]),
    _c6(9,  8,  5, 0.43, False, [_M6_DIAC1, _M6_INCR, _M6_LETTER]),
    _c6(10, 9,  5, 0.48, True,  [_M6_DIAC1, _M6_INCR, _M6_LETTER]),
    _c6(11, 10, 6, 0.52, False, [_M6_DIAC1, _M6_INCR, _M6_LETTER]),
    _c6(12, 11, 6, 0.57, False, [_M6_DIAC1, _M6_INCR, _M6_LETTER, _M6_DIAC2]),
    _c6(13, 12, 6, 0.62, True,  [_M6_DIAC1, _M6_INCR, _M6_LETTER, _M6_DIAC2]),
    _c6(14, 13, 7, 0.67, False, [_M6_DIAC1, _M6_INCR, _M6_LETTER, _M6_DIAC2]),
    _c6(15, 14, 7, 0.71, False, [_M6_DIAC1, _M6_INCR, _M6_LETTER, _M6_DIAC2]),
    _c6(16, 15, 7, 0.76, False, [_M6_DIAC1, _M6_INCR, _M6_LETTER, _M6_DIAC2, _M6_VOWEL1]),
    _c6(17, 16, 7, 0.81, True,  [_M6_DIAC1, _M6_INCR, _M6_LETTER, _M6_DIAC2, _M6_VOWEL1]),
    _c6(18, 17, 8, 0.86, False, _C6_ALL),
    _c6(19, 18, 8, 0.90, False, _C6_ALL),
    _c6(20, 19, 8, 0.95, False, _C6_ALL),
    _c6(21, 20, 8, 1.00, True,  _C6_ALL),
]

_C6_LM, _C6_WM = _split_mistakes(_C6_ALL)

_C6_SUMMARY = {
    "type": "session_summary", "verse_id": "55:1-8",
    "total_chunks": 21, "duration_seconds": 40,
    "full_transcription": _c6_tx(20),
    "total_words": 21, "words_correct": 15,
    "words_diacritic_error": 2, "words_vowel_error": 2,
    "words_letter_error": 1, "words_incorrect": 1, "words_not_recited": 0,
    "total_score": 65, "completion_percentage": 100,
    "skipped_ayahs": [], "repeated_ayahs": [],
    "skip_detail": [], "repetition_detail": [],
    "ayah_scores": [
        {"ayah": 1, "score": 100, "words_correct": 1, "words_errors": 0},
        {"ayah": 2, "score": 67,  "words_correct": 1, "words_errors": 1,
         "note": "الْقُرْآنَ — sukūn on rā dropped"},
        {"ayah": 3, "score": 50,  "words_correct": 1, "words_errors": 1,
         "note": "الْإِنسَانَ recited incorrectly as 'الانس'"},
        {"ayah": 4, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 5, "score": 67,  "words_correct": 2, "words_errors": 1,
         "note": "الشَّمْسُ — shin substituted with ṣād"},
        {"ayah": 6, "score": 67,  "words_correct": 2, "words_errors": 1,
         "note": "وَالشَّجَرُ — shadda on shin missing"},
        {"ayah": 7, "score": 75,  "words_correct": 3, "words_errors": 1,
         "note": "وَوَضَعَ — fatha on ḍād recited as kasra"},
        {"ayah": 8, "score": 75,  "words_correct": 3, "words_errors": 1,
         "note": "أَلَّا — fatha on hamza recited as kasra"},
    ],
    "letter_mistakes": _C6_LM,
    "word_mistakes":   _C6_WM,
    "mistakes":        _C6_ALL,
    "overall_feedback": (
        "6 mistakes across all categories: sukūn dropped from الْقُرْآنَ; "
        "الْإِنسَانَ recited incorrectly; shin→ṣād in الشَّمْسُ (letter); "
        "shadda missing from وَالشَّجَرُ; vowel errors on وَوَضَعَ and أَلَّا. "
        "Work on letter precision and diacritic consistency."
    ),
    "recording": _recording(6, 40),
}


# ─────────────────────────────────────────────────────────────────────────────
# Case 7 – Mixed heavy: 2 incorrect + 1 letter + 2 diacritic + 2 vowel  (7 mistakes)
#
# Mistakes:
#   Word  2  (الْقُرْآنَ)  – incorrect:       wrong form             → "القراء"
#   Word  3  (خَلَقَ)      – vowel_error:      fatha on ل → damma    → "خَلُقَ"
#   Word  6  (الْبَيَانَ)  – letter_error:     ب (pos 3) → ف         → "الْفَيَانَ"
#   Word  9  (بِحُسْبَانٍ) – diacritic_error:  tanwīn kasra dropped   → "بِحُسْبَانَ"
#   Word 12  (يَسْجُدَانِ) – diacritic_error:  sukūn on سْ dropped    → "يَسَجُدَانِ"
#   Word 16  (الْمِيزَانَ) – vowel_error:      kasra on م → damma    → "الْمُيزَانَ"
#   Word 18  (تَطْغَوْا)   – incorrect:        ending dropped         → "تطغو"
# ─────────────────────────────────────────────────────────────────────────────

_C7_STATUS = {
    "type": "status", "verse_id": "55:1-8",
    "message": "Session started. Ready to receive audio.",
    "total_words": 21, "total_ayahs": 8,
}

_C7_ERR = {
    2:  "القراء",
    3:  "خَلُقَ",
    6:  "الْفَيَانَ",
    9:  "بِحُسْبَانَ",
    12: "يَسَجُدَانِ",
    16: "الْمُيزَانَ",
    18: "تطغو",
}

_C7_OVR = {
    2:  ("incorrect",       _C7_ERR[2],  None),
    3:  ("vowel_error",     _C7_ERR[3],  _LF_W3_VOWEL_C7),
    6:  ("letter_error",    _C7_ERR[6],  _LF_W6_LETTER),
    9:  ("diacritic_error", _C7_ERR[9],  _LF_W9_DIAC),
    12: ("diacritic_error", _C7_ERR[12], _LF_W12_DIAC_C7),
    16: ("vowel_error",     _C7_ERR[16], _LF_W16_VOWEL_C7),
    18: ("incorrect",       _C7_ERR[18], None),
}

_M7_INCR1 = {
    "word_id": "55:2:2", "word_text": "الْقُرْآنَ", "word_position": 2,
    "type": "incorrect", "recited_text": _C7_ERR[2],
    "details": "الْقُرْآنَ recited as 'القراء' — wrong word form",
}
_M7_VOWEL1 = {
    "word_id": "55:3:1", "word_text": "خَلَقَ", "word_position": 3,
    "type": "vowel_error", "recited_text": _C7_ERR[3],
    "details": "Fatha (َ) on lam recited as damma (ُ) — خَلَقَ became خَلُقَ",
    "letter_feedback": _LF_W3_VOWEL_C7,
}
_M7_LETTER = {
    "word_id": "55:4:2", "word_text": "الْبَيَانَ", "word_position": 6,
    "type": "letter_error", "recited_text": _C7_ERR[6],
    "details": "بَاء (ب) recited as فَاء (ف) — bilabial/labiodental confusion",
    "letter_feedback": _LF_W6_LETTER,
}
_M7_DIAC1 = {
    "word_id": "55:5:3", "word_text": "بِحُسْبَانٍ", "word_position": 9,
    "type": "diacritic_error", "recited_text": _C7_ERR[9],
    "details": "Tanwīn kasra (ٍ) missing at end — nunation dropped entirely",
    "letter_feedback": _LF_W9_DIAC,
}
_M7_DIAC2 = {
    "word_id": "55:6:3", "word_text": "يَسْجُدَانِ", "word_position": 12,
    "type": "diacritic_error", "recited_text": _C7_ERR[12],
    "details": "Sukūn (ْ) missing on sīn — يَسْجُدَانِ gained extra syllable يَسَجُدَانِ",
    "letter_feedback": _LF_W12_DIAC_C7,
}
_M7_VOWEL2 = {
    "word_id": "55:7:4", "word_text": "الْمِيزَانَ", "word_position": 16,
    "type": "vowel_error", "recited_text": _C7_ERR[16],
    "details": "Kasra (ِ) on mīm recited as damma (ُ) — الْمِيزَانَ became الْمُيزَانَ",
    "letter_feedback": _LF_W16_VOWEL_C7,
}
_M7_INCR2 = {
    "word_id": "55:8:2", "word_text": "تَطْغَوْا", "word_position": 18,
    "type": "incorrect", "recited_text": _C7_ERR[18],
    "details": "Ending 'وا' dropped — تَطْغَوْا recited as تطغو",
}

_C7_ALL = [_M7_INCR1, _M7_VOWEL1, _M7_LETTER, _M7_DIAC1, _M7_DIAC2, _M7_VOWEL2, _M7_INCR2]


def _c7_tx(cursor: int) -> str:
    return " ".join(_C7_ERR.get(i, WORDS[i]["text"]) for i in range(cursor + 1))


def _c7(ci, cursor, ayah, pos, complete, mistakes):
    return {
        "type": "feedback", "chunk_index": ci,
        "transcribed_text": _c7_tx(cursor),
        "current_ayah": ayah, "word_cursor": cursor,
        "position_in_verse": pos, "ayah_complete": complete,
        "skipped_ayahs": [], "repeated_ayahs": [],
        "word_feedback": _wf(cursor, _C7_OVR), "mistakes": mistakes,
    }


_C7_CHUNKS = [
    _c7(1,  0,  1, 0.05, True,  []),
    _c7(2,  1,  2, 0.10, False, []),
    _c7(3,  2,  2, 0.14, True,  [_M7_INCR1]),
    _c7(4,  3,  3, 0.19, False, [_M7_INCR1, _M7_VOWEL1]),
    _c7(5,  4,  3, 0.24, True,  [_M7_INCR1, _M7_VOWEL1]),
    _c7(6,  5,  4, 0.29, False, [_M7_INCR1, _M7_VOWEL1]),
    _c7(7,  6,  4, 0.33, True,  [_M7_INCR1, _M7_VOWEL1, _M7_LETTER]),
    _c7(8,  7,  5, 0.38, False, [_M7_INCR1, _M7_VOWEL1, _M7_LETTER]),
    _c7(9,  8,  5, 0.43, False, [_M7_INCR1, _M7_VOWEL1, _M7_LETTER]),
    _c7(10, 9,  5, 0.48, True,  [_M7_INCR1, _M7_VOWEL1, _M7_LETTER, _M7_DIAC1]),
    _c7(11, 10, 6, 0.52, False, [_M7_INCR1, _M7_VOWEL1, _M7_LETTER, _M7_DIAC1]),
    _c7(12, 11, 6, 0.57, False, [_M7_INCR1, _M7_VOWEL1, _M7_LETTER, _M7_DIAC1]),
    _c7(13, 12, 6, 0.62, True,  [_M7_INCR1, _M7_VOWEL1, _M7_LETTER, _M7_DIAC1, _M7_DIAC2]),
    _c7(14, 13, 7, 0.67, False, [_M7_INCR1, _M7_VOWEL1, _M7_LETTER, _M7_DIAC1, _M7_DIAC2]),
    _c7(15, 14, 7, 0.71, False, [_M7_INCR1, _M7_VOWEL1, _M7_LETTER, _M7_DIAC1, _M7_DIAC2]),
    _c7(16, 15, 7, 0.76, False, [_M7_INCR1, _M7_VOWEL1, _M7_LETTER, _M7_DIAC1, _M7_DIAC2]),
    _c7(17, 16, 7, 0.81, True,  [_M7_INCR1, _M7_VOWEL1, _M7_LETTER, _M7_DIAC1, _M7_DIAC2, _M7_VOWEL2]),
    _c7(18, 17, 8, 0.86, False, [_M7_INCR1, _M7_VOWEL1, _M7_LETTER, _M7_DIAC1, _M7_DIAC2, _M7_VOWEL2]),
    _c7(19, 18, 8, 0.90, False, _C7_ALL),
    _c7(20, 19, 8, 0.95, False, _C7_ALL),
    _c7(21, 20, 8, 1.00, True,  _C7_ALL),
]

_C7_LM, _C7_WM = _split_mistakes(_C7_ALL)

_C7_SUMMARY = {
    "type": "session_summary", "verse_id": "55:1-8",
    "total_chunks": 21, "duration_seconds": 40,
    "full_transcription": _c7_tx(20),
    "total_words": 21, "words_correct": 14,
    "words_diacritic_error": 2, "words_vowel_error": 2,
    "words_letter_error": 1, "words_incorrect": 2, "words_not_recited": 0,
    "total_score": 55, "completion_percentage": 100,
    "skipped_ayahs": [], "repeated_ayahs": [],
    "skip_detail": [], "repetition_detail": [],
    "ayah_scores": [
        {"ayah": 1, "score": 100, "words_correct": 1, "words_errors": 0},
        {"ayah": 2, "score": 50,  "words_correct": 1, "words_errors": 1,
         "note": "الْقُرْآنَ recited as 'القراء'"},
        {"ayah": 3, "score": 50,  "words_correct": 1, "words_errors": 1,
         "note": "خَلَقَ — fatha on lam raised to damma"},
        {"ayah": 4, "score": 50,  "words_correct": 1, "words_errors": 1,
         "note": "الْبَيَانَ — bā recited as fā"},
        {"ayah": 5, "score": 67,  "words_correct": 2, "words_errors": 1,
         "note": "بِحُسْبَانٍ — tanwīn dropped"},
        {"ayah": 6, "score": 67,  "words_correct": 2, "words_errors": 1,
         "note": "يَسْجُدَانِ — sukūn on sīn dropped, extra syllable"},
        {"ayah": 7, "score": 75,  "words_correct": 3, "words_errors": 1,
         "note": "الْمِيزَانَ — kasra on mīm raised to damma"},
        {"ayah": 8, "score": 75,  "words_correct": 3, "words_errors": 1,
         "note": "تَطْغَوْا — ending 'وا' dropped"},
    ],
    "letter_mistakes": _C7_LM,
    "word_mistakes":   _C7_WM,
    "mistakes":        _C7_ALL,
    "overall_feedback": (
        "7 mistakes: القرآن recited incorrectly; vowel raised in خَلَقَ; "
        "ب→ف in الْبَيَانَ; tanwīn and sukūn dropped (2 diacritics); "
        "kasra→damma in الْمِيزَانَ; and تَطْغَوْا recited incorrectly. "
        "Systematic review of harakat and letter articulation needed."
    ),
    "recording": _recording(7, 40),
}


# ─────────────────────────────────────────────────────────────────────────────
# Case 8 – Severe multi-type: 2 incorrect + 2 letter + 2 diacritic + 1 vowel  (7 mistakes)
#
# Mistakes:
#   Word  0  (الرَّحْمَٰنُ) – diacritic_error: shadda on رَّ dropped  → "الرَحْمَٰنُ"
#   Word  2  (الْقُرْآنَ)   – incorrect:       truncated              → "القرآ"
#   Word  5  (عَلَّمَهُ)    – letter_error:    ه (pos 6) → ح          → "عَلَّمَحُ"
#   Word  9  (بِحُسْبَانٍ)  – diacritic_error: tanwīn kasra dropped   → "بِحُسْبَانَ"
#   Word 11  (وَالشَّجَرُ)  – vowel_error:     damma on ر → fatha     → "وَالشَّجَرَ"
#   Word 14  (رَفَعَهَا)    – letter_error:    ع (pos 4) → غ          → "رَفَغَهَا"
#   Word 18  (تَطْغَوْا)    – incorrect:       ending dropped         → "تطغو"
# ─────────────────────────────────────────────────────────────────────────────

_C8_STATUS = {
    "type": "status", "verse_id": "55:1-8",
    "message": "Session started. Ready to receive audio.",
    "total_words": 21, "total_ayahs": 8,
}

_C8_ERR = {
    0:  "الرَحْمَٰنُ",
    2:  "القرآ",
    5:  "عَلَّمَحُ",
    9:  "بِحُسْبَانَ",
    11: "وَالشَّجَرَ",
    14: "رَفَغَهَا",
    18: "تطغو",
}

_C8_OVR = {
    0:  ("diacritic_error", _C8_ERR[0],  _LF_W0_DIAC),
    2:  ("incorrect",       _C8_ERR[2],  None),
    5:  ("letter_error",    _C8_ERR[5],  _LF_W5_LETTER),
    9:  ("diacritic_error", _C8_ERR[9],  _LF_W9_DIAC),
    11: ("vowel_error",     _C8_ERR[11], _LF_W11_VOWEL),
    14: ("letter_error",    _C8_ERR[14], _LF_W14_LETTER_C8),
    18: ("incorrect",       _C8_ERR[18], None),
}

_M8_DIAC1 = {
    "word_id": "55:1:1", "word_text": "الرَّحْمَٰنُ", "word_position": 0,
    "type": "diacritic_error", "recited_text": _C8_ERR[0],
    "details": "Shadda (ّ) missing from rā — الرَّحْمَٰنُ recited without tashdīd",
    "letter_feedback": _LF_W0_DIAC,
}
_M8_INCR1 = {
    "word_id": "55:2:2", "word_text": "الْقُرْآنَ", "word_position": 2,
    "type": "incorrect", "recited_text": _C8_ERR[2],
    "details": "الْقُرْآنَ truncated — recited as 'القرآ' without the final syllable",
}
_M8_LETTER1 = {
    "word_id": "55:4:1", "word_text": "عَلَّمَهُ", "word_position": 5,
    "type": "letter_error", "recited_text": _C8_ERR[5],
    "details": "هَاء (ه) recited as حَاء (ح) — glottal vs pharyngeal confusion",
    "letter_feedback": _LF_W5_LETTER,
}
_M8_DIAC2 = {
    "word_id": "55:5:3", "word_text": "بِحُسْبَانٍ", "word_position": 9,
    "type": "diacritic_error", "recited_text": _C8_ERR[9],
    "details": "Tanwīn kasra (ٍ) missing — بِحُسْبَانٍ recited as بِحُسْبَانَ",
    "letter_feedback": _LF_W9_DIAC,
}
_M8_VOWEL = {
    "word_id": "55:6:2", "word_text": "وَالشَّجَرُ", "word_position": 11,
    "type": "vowel_error", "recited_text": _C8_ERR[11],
    "details": "Damma (ُ) on rā recited as fatha (َ) — وَالشَّجَرُ became وَالشَّجَرَ",
    "letter_feedback": _LF_W11_VOWEL,
}
_M8_LETTER2 = {
    "word_id": "55:7:2", "word_text": "رَفَعَهَا", "word_position": 14,
    "type": "letter_error", "recited_text": _C8_ERR[14],
    "details": "عَيْن (ع) recited as غَيْن (غ) — voiced pharyngeal vs velar fricative",
    "letter_feedback": _LF_W14_LETTER_C8,
}
_M8_INCR2 = {
    "word_id": "55:8:2", "word_text": "تَطْغَوْا", "word_position": 18,
    "type": "incorrect", "recited_text": _C8_ERR[18],
    "details": "Ending 'وا' dropped — تَطْغَوْا recited as تطغو",
}

_C8_ALL = [_M8_DIAC1, _M8_INCR1, _M8_LETTER1, _M8_DIAC2, _M8_VOWEL, _M8_LETTER2, _M8_INCR2]


def _c8_tx(cursor: int) -> str:
    return " ".join(_C8_ERR.get(i, WORDS[i]["text"]) for i in range(cursor + 1))


def _c8(ci, cursor, ayah, pos, complete, mistakes):
    return {
        "type": "feedback", "chunk_index": ci,
        "transcribed_text": _c8_tx(cursor),
        "current_ayah": ayah, "word_cursor": cursor,
        "position_in_verse": pos, "ayah_complete": complete,
        "skipped_ayahs": [], "repeated_ayahs": [],
        "word_feedback": _wf(cursor, _C8_OVR), "mistakes": mistakes,
    }


_C8_CHUNKS = [
    _c8(1,  0,  1, 0.05, True,  [_M8_DIAC1]),
    _c8(2,  1,  2, 0.10, False, [_M8_DIAC1]),
    _c8(3,  2,  2, 0.14, True,  [_M8_DIAC1, _M8_INCR1]),
    _c8(4,  3,  3, 0.19, False, [_M8_DIAC1, _M8_INCR1]),
    _c8(5,  4,  3, 0.24, True,  [_M8_DIAC1, _M8_INCR1]),
    _c8(6,  5,  4, 0.29, False, [_M8_DIAC1, _M8_INCR1, _M8_LETTER1]),
    _c8(7,  6,  4, 0.33, True,  [_M8_DIAC1, _M8_INCR1, _M8_LETTER1]),
    _c8(8,  7,  5, 0.38, False, [_M8_DIAC1, _M8_INCR1, _M8_LETTER1]),
    _c8(9,  8,  5, 0.43, False, [_M8_DIAC1, _M8_INCR1, _M8_LETTER1]),
    _c8(10, 9,  5, 0.48, True,  [_M8_DIAC1, _M8_INCR1, _M8_LETTER1, _M8_DIAC2]),
    _c8(11, 10, 6, 0.52, False, [_M8_DIAC1, _M8_INCR1, _M8_LETTER1, _M8_DIAC2]),
    _c8(12, 11, 6, 0.57, False, [_M8_DIAC1, _M8_INCR1, _M8_LETTER1, _M8_DIAC2, _M8_VOWEL]),
    _c8(13, 12, 6, 0.62, True,  [_M8_DIAC1, _M8_INCR1, _M8_LETTER1, _M8_DIAC2, _M8_VOWEL]),
    _c8(14, 13, 7, 0.67, False, [_M8_DIAC1, _M8_INCR1, _M8_LETTER1, _M8_DIAC2, _M8_VOWEL]),
    _c8(15, 14, 7, 0.71, False, [_M8_DIAC1, _M8_INCR1, _M8_LETTER1, _M8_DIAC2, _M8_VOWEL, _M8_LETTER2]),
    _c8(16, 15, 7, 0.76, False, [_M8_DIAC1, _M8_INCR1, _M8_LETTER1, _M8_DIAC2, _M8_VOWEL, _M8_LETTER2]),
    _c8(17, 16, 7, 0.81, True,  [_M8_DIAC1, _M8_INCR1, _M8_LETTER1, _M8_DIAC2, _M8_VOWEL, _M8_LETTER2]),
    _c8(18, 17, 8, 0.86, False, [_M8_DIAC1, _M8_INCR1, _M8_LETTER1, _M8_DIAC2, _M8_VOWEL, _M8_LETTER2]),
    _c8(19, 18, 8, 0.90, False, _C8_ALL),
    _c8(20, 19, 8, 0.95, False, _C8_ALL),
    _c8(21, 20, 8, 1.00, True,  _C8_ALL),
]

_C8_LM, _C8_WM = _split_mistakes(_C8_ALL)

_C8_SUMMARY = {
    "type": "session_summary", "verse_id": "55:1-8",
    "total_chunks": 21, "duration_seconds": 40,
    "full_transcription": _c8_tx(20),
    "total_words": 21, "words_correct": 14,
    "words_diacritic_error": 2, "words_vowel_error": 1,
    "words_letter_error": 2, "words_incorrect": 2, "words_not_recited": 0,
    "total_score": 52, "completion_percentage": 100,
    "skipped_ayahs": [], "repeated_ayahs": [],
    "skip_detail": [], "repetition_detail": [],
    "ayah_scores": [
        {"ayah": 1, "score": 50,  "words_correct": 0, "words_errors": 1,
         "note": "الرَّحْمَٰنُ — shadda on rā missing"},
        {"ayah": 2, "score": 50,  "words_correct": 1, "words_errors": 1,
         "note": "الْقُرْآنَ — truncated to 'القرآ'"},
        {"ayah": 3, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 4, "score": 50,  "words_correct": 1, "words_errors": 1,
         "note": "عَلَّمَهُ — hā recited as ḥā"},
        {"ayah": 5, "score": 67,  "words_correct": 2, "words_errors": 1,
         "note": "بِحُسْبَانٍ — tanwīn dropped"},
        {"ayah": 6, "score": 67,  "words_correct": 2, "words_errors": 1,
         "note": "وَالشَّجَرُ — damma on rā dropped to fatha"},
        {"ayah": 7, "score": 75,  "words_correct": 3, "words_errors": 1,
         "note": "رَفَعَهَا — ʿayn recited as ghain"},
        {"ayah": 8, "score": 75,  "words_correct": 3, "words_errors": 1,
         "note": "تَطْغَوْا — ending dropped"},
    ],
    "letter_mistakes": _C8_LM,
    "word_mistakes":   _C8_WM,
    "mistakes":        _C8_ALL,
    "overall_feedback": (
        "7 mistakes across 4 categories: "
        "shadda dropped from الرَّحْمَٰنُ and tanwīn from بِحُسْبَانٍ (2 diacritics); "
        "ه→ح in عَلَّمَهُ and ع→غ in رَفَعَهَا (2 letter errors); "
        "damma→fatha in وَالشَّجَرُ (vowel); "
        "الْقُرْآنَ and تَطْغَوْا recited incorrectly. "
        "Serious practice of pharyngeal letters and diacritics required."
    ),
    "recording": _recording(8, 40),
}


# ─────────────────────────────────────────────────────────────────────────────
# Case 9 – Extreme chaos: 1 incorrect + 3 letter + 2 diacritic + 2 vowel  (8 mistakes)
#
# Mistakes:
#   Word  1  (عَلَّمَ)      – diacritic_error: shadda on ل dropped    → "عَلَمَ"
#   Word  4  (الْإِنسَانَ)  – letter_error:    ن (pos 5) → م          → "الْإِمسَانَ"
#   Word  5  (عَلَّمَهُ)    – vowel_error:     damma on ه → kasra     → "عَلَّمَهِ"
#   Word  8  (وَالْقَمَرُ)  – letter_error:    ق (pos 5) → ك          → "وَالْكَمَرُ"
#   Word 10  (وَالنَّجْمُ)  – diacritic_error: shadda on نَّ dropped   → "وَالنَجْمُ"
#   Word 13  (وَالسَّمَاءَ) – incorrect:       wrong word             → "والأرض"
#   Word 15  (وَوَضَعَ)     – vowel_error:     fatha on ض → kasra     → "وَوَضِعَ"
#   Word 17  (أَلَّا)       – letter_error:    ل (pos 2) → ن          → "أَنَّا"
# ─────────────────────────────────────────────────────────────────────────────

_C9_STATUS = {
    "type": "status", "verse_id": "55:1-8",
    "message": "Session started. Ready to receive audio.",
    "total_words": 21, "total_ayahs": 8,
}

_C9_ERR = {
    1:  "عَلَمَ",
    4:  "الْإِمسَانَ",
    5:  "عَلَّمَهِ",
    8:  "وَالْكَمَرُ",
    10: "وَالنَجْمُ",
    13: "والأرض",
    15: "وَوَضِعَ",
    17: "أَنَّا",
}

_C9_OVR = {
    1:  ("diacritic_error", _C9_ERR[1],  _LF_W1_DIAC),
    4:  ("letter_error",    _C9_ERR[4],  _LF_W4_LETTER),
    5:  ("vowel_error",     _C9_ERR[5],  _LF_W5_VOWEL),
    8:  ("letter_error",    _C9_ERR[8],  _LF_W8_LETTER_C9),
    10: ("diacritic_error", _C9_ERR[10], _LF_W10_DIAC),
    13: ("incorrect",       _C9_ERR[13], None),
    15: ("vowel_error",     _C9_ERR[15], _LF_W15_VOWEL),
    17: ("letter_error",    _C9_ERR[17], _LF_W17_LETTER),
}

_M9_DIAC1 = {
    "word_id": "55:2:1", "word_text": "عَلَّمَ", "word_position": 1,
    "type": "diacritic_error", "recited_text": _C9_ERR[1],
    "details": "Shadda (ّ) missing from lam — عَلَّمَ became عَلَمَ (double consonant lost)",
    "letter_feedback": _LF_W1_DIAC,
}
_M9_LETTER1 = {
    "word_id": "55:3:2", "word_text": "الْإِنسَانَ", "word_position": 4,
    "type": "letter_error", "recited_text": _C9_ERR[4],
    "details": "نُون (ن, pos 5) recited as مِيم (م) — nasal confusion",
    "letter_feedback": _LF_W4_LETTER,
}
_M9_VOWEL1 = {
    "word_id": "55:4:1", "word_text": "عَلَّمَهُ", "word_position": 5,
    "type": "vowel_error", "recited_text": _C9_ERR[5],
    "details": "Damma (ُ) on hā recited as kasra (ِ) — عَلَّمَهُ became عَلَّمَهِ",
    "letter_feedback": _LF_W5_VOWEL,
}
_M9_LETTER2 = {
    "word_id": "55:5:2", "word_text": "وَالْقَمَرُ", "word_position": 8,
    "type": "letter_error", "recited_text": _C9_ERR[8],
    "details": "قَاف (ق) recited as كَاف (ك) — uvular vs velar stop confusion",
    "letter_feedback": _LF_W8_LETTER_C9,
}
_M9_DIAC2 = {
    "word_id": "55:6:1", "word_text": "وَالنَّجْمُ", "word_position": 10,
    "type": "diacritic_error", "recited_text": _C9_ERR[10],
    "details": "Shadda (ّ) missing from nūn — وَالنَّجْمُ recited as وَالنَجْمُ",
    "letter_feedback": _LF_W10_DIAC,
}
_M9_INCR = {
    "word_id": "55:7:1", "word_text": "وَالسَّمَاءَ", "word_position": 13,
    "type": "incorrect", "recited_text": _C9_ERR[13],
    "details": "Completely wrong word recited — 'والأرض' instead of وَالسَّمَاءَ",
}
_M9_VOWEL2 = {
    "word_id": "55:7:3", "word_text": "وَوَضَعَ", "word_position": 15,
    "type": "vowel_error", "recited_text": _C9_ERR[15],
    "details": "Fatha (َ) on ḍād recited as kasra (ِ) — وَوَضَعَ became وَوَضِعَ",
    "letter_feedback": _LF_W15_VOWEL,
}
_M9_LETTER3 = {
    "word_id": "55:8:1", "word_text": "أَلَّا", "word_position": 17,
    "type": "letter_error", "recited_text": _C9_ERR[17],
    "details": "لَام (ل, pos 2) recited as نُون (ن) — أَلَّا became أَنَّا",
    "letter_feedback": _LF_W17_LETTER,
}

_C9_ALL = [
    _M9_DIAC1, _M9_LETTER1, _M9_VOWEL1, _M9_LETTER2,
    _M9_DIAC2, _M9_INCR, _M9_VOWEL2, _M9_LETTER3,
]


def _c9_tx(cursor: int) -> str:
    return " ".join(_C9_ERR.get(i, WORDS[i]["text"]) for i in range(cursor + 1))


def _c9(ci, cursor, ayah, pos, complete, mistakes):
    return {
        "type": "feedback", "chunk_index": ci,
        "transcribed_text": _c9_tx(cursor),
        "current_ayah": ayah, "word_cursor": cursor,
        "position_in_verse": pos, "ayah_complete": complete,
        "skipped_ayahs": [], "repeated_ayahs": [],
        "word_feedback": _wf(cursor, _C9_OVR), "mistakes": mistakes,
    }


_C9_CHUNKS = [
    _c9(1,  0,  1, 0.05, True,  []),
    _c9(2,  1,  2, 0.10, False, [_M9_DIAC1]),
    _c9(3,  2,  2, 0.14, True,  [_M9_DIAC1]),
    _c9(4,  3,  3, 0.19, False, [_M9_DIAC1]),
    _c9(5,  4,  3, 0.24, True,  [_M9_DIAC1, _M9_LETTER1]),
    _c9(6,  5,  4, 0.29, False, [_M9_DIAC1, _M9_LETTER1, _M9_VOWEL1]),
    _c9(7,  6,  4, 0.33, True,  [_M9_DIAC1, _M9_LETTER1, _M9_VOWEL1]),
    _c9(8,  7,  5, 0.38, False, [_M9_DIAC1, _M9_LETTER1, _M9_VOWEL1]),
    _c9(9,  8,  5, 0.43, False, [_M9_DIAC1, _M9_LETTER1, _M9_VOWEL1, _M9_LETTER2]),
    _c9(10, 9,  5, 0.48, True,  [_M9_DIAC1, _M9_LETTER1, _M9_VOWEL1, _M9_LETTER2]),
    _c9(11, 10, 6, 0.52, False, [_M9_DIAC1, _M9_LETTER1, _M9_VOWEL1, _M9_LETTER2, _M9_DIAC2]),
    _c9(12, 11, 6, 0.57, False, [_M9_DIAC1, _M9_LETTER1, _M9_VOWEL1, _M9_LETTER2, _M9_DIAC2]),
    _c9(13, 12, 6, 0.62, True,  [_M9_DIAC1, _M9_LETTER1, _M9_VOWEL1, _M9_LETTER2, _M9_DIAC2]),
    _c9(14, 13, 7, 0.67, False, [_M9_DIAC1, _M9_LETTER1, _M9_VOWEL1, _M9_LETTER2, _M9_DIAC2, _M9_INCR]),
    _c9(15, 14, 7, 0.71, False, [_M9_DIAC1, _M9_LETTER1, _M9_VOWEL1, _M9_LETTER2, _M9_DIAC2, _M9_INCR]),
    _c9(16, 15, 7, 0.76, False, [_M9_DIAC1, _M9_LETTER1, _M9_VOWEL1, _M9_LETTER2, _M9_DIAC2, _M9_INCR, _M9_VOWEL2]),
    _c9(17, 16, 7, 0.81, True,  [_M9_DIAC1, _M9_LETTER1, _M9_VOWEL1, _M9_LETTER2, _M9_DIAC2, _M9_INCR, _M9_VOWEL2]),
    _c9(18, 17, 8, 0.86, False, _C9_ALL),
    _c9(19, 18, 8, 0.90, False, _C9_ALL),
    _c9(20, 19, 8, 0.95, False, _C9_ALL),
    _c9(21, 20, 8, 1.00, True,  _C9_ALL),
]

_C9_LM, _C9_WM = _split_mistakes(_C9_ALL)

_C9_SUMMARY = {
    "type": "session_summary", "verse_id": "55:1-8",
    "total_chunks": 21, "duration_seconds": 42,
    "full_transcription": _c9_tx(20),
    "total_words": 21, "words_correct": 13,
    "words_diacritic_error": 2, "words_vowel_error": 2,
    "words_letter_error": 3, "words_incorrect": 1, "words_not_recited": 0,
    "total_score": 42, "completion_percentage": 100,
    "skipped_ayahs": [], "repeated_ayahs": [],
    "skip_detail": [], "repetition_detail": [],
    "ayah_scores": [
        {"ayah": 1, "score": 100, "words_correct": 1, "words_errors": 0},
        {"ayah": 2, "score": 50,  "words_correct": 1, "words_errors": 1,
         "note": "عَلَّمَ — shadda missing from lam"},
        {"ayah": 3, "score": 50,  "words_correct": 1, "words_errors": 1,
         "note": "الْإِنسَانَ — nūn (pos 5) recited as mīm"},
        {"ayah": 4, "score": 50,  "words_correct": 1, "words_errors": 1,
         "note": "عَلَّمَهُ — damma on hā recited as kasra"},
        {"ayah": 5, "score": 67,  "words_correct": 2, "words_errors": 1,
         "note": "وَالْقَمَرُ — qāf recited as kāf"},
        {"ayah": 6, "score": 67,  "words_correct": 2, "words_errors": 1,
         "note": "وَالنَّجْمُ — shadda missing from nūn"},
        {"ayah": 7, "score": 25,  "words_correct": 1, "words_errors": 3,
         "note": "وَالسَّمَاءَ recited incorrectly; وَوَضَعَ vowel error; أَلَّا lām→nūn"},
        {"ayah": 8, "score": 100, "words_correct": 4, "words_errors": 0},
    ],
    "letter_mistakes": _C9_LM,
    "word_mistakes":   _C9_WM,
    "mistakes":        _C9_ALL,
    "overall_feedback": (
        "8 mistakes — critical practice required: "
        "shadda dropped from عَلَّمَ and وَالنَّجْمُ (2 diacritics); "
        "ن→م in الْإِنسَانَ, ق→ك in وَالْقَمَرُ, ل→ن in أَلَّا (3 letter errors); "
        "damma→kasra in عَلَّمَهُ and fatha→kasra in وَوَضَعَ (2 vowel errors); "
        "and وَالسَّمَاءَ recited as a completely wrong word. "
        "Focused drill on each of these words is strongly recommended."
    ),
    "recording": _recording(9, 42),
}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

CASE_DATA = {
    1: {"status": _C1_STATUS, "chunks": _C1_CHUNKS, "summary": _C1_SUMMARY},
    2: {"status": _C2_STATUS, "chunks": _C2_CHUNKS, "summary": _C2_SUMMARY},
    3: {"status": _C3_STATUS, "chunks": _C3_CHUNKS, "summary": _C3_SUMMARY},
    4: {"status": _C4_STATUS, "chunks": _C4_CHUNKS, "summary": _C4_SUMMARY},
    5: {"status": _C5_STATUS, "chunks": _C5_CHUNKS, "summary": _C5_SUMMARY},
    6: {"status": _C6_STATUS, "chunks": _C6_CHUNKS, "summary": _C6_SUMMARY},
    7: {"status": _C7_STATUS, "chunks": _C7_CHUNKS, "summary": _C7_SUMMARY},
    8: {"status": _C8_STATUS, "chunks": _C8_CHUNKS, "summary": _C8_SUMMARY},
    9: {"status": _C9_STATUS, "chunks": _C9_CHUNKS, "summary": _C9_SUMMARY},
}
