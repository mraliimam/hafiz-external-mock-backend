"""
Mock response data for all 7 test cases.

Case 1 – Smooth recitation: 1 diacritic error + 1 incorrect word.
Case 2 – User repeats Ayah 1 before continuing (perfect otherwise).
Case 3 – User skips Ayah 2 and jumps directly to Ayah 3.
Case 4 – Heavy harakat mistakes: 3 diacritic errors + 2 vowel errors.
Case 5 – Letter-level mistakes: 2 consonant substitutions + 2 vowel errors.
Case 6 – Mixed mistakes: 1 incorrect word + 1 letter error + 1 diacritic error + 1 vowel error.
Case 7 – Heavy mixed mistakes: 1 incorrect word + 1 letter error + 2 diacritic errors + 1 vowel error.

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

Words with "vowel_error" or "letter_error" carry an extra letter_feedback
list that pins the mistake to the exact letter position.
"""

import base64
import math
import struct
from typing import Any, Dict, List, Optional, Tuple

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
    """Return a base64-encoded 16 kHz mono 16-bit PCM WAV sine-wave tone.

    Each use-case gets a distinct pitch so the frontend developer can
    audibly tell which session is playing.
    """
    sample_rate = 16000
    n_samples = int(sample_rate * duration_ms / 1000)
    amplitude = 8000  # safe level, well below 16-bit saturation (32767)

    pcm = bytearray()
    for i in range(n_samples):
        value = int(amplitude * math.sin(2.0 * math.pi * freq_hz * i / sample_rate))
        pcm += struct.pack("<h", value)

    data_size = len(pcm)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16,        # PCM subchunk size
        1,                  # AudioFormat = PCM
        1,                  # NumChannels = mono
        sample_rate,        # SampleRate
        sample_rate * 2,    # ByteRate = SampleRate * BlockAlign
        2,                  # BlockAlign = channels * bits/8
        16,                 # BitsPerSample
        b"data", data_size,
    )
    return base64.b64encode(header + bytes(pcm)).decode("ascii")


# Pre-computed per-case WAVs (different pitches — A4, C5, G4, F4, D4, C4, E4)
MOCK_WAVS: Dict[int, str] = {
    1: _make_mock_wav(440.0),   # A4 – Case 1
    2: _make_mock_wav(523.25),  # C5 – Case 2
    3: _make_mock_wav(392.0),   # G4 – Case 3
    4: _make_mock_wav(349.23),  # F4 – Case 4
    5: _make_mock_wav(293.66),  # D4 – Case 5
    6: _make_mock_wav(261.63),  # C4 – Case 6
    7: _make_mock_wav(329.63),  # E4 – Case 7
}

def _recording(case_num: int, duration_seconds: int) -> Dict[str, Any]:
    """Build the recording metadata block for a session_summary."""
    wav_b64 = MOCK_WAVS[case_num]
    size_bytes = len(base64.b64decode(wav_b64))
    return {
        "audio_data":    wav_b64,
        "audio_format":  "wav",
        "audio_size_bytes": size_bytes,
        "duration_seconds": duration_seconds,
        "filename":      f"recitation_case_{case_num}.wav",
        "download_url":  f"/api/recordings/{case_num}",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _wf(cursor: int, overrides: Optional[Dict] = None, skipped: Optional[Any] = None) -> List[Dict]:
    """Build the 21-element word_feedback list.

    cursor    – last word index reached (inclusive, 0-based)
    overrides – {index: (status, recited_text)}
                     or {index: (status, recited_text, letter_feedback)}
                for non-correct entries.
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
# Letter-feedback arrays  (one per word that has a vowel/letter error)
# ─────────────────────────────────────────────────────────────────────────────
#
# Each entry: { position, expected_letter, recited_letter, status }
# status values: "correct" | "diacritic_error" | "vowel_error" | "letter_error"

# ── Case 4 letter feedback ────────────────────────────────────────────────────

# Word 1 · عَلَّمَ  → "عَلَمَ"  (shadda on lam dropped)
# letters: ["ع","َ","ل","َّ","م","َ"]
_LF_W1_DIAC = [
    {"position": 0, "expected_letter": "ع",  "recited_letter": "ع",  "status": "correct"},
    {"position": 1, "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
    {"position": 2, "expected_letter": "ل",  "recited_letter": "ل",  "status": "correct"},
    {"position": 3, "expected_letter": "َّ", "recited_letter": "َ",  "status": "diacritic_error"},
    {"position": 4, "expected_letter": "م",  "recited_letter": "م",  "status": "correct"},
    {"position": 5, "expected_letter": "َ",  "recited_letter": "َ",  "status": "correct"},
]

# Word 5 · عَلَّمَهُ  → "عَلَّمَه"  (damma on hā dropped)
# letters: ["ع","َ","ل","َّ","م","َ","ه","ُ"]
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

# Word 12 · يَسْجُدَانِ  → "يَسْجُدَانَ"  (kasra on nūn → fatha)
# letters: ["ي","َ","س","ْ","ج","ُ","د","َ","ا","ن","ِ"]
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

# Word 14 · رَفَعَهَا  → "رُفِعَهَا"  (fatha on rā → damma; fatha on fā → kasra)
# letters: ["ر","َ","ف","َ","ع","َ","ه","َ","ا"]
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

# Word 16 · الْمِيزَانَ  → "الْمَيزَانَ"  (kasra on mīm → fatha)
# letters: ["ا","ل","ْ","م","ِ","ي","ز","َ","ا","ن","َ"]
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

# ── Case 5 letter feedback ────────────────────────────────────────────────────

# Word 3 · خَلَقَ  → "حَلَقَ"  (kha خ substituted by ha ح)
# letters: ["خ","َ","ل","َ","ق","َ"]
_LF_W3_LETTER = [
    {"position": 0, "expected_letter": "خ", "recited_letter": "ح", "status": "letter_error"},
    {"position": 1, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 2, "expected_letter": "ل", "recited_letter": "ل", "status": "correct"},
    {"position": 3, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
    {"position": 4, "expected_letter": "ق", "recited_letter": "ق", "status": "correct"},
    {"position": 5, "expected_letter": "َ", "recited_letter": "َ", "status": "correct"},
]

# Word 8 · وَالْقَمَرُ  → "وَالْغَمَرُ"  (qāf ق substituted by ghain غ)
# letters: ["و","َ","ا","ل","ْ","ق","َ","م","َ","ر","ُ"]
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

# Word 10 · وَالنَّجْمُ  → "وَالنَّجْمِ"  (damma ُ on mīm → kasra ِ)
# letters: ["و","َ","ا","ل","ن","َّ","ج","ْ","م","ُ"]
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

# Word 15 · وَوَضَعَ  → "وَوَضِعَ"  (fatha َ on dad → kasra ِ)
# letters: ["و","َ","و","َ","ض","َ","ع","َ"]
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


# ─────────────────────────────────────────────────────────────────────────────
# Shared mistake objects  (Cases 1 & 2 & 3)
# ─────────────────────────────────────────────────────────────────────────────

_M_DIAC = {
    "word_id": "55:5:3", "word_text": "بِحُسْبَانٍ",
    "type": "diacritic_error", "recited_text": "بحسبان",
    "details": "Tanwīn kasra (ٍ) missing at end of word",
}
_M_INCR = {
    "word_id": "55:8:2", "word_text": "تَطْغَوْا",
    "type": "incorrect", "recited_text": "تطغو",
    "details": "Ending 'وا' dropped from word",
}


# ─────────────────────────────────────────────────────────────────────────────
# Case 1 – Smooth recitation with two mistakes
# ─────────────────────────────────────────────────────────────────────────────

_C1_OVR = {
    9:  ("diacritic_error", "بحسبان"),   # بِحُسْبَانٍ – tanwin dropped
    18: ("incorrect",       "تطغو"),     # تَطْغَوْا – waw-alif dropped
}

_C1_STATUS = {
    "type": "status",
    "verse_id": "55:1-8",
    "message": "Session started. Ready to receive audio.",
    "total_words": 21,
    "total_ayahs": 8,
}


def _c1(ci, cursor, ayah, pos, complete, mistakes):
    return {
        "type": "feedback",
        "chunk_index": ci,
        "transcribed_text": _txt(range(cursor + 1)),
        "current_ayah": ayah,
        "word_cursor": cursor,
        "position_in_verse": pos,
        "ayah_complete": complete,
        "skipped_ayahs": [],
        "repeated_ayahs": [],
        "word_feedback": _wf(cursor, _C1_OVR),
        "mistakes": mistakes,
    }


_C1_CHUNKS = [
    _c1(1,  0,  1, 0.05, True,  []),
    _c1(2,  1,  2, 0.10, False, []),
    _c1(3,  2,  2, 0.14, True,  []),
    _c1(4,  3,  3, 0.19, False, []),
    _c1(5,  4,  3, 0.24, True,  []),
    _c1(6,  5,  4, 0.29, False, []),
    _c1(7,  6,  4, 0.33, True,  []),
    _c1(8,  7,  5, 0.38, False, []),
    _c1(9,  8,  5, 0.43, False, []),
    _c1(10, 9,  5, 0.48, True,  [_M_DIAC]),
    _c1(11, 10, 6, 0.52, False, [_M_DIAC]),
    _c1(12, 11, 6, 0.57, False, [_M_DIAC]),
    _c1(13, 12, 6, 0.62, True,  [_M_DIAC]),
    _c1(14, 13, 7, 0.67, False, [_M_DIAC]),
    _c1(15, 14, 7, 0.71, False, [_M_DIAC]),
    _c1(16, 15, 7, 0.76, False, [_M_DIAC]),
    _c1(17, 16, 7, 0.81, True,  [_M_DIAC]),
    {
        "type": "feedback", "chunk_index": 18,
        "transcribed_text": _txt(range(19)), "current_ayah": 8,
        "word_cursor": 18, "position_in_verse": 0.90, "ayah_complete": False,
        "skipped_ayahs": [], "repeated_ayahs": [],
        "word_feedback": _wf(18, _C1_OVR), "mistakes": [_M_DIAC, _M_INCR],
    },
    {
        "type": "feedback", "chunk_index": 19,
        "transcribed_text": _txt(range(21)), "current_ayah": 8,
        "word_cursor": 20, "position_in_verse": 1.00, "ayah_complete": True,
        "skipped_ayahs": [], "repeated_ayahs": [],
        "word_feedback": _wf(20, _C1_OVR), "mistakes": [_M_DIAC, _M_INCR],
    },
]

_C1_SUMMARY = {
    "type": "session_summary",
    "verse_id": "55:1-8",
    "total_chunks": 19,
    "duration_seconds": 38,
    "full_transcription": _txt(range(21)),
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
        {"ayah": 2, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 3, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 4, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 5, "score": 80,  "words_correct": 2, "words_errors": 1},
        {"ayah": 6, "score": 100, "words_correct": 3, "words_errors": 0},
        {"ayah": 7, "score": 100, "words_correct": 4, "words_errors": 0},
        {"ayah": 8, "score": 75,  "words_correct": 3, "words_errors": 1},
    ],
    "mistakes": [_M_DIAC, _M_INCR],
    "overall_feedback": (
        "Excellent recitation! 2 mistakes to review: a missing tanwīn on "
        "بِحُسْبَانٍ and an incorrect reading of تَطْغَوْا. All 8 ayahs completed."
    ),
    "recording": _recording(1, 38),
}


# ─────────────────────────────────────────────────────────────────────────────
# Case 2 – User repeats Ayah 1 then recites perfectly
# ─────────────────────────────────────────────────────────────────────────────

_C2_STATUS = {
    "type": "status",
    "verse_id": "55:1-8",
    "message": "Session started. Ready to receive audio.",
    "total_words": 21,
    "total_ayahs": 8,
}

_C2_REP_DETAIL = [{
    "ayah": 1,
    "first_occurrence_chunk": 1,
    "repeat_chunk": 2,
    "recited_text": "الرحمن",
    "note": "Ayah 1 recited again from the beginning",
}]

_C2_W0 = WORDS[0]["text"]
_C2_PREFIX = _C2_W0 + " " + _C2_W0   # "الرَّحْمَٰنُ الرَّحْمَٰنُ"


def _c2_tx(cursor):
    if cursor == 0:
        return _C2_PREFIX
    return _C2_PREFIX + " " + _txt(range(1, cursor + 1))


def _c2_prog(ci, cursor, ayah, pos, complete):
    return {
        "type": "feedback",
        "chunk_index": ci,
        "transcribed_text": _c2_tx(cursor),
        "current_ayah": ayah,
        "word_cursor": cursor,
        "position_in_verse": pos,
        "ayah_complete": complete,
        "skipped_ayahs": [],
        "repeated_ayahs": [1],
        "repetition_detail": _C2_REP_DETAIL,
        "word_feedback": _wf(cursor),
        "mistakes": [],
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
    _c2_prog(3,  1,  2, 0.10, False),
    _c2_prog(4,  2,  2, 0.14, True),
    _c2_prog(5,  3,  3, 0.19, False),
    _c2_prog(6,  4,  3, 0.24, True),
    _c2_prog(7,  5,  4, 0.29, False),
    _c2_prog(8,  6,  4, 0.33, True),
    _c2_prog(9,  7,  5, 0.38, False),
    _c2_prog(10, 8,  5, 0.43, False),
    _c2_prog(11, 9,  5, 0.48, True),
    _c2_prog(12, 10, 6, 0.52, False),
    _c2_prog(13, 11, 6, 0.57, False),
    _c2_prog(14, 12, 6, 0.62, True),
    _c2_prog(15, 13, 7, 0.67, False),
    _c2_prog(16, 14, 7, 0.71, False),
    _c2_prog(17, 15, 7, 0.76, False),
    _c2_prog(18, 16, 7, 0.81, True),
    _c2_prog(19, 17, 8, 0.86, False),
    _c2_prog(20, 18, 8, 0.90, False),
    _c2_prog(21, 20, 8, 1.00, True),
]

_C2_SUMMARY = {
    "type": "session_summary",
    "verse_id": "55:1-8",
    "total_chunks": 21,
    "duration_seconds": 42,
    "full_transcription": _c2_tx(20),
    "total_words": 21,
    "words_correct": 21,
    "words_diacritic_error": 0,
    "words_vowel_error": 0,
    "words_letter_error": 0,
    "words_incorrect": 0,
    "words_not_recited": 0,
    "total_score": 95,
    "completion_percentage": 100,
    "skipped_ayahs": [],
    "repeated_ayahs": [1],
    "skip_detail": [],
    "repetition_detail": _C2_REP_DETAIL,
    "ayah_scores": [
        {"ayah": 1, "score": 100, "words_correct": 1, "words_errors": 0, "note": "Repeated once"},
        {"ayah": 2, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 3, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 4, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 5, "score": 100, "words_correct": 3, "words_errors": 0},
        {"ayah": 6, "score": 100, "words_correct": 3, "words_errors": 0},
        {"ayah": 7, "score": 100, "words_correct": 4, "words_errors": 0},
        {"ayah": 8, "score": 100, "words_correct": 4, "words_errors": 0},
    ],
    "mistakes": [],
    "overall_feedback": (
        "Perfect recitation! All words and harakat correct. "
        "Note: Ayah 1 was repeated once — this may indicate uncertainty at the start."
    ),
    "recording": _recording(2, 42),
}


# ─────────────────────────────────────────────────────────────────────────────
# Case 3 – User skips Ayah 2 and jumps to Ayah 3
# ─────────────────────────────────────────────────────────────────────────────

_C3_STATUS = {
    "type": "status",
    "verse_id": "55:1-8",
    "message": "Session started. Ready to receive audio.",
    "total_words": 21,
    "total_ayahs": 8,
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


def _c3_tx(cursor):
    indices = [i for i in range(cursor + 1) if i not in _C3_SKIP_POS]
    return _txt(indices)


def _c3_prog(ci, cursor, ayah, pos, complete):
    return {
        "type": "feedback",
        "chunk_index": ci,
        "transcribed_text": _c3_tx(cursor),
        "current_ayah": ayah,
        "word_cursor": cursor,
        "position_in_verse": pos,
        "ayah_complete": complete,
        "skipped_ayahs": [2],
        "skip_detail": _C3_SKIP_DETAIL,
        "repeated_ayahs": [],
        "word_feedback": _wf(cursor, skipped=_C3_SKIP_POS),
        "mistakes": [],
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
        "word_feedback": _wf(3, skipped=_C3_SKIP_POS), "mistakes": [],
    },
    {
        "type": "feedback", "chunk_index": 3,
        "transcribed_text": _txt([0, 3, 4]), "current_ayah": 3,
        "word_cursor": 4, "position_in_verse": 0.24, "ayah_complete": True,
        "skipped_ayahs": [2], "skip_detail": _C3_SKIP_DETAIL, "repeated_ayahs": [],
        "word_feedback": _wf(4, skipped=_C3_SKIP_POS), "mistakes": [],
    },
    _c3_prog(4,  5,  4, 0.29, False),
    _c3_prog(5,  6,  4, 0.33, True),
    _c3_prog(6,  7,  5, 0.38, False),
    _c3_prog(7,  8,  5, 0.43, False),
    _c3_prog(8,  9,  5, 0.48, True),
    _c3_prog(9,  10, 6, 0.52, False),
    _c3_prog(10, 11, 6, 0.57, False),
    _c3_prog(11, 12, 6, 0.62, True),
    _c3_prog(12, 13, 7, 0.67, False),
    _c3_prog(13, 14, 7, 0.71, False),
    _c3_prog(14, 15, 7, 0.76, False),
    _c3_prog(15, 16, 7, 0.81, True),
    _c3_prog(16, 17, 8, 0.86, False),
    _c3_prog(17, 18, 8, 0.90, False),
    _c3_prog(18, 19, 8, 0.95, False),
    _c3_prog(19, 20, 8, 1.00, True),
]

_C3_SUMMARY = {
    "type": "session_summary",
    "verse_id": "55:1-8",
    "total_chunks": 19,
    "duration_seconds": 38,
    "full_transcription": _c3_tx(20),
    "total_words": 21,
    "words_correct": 19,
    "words_diacritic_error": 0,
    "words_vowel_error": 0,
    "words_letter_error": 0,
    "words_incorrect": 0,
    "words_not_recited": 2,
    "total_score": 72,
    "completion_percentage": 90,
    "skipped_ayahs": [2],
    "repeated_ayahs": [],
    "skip_detail": _C3_SKIP_DETAIL,
    "repetition_detail": [],
    "ayah_scores": [
        {"ayah": 1, "score": 100, "words_correct": 1, "words_errors": 0},
        {"ayah": 2, "score": 0,   "words_correct": 0, "words_errors": 0, "note": "Skipped entirely"},
        {"ayah": 3, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 4, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 5, "score": 100, "words_correct": 3, "words_errors": 0},
        {"ayah": 6, "score": 100, "words_correct": 3, "words_errors": 0},
        {"ayah": 7, "score": 100, "words_correct": 4, "words_errors": 0},
        {"ayah": 8, "score": 100, "words_correct": 4, "words_errors": 0},
    ],
    "mistakes": [],
    "overall_feedback": (
        "Good recitation with one issue: Ayah 2 (عَلَّمَ الْقُرْآنَ) was skipped. "
        "All other ayahs were recited correctly. "
        "Review and memorise ayah 2 before the next session."
    ),
    "recording": _recording(3, 38),
}


# ─────────────────────────────────────────────────────────────────────────────
# Case 4 – Heavy harakat mistakes (3 diacritic + 2 vowel errors)
#
# Scenario: User completes all 8 ayahs but repeatedly struggles with harakat.
#
# Mistakes:
#   Word  1  (عَلَّمَ)     – diacritic_error: shadda on lam dropped → "عَلَمَ"
#   Word  5  (عَلَّمَهُ)   – diacritic_error: damma on hā dropped   → "عَلَّمَه"
#   Word 12  (يَسْجُدَانِ) – diacritic_error: kasra on nūn → fatha  → "يَسْجُدَانَ"
#   Word 14  (رَفَعَهَا)   – vowel_error:    fatha→damma, fatha→kasra → "رُفِعَهَا"
#   Word 16  (الْمِيزَانَ) – vowel_error:    kasra on mīm → fatha   → "الْمَيزَانَ"
# ─────────────────────────────────────────────────────────────────────────────

_C4_STATUS = {
    "type": "status",
    "verse_id": "55:1-8",
    "message": "Session started. Ready to receive audio.",
    "total_words": 21,
    "total_ayahs": 8,
}

# Recited forms for error words in Case 4
_C4_ERR = {
    1:  "عَلَمَ",
    5:  "عَلَّمَه",
    12: "يَسْجُدَانَ",
    14: "رُفِعَهَا",
    16: "الْمَيزَانَ",
}

# Overrides: (status, recited_text, letter_feedback)
_C4_OVR = {
    1:  ("diacritic_error", _C4_ERR[1],  _LF_W1_DIAC),
    5:  ("diacritic_error", _C4_ERR[5],  _LF_W5_DIAC),
    12: ("diacritic_error", _C4_ERR[12], _LF_W12_DIAC),
    14: ("vowel_error",     _C4_ERR[14], _LF_W14_VOWEL),
    16: ("vowel_error",     _C4_ERR[16], _LF_W16_VOWEL),
}

# Mistake objects (carry letter_feedback for rich frontend display)
_M4_DIAC1 = {
    "word_id": "55:2:1", "word_text": "عَلَّمَ",
    "type": "diacritic_error", "recited_text": _C4_ERR[1],
    "details": "Shadda (ّ) missing on lam — word shortened to عَلَمَ",
    "letter_feedback": _LF_W1_DIAC,
}
_M4_DIAC2 = {
    "word_id": "55:4:1", "word_text": "عَلَّمَهُ",
    "type": "diacritic_error", "recited_text": _C4_ERR[5],
    "details": "Damma (ُ) missing on hā — word ends without vowel",
    "letter_feedback": _LF_W5_DIAC,
}
_M4_DIAC3 = {
    "word_id": "55:6:3", "word_text": "يَسْجُدَانِ",
    "type": "diacritic_error", "recited_text": _C4_ERR[12],
    "details": "Kasra (ِ) on nūn recited as fatha (َ) — ending changed",
    "letter_feedback": _LF_W12_DIAC,
}
_M4_VOWEL1 = {
    "word_id": "55:7:2", "word_text": "رَفَعَهَا",
    "type": "vowel_error", "recited_text": _C4_ERR[14],
    "details": "Fatha (َ) on rā recited as damma (ُ); fatha on fā recited as kasra (ِ)",
    "letter_feedback": _LF_W14_VOWEL,
}
_M4_VOWEL2 = {
    "word_id": "55:7:4", "word_text": "الْمِيزَانَ",
    "type": "vowel_error", "recited_text": _C4_ERR[16],
    "details": "Kasra (ِ) on mīm recited as fatha (َ) — vowel of mīm changed",
    "letter_feedback": _LF_W16_VOWEL,
}


def _c4_tx(cursor: int) -> str:
    """Cumulative transcription for Case 4 (uses recited forms for error words)."""
    return " ".join(_C4_ERR.get(i, WORDS[i]["text"]) for i in range(cursor + 1))


def _c4(ci, cursor, ayah, pos, complete, mistakes):
    return {
        "type": "feedback",
        "chunk_index": ci,
        "transcribed_text": _c4_tx(cursor),
        "current_ayah": ayah,
        "word_cursor": cursor,
        "position_in_verse": pos,
        "ayah_complete": complete,
        "skipped_ayahs": [],
        "repeated_ayahs": [],
        "word_feedback": _wf(cursor, _C4_OVR),
        "mistakes": mistakes,
    }


_C4_CHUNKS = [
    _c4(1,  0,  1, 0.05, True,  []),
    _c4(2,  1,  2, 0.10, False, [_M4_DIAC1]),           # word 1: diacritic
    _c4(3,  2,  2, 0.14, True,  [_M4_DIAC1]),
    _c4(4,  3,  3, 0.19, False, [_M4_DIAC1]),
    _c4(5,  4,  3, 0.24, True,  [_M4_DIAC1]),
    _c4(6,  5,  4, 0.29, False, [_M4_DIAC1, _M4_DIAC2]), # word 5: diacritic
    _c4(7,  6,  4, 0.33, True,  [_M4_DIAC1, _M4_DIAC2]),
    _c4(8,  7,  5, 0.38, False, [_M4_DIAC1, _M4_DIAC2]),
    _c4(9,  8,  5, 0.43, False, [_M4_DIAC1, _M4_DIAC2]),
    _c4(10, 9,  5, 0.48, True,  [_M4_DIAC1, _M4_DIAC2]),
    _c4(11, 10, 6, 0.52, False, [_M4_DIAC1, _M4_DIAC2]),
    _c4(12, 11, 6, 0.57, False, [_M4_DIAC1, _M4_DIAC2]),
    _c4(13, 12, 6, 0.62, True,  [_M4_DIAC1, _M4_DIAC2, _M4_DIAC3]), # word 12
    _c4(14, 13, 7, 0.67, False, [_M4_DIAC1, _M4_DIAC2, _M4_DIAC3]),
    _c4(15, 14, 7, 0.71, False, [_M4_DIAC1, _M4_DIAC2, _M4_DIAC3, _M4_VOWEL1]), # word 14
    _c4(16, 15, 7, 0.76, False, [_M4_DIAC1, _M4_DIAC2, _M4_DIAC3, _M4_VOWEL1]),
    _c4(17, 16, 7, 0.81, True,  [_M4_DIAC1, _M4_DIAC2, _M4_DIAC3, _M4_VOWEL1, _M4_VOWEL2]), # word 16
    {
        "type": "feedback", "chunk_index": 18,
        "transcribed_text": _c4_tx(18), "current_ayah": 8,
        "word_cursor": 18, "position_in_verse": 0.90, "ayah_complete": False,
        "skipped_ayahs": [], "repeated_ayahs": [],
        "word_feedback": _wf(18, _C4_OVR),
        "mistakes": [_M4_DIAC1, _M4_DIAC2, _M4_DIAC3, _M4_VOWEL1, _M4_VOWEL2],
    },
    {
        "type": "feedback", "chunk_index": 19,
        "transcribed_text": _c4_tx(20), "current_ayah": 8,
        "word_cursor": 20, "position_in_verse": 1.00, "ayah_complete": True,
        "skipped_ayahs": [], "repeated_ayahs": [],
        "word_feedback": _wf(20, _C4_OVR),
        "mistakes": [_M4_DIAC1, _M4_DIAC2, _M4_DIAC3, _M4_VOWEL1, _M4_VOWEL2],
    },
]

_C4_ALL_MISTAKES = [_M4_DIAC1, _M4_DIAC2, _M4_DIAC3, _M4_VOWEL1, _M4_VOWEL2]

_C4_SUMMARY = {
    "type": "session_summary",
    "verse_id": "55:1-8",
    "total_chunks": 19,
    "duration_seconds": 38,
    "full_transcription": _c4_tx(20),
    "total_words": 21,
    "words_correct": 16,
    "words_diacritic_error": 3,
    "words_vowel_error": 2,
    "words_letter_error": 0,
    "words_incorrect": 0,
    "words_not_recited": 0,
    "total_score": 78,
    "completion_percentage": 100,
    "skipped_ayahs": [],
    "repeated_ayahs": [],
    "skip_detail": [],
    "repetition_detail": [],
    "ayah_scores": [
        {"ayah": 1, "score": 100, "words_correct": 1, "words_errors": 0},
        {"ayah": 2, "score": 70,  "words_correct": 1, "words_errors": 1,
         "note": "عَلَّمَ recited without shadda"},
        {"ayah": 3, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 4, "score": 70,  "words_correct": 1, "words_errors": 1,
         "note": "عَلَّمَهُ recited without damma on hā"},
        {"ayah": 5, "score": 100, "words_correct": 3, "words_errors": 0},
        {"ayah": 6, "score": 80,  "words_correct": 2, "words_errors": 1,
         "note": "يَسْجُدَانِ — kasra on nūn changed to fatha"},
        {"ayah": 7, "score": 60,  "words_correct": 2, "words_errors": 2,
         "note": "رَفَعَهَا and الْمِيزَانَ have wrong vowels"},
        {"ayah": 8, "score": 100, "words_correct": 4, "words_errors": 0},
    ],
    "mistakes": _C4_ALL_MISTAKES,
    "overall_feedback": (
        "Good effort! 5 harakat mistakes found: 3 diacritical errors and 2 vowel "
        "errors. Focus on the shadda in عَلَّمَ, the damma ending of عَلَّمَهُ, "
        "the kasra on يَسْجُدَانِ, and the vowels in رَفَعَهَا and الْمِيزَانَ."
    ),
    "recording": _recording(4, 38),
}


# ─────────────────────────────────────────────────────────────────────────────
# Case 5 – Letter-level mistakes (2 consonant substitutions + 2 vowel errors)
#
# Scenario: User completes all 8 ayahs but makes actual letter-substitution
# mistakes (wrong consonants) in addition to short-vowel errors.
#
# Mistakes:
#   Word  3  (خَلَقَ)      – letter_error: خ (kha) → ح (ha)   → "حَلَقَ"
#   Word  8  (وَالْقَمَرُ) – letter_error: ق (qāf) → غ (ghain)→ "وَالْغَمَرُ"
#   Word 10  (وَالنَّجْمُ) – vowel_error:  damma ُ on mīm → kasra ِ → "وَالنَّجْمِ"
#   Word 15  (وَوَضَعَ)    – vowel_error:  fatha َ on ḍad → kasra ِ → "وَوَضِعَ"
# ─────────────────────────────────────────────────────────────────────────────

_C5_STATUS = {
    "type": "status",
    "verse_id": "55:1-8",
    "message": "Session started. Ready to receive audio.",
    "total_words": 21,
    "total_ayahs": 8,
}

_C5_ERR = {
    3:  "حَلَقَ",
    8:  "وَالْغَمَرُ",
    10: "وَالنَّجْمِ",
    15: "وَوَضِعَ",
}

_C5_OVR = {
    3:  ("letter_error", _C5_ERR[3],  _LF_W3_LETTER),
    8:  ("letter_error", _C5_ERR[8],  _LF_W8_LETTER),
    10: ("vowel_error",  _C5_ERR[10], _LF_W10_VOWEL),
    15: ("vowel_error",  _C5_ERR[15], _LF_W15_VOWEL),
}

_M5_LETTER1 = {
    "word_id": "55:3:1", "word_text": "خَلَقَ",
    "type": "letter_error", "recited_text": _C5_ERR[3],
    "details": "خ (kha) recited as ح (ha) — velar fricative confused with pharyngeal",
    "letter_feedback": _LF_W3_LETTER,
}
_M5_LETTER2 = {
    "word_id": "55:5:2", "word_text": "وَالْقَمَرُ",
    "type": "letter_error", "recited_text": _C5_ERR[8],
    "details": "ق (qāf) recited as غ (ghain) — uvular stop confused with voiced velar fricative",
    "letter_feedback": _LF_W8_LETTER,
}
_M5_VOWEL1 = {
    "word_id": "55:6:1", "word_text": "وَالنَّجْمُ",
    "type": "vowel_error", "recited_text": _C5_ERR[10],
    "details": "Damma (ُ) on mīm recited as kasra (ِ) — vowel harmony error",
    "letter_feedback": _LF_W10_VOWEL,
}
_M5_VOWEL2 = {
    "word_id": "55:7:3", "word_text": "وَوَضَعَ",
    "type": "vowel_error", "recited_text": _C5_ERR[15],
    "details": "Fatha (َ) on ḍad recited as kasra (ِ) — vowel of ḍad changed",
    "letter_feedback": _LF_W15_VOWEL,
}


def _c5_tx(cursor: int) -> str:
    """Cumulative transcription for Case 5 (uses recited forms for error words)."""
    return " ".join(_C5_ERR.get(i, WORDS[i]["text"]) for i in range(cursor + 1))


def _c5(ci, cursor, ayah, pos, complete, mistakes):
    return {
        "type": "feedback",
        "chunk_index": ci,
        "transcribed_text": _c5_tx(cursor),
        "current_ayah": ayah,
        "word_cursor": cursor,
        "position_in_verse": pos,
        "ayah_complete": complete,
        "skipped_ayahs": [],
        "repeated_ayahs": [],
        "word_feedback": _wf(cursor, _C5_OVR),
        "mistakes": mistakes,
    }


_C5_CHUNKS = [
    _c5(1,  0,  1, 0.05, True,  []),
    _c5(2,  1,  2, 0.10, False, []),
    _c5(3,  2,  2, 0.14, True,  []),
    _c5(4,  3,  3, 0.19, False, [_M5_LETTER1]),          # word 3: letter error
    _c5(5,  4,  3, 0.24, True,  [_M5_LETTER1]),
    _c5(6,  5,  4, 0.29, False, [_M5_LETTER1]),
    _c5(7,  6,  4, 0.33, True,  [_M5_LETTER1]),
    _c5(8,  7,  5, 0.38, False, [_M5_LETTER1]),
    _c5(9,  8,  5, 0.43, False, [_M5_LETTER1, _M5_LETTER2]), # word 8: letter error
    _c5(10, 9,  5, 0.48, True,  [_M5_LETTER1, _M5_LETTER2]),
    _c5(11, 10, 6, 0.52, False, [_M5_LETTER1, _M5_LETTER2, _M5_VOWEL1]), # word 10: vowel
    _c5(12, 11, 6, 0.57, False, [_M5_LETTER1, _M5_LETTER2, _M5_VOWEL1]),
    _c5(13, 12, 6, 0.62, True,  [_M5_LETTER1, _M5_LETTER2, _M5_VOWEL1]),
    _c5(14, 13, 7, 0.67, False, [_M5_LETTER1, _M5_LETTER2, _M5_VOWEL1]),
    _c5(15, 14, 7, 0.71, False, [_M5_LETTER1, _M5_LETTER2, _M5_VOWEL1]),
    _c5(16, 15, 7, 0.76, False, [_M5_LETTER1, _M5_LETTER2, _M5_VOWEL1, _M5_VOWEL2]), # word 15: vowel
    _c5(17, 16, 7, 0.81, True,  [_M5_LETTER1, _M5_LETTER2, _M5_VOWEL1, _M5_VOWEL2]),
    {
        "type": "feedback", "chunk_index": 18,
        "transcribed_text": _c5_tx(18), "current_ayah": 8,
        "word_cursor": 18, "position_in_verse": 0.90, "ayah_complete": False,
        "skipped_ayahs": [], "repeated_ayahs": [],
        "word_feedback": _wf(18, _C5_OVR),
        "mistakes": [_M5_LETTER1, _M5_LETTER2, _M5_VOWEL1, _M5_VOWEL2],
    },
    {
        "type": "feedback", "chunk_index": 19,
        "transcribed_text": _c5_tx(20), "current_ayah": 8,
        "word_cursor": 20, "position_in_verse": 1.00, "ayah_complete": True,
        "skipped_ayahs": [], "repeated_ayahs": [],
        "word_feedback": _wf(20, _C5_OVR),
        "mistakes": [_M5_LETTER1, _M5_LETTER2, _M5_VOWEL1, _M5_VOWEL2],
    },
]

_C5_ALL_MISTAKES = [_M5_LETTER1, _M5_LETTER2, _M5_VOWEL1, _M5_VOWEL2]

_C5_SUMMARY = {
    "type": "session_summary",
    "verse_id": "55:1-8",
    "total_chunks": 19,
    "duration_seconds": 38,
    "full_transcription": _c5_tx(20),
    "total_words": 21,
    "words_correct": 17,
    "words_diacritic_error": 0,
    "words_vowel_error": 2,
    "words_letter_error": 2,
    "words_incorrect": 0,
    "words_not_recited": 0,
    "total_score": 65,
    "completion_percentage": 100,
    "skipped_ayahs": [],
    "repeated_ayahs": [],
    "skip_detail": [],
    "repetition_detail": [],
    "ayah_scores": [
        {"ayah": 1, "score": 100, "words_correct": 1, "words_errors": 0},
        {"ayah": 2, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 3, "score": 50,  "words_correct": 1, "words_errors": 1,
         "note": "خَلَقَ — kha recited as ha (letter substitution)"},
        {"ayah": 4, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 5, "score": 67,  "words_correct": 2, "words_errors": 1,
         "note": "وَالْقَمَرُ — qāf recited as ghain (letter substitution)"},
        {"ayah": 6, "score": 80,  "words_correct": 2, "words_errors": 1,
         "note": "وَالنَّجْمُ — damma on mīm recited as kasra"},
        {"ayah": 7, "score": 75,  "words_correct": 3, "words_errors": 1,
         "note": "وَوَضَعَ — fatha on ḍad recited as kasra"},
        {"ayah": 8, "score": 100, "words_correct": 4, "words_errors": 0},
    ],
    "mistakes": _C5_ALL_MISTAKES,
    "overall_feedback": (
        "4 mistakes detected: 2 letter substitutions and 2 short-vowel errors. "
        "Critical: خ in خَلَقَ was pronounced as ح — practice the kha sound. "
        "ق in وَالْقَمَرُ was pronounced as غ — focus on the uvular stop. "
        "Also review short vowels on وَالنَّجْمُ and وَوَضَعَ."
    ),
    "recording": _recording(5, 38),
}


# ─────────────────────────────────────────────────────────────────────────────
# Case 6 – Mixed mistakes: incorrect word + letter error + diacritic + vowel
#
# Scenario: User completes all 8 ayahs with one mistake from each major
# category, spread across different ayahs.
#
# Mistakes:
#   Word  4  (الْإِنسَانَ) – incorrect:       recited as "الانس" (truncated)
#   Word  7  (الشَّمْسُ)  – letter_error:     ش (shin) → ص (sad)  → "الصَّمْسُ"
#   Word 11  (وَالشَّجَرُ)– diacritic_error:  shadda on شَّ missing → "وَالشَجَرُ"
#   Word 17  (أَلَّا)     – vowel_error:      fatha on أ → kasra   → "إِلَّا"
# ─────────────────────────────────────────────────────────────────────────────

# ── Case 6 letter feedback ────────────────────────────────────────────────────

# Word 7 · الشَّمْسُ  → "الصَّمْسُ"  (shin ش substituted by sad ص)
# letters: ["ا","ل","ش","َّ","م","ْ","س","ُ"]
_LF_W7_C6_LETTER = [
    {"position": 0, "expected_letter": "ا",  "recited_letter": "ا",  "status": "correct"},
    {"position": 1, "expected_letter": "ل",  "recited_letter": "ل",  "status": "correct"},
    {"position": 2, "expected_letter": "ش",  "recited_letter": "ص",  "status": "letter_error"},
    {"position": 3, "expected_letter": "َّ", "recited_letter": "َّ", "status": "correct"},
    {"position": 4, "expected_letter": "م",  "recited_letter": "م",  "status": "correct"},
    {"position": 5, "expected_letter": "ْ",  "recited_letter": "ْ",  "status": "correct"},
    {"position": 6, "expected_letter": "س",  "recited_letter": "س",  "status": "correct"},
    {"position": 7, "expected_letter": "ُ",  "recited_letter": "ُ",  "status": "correct"},
]

# Word 11 · وَالشَّجَرُ  → "وَالشَجَرُ"  (shadda on shin dropped)
# letters: ["و","َ","ا","ل","ش","َّ","ج","َ","ر","ُ"]
_LF_W11_C6_DIAC = [
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

# Word 17 · أَلَّا  → "إِلَّا"  (fatha on hamza → kasra)
# letters: ["أ","َ","ل","َّ","ا"]
_LF_W17_C6_VOWEL = [
    {"position": 0, "expected_letter": "أ",  "recited_letter": "أ",  "status": "correct"},
    {"position": 1, "expected_letter": "َ",  "recited_letter": "ِ",  "status": "vowel_error"},
    {"position": 2, "expected_letter": "ل",  "recited_letter": "ل",  "status": "correct"},
    {"position": 3, "expected_letter": "َّ", "recited_letter": "َّ", "status": "correct"},
    {"position": 4, "expected_letter": "ا",  "recited_letter": "ا",  "status": "correct"},
]

_C6_STATUS = {
    "type": "status",
    "verse_id": "55:1-8",
    "message": "Session started. Ready to receive audio.",
    "total_words": 21,
    "total_ayahs": 8,
}

_C6_ERR = {
    4:  "الانس",
    7:  "الصَّمْسُ",
    11: "وَالشَجَرُ",
    17: "إِلَّا",
}

_C6_OVR = {
    4:  ("incorrect",       _C6_ERR[4],  None),
    7:  ("letter_error",    _C6_ERR[7],  _LF_W7_C6_LETTER),
    11: ("diacritic_error", _C6_ERR[11], _LF_W11_C6_DIAC),
    17: ("vowel_error",     _C6_ERR[17], _LF_W17_C6_VOWEL),
}

# Mistake objects for Case 6
_M6_INCR = {
    "word_id": "55:3:2", "word_text": "الْإِنسَانَ",
    "type": "incorrect", "recited_text": _C6_ERR[4],
    "details": "Word truncated — 'الانس' recited instead of الْإِنسَانَ",
}
_M6_LETTER = {
    "word_id": "55:5:1", "word_text": "الشَّمْسُ",
    "type": "letter_error", "recited_text": _C6_ERR[7],
    "details": "ش (shin) recited as ص (sad) — emphatic substitution",
    "letter_feedback": _LF_W7_C6_LETTER,
}
_M6_DIAC = {
    "word_id": "55:6:2", "word_text": "وَالشَّجَرُ",
    "type": "diacritic_error", "recited_text": _C6_ERR[11],
    "details": "Shadda (ّ) missing on shin — وَالشَّجَرُ shortened to وَالشَجَرُ",
    "letter_feedback": _LF_W11_C6_DIAC,
}
_M6_VOWEL = {
    "word_id": "55:8:1", "word_text": "أَلَّا",
    "type": "vowel_error", "recited_text": _C6_ERR[17],
    "details": "Fatha (َ) on hamza recited as kasra (ِ) — أَلَّا became إِلَّا",
    "letter_feedback": _LF_W17_C6_VOWEL,
}


def _c6_tx(cursor: int) -> str:
    return " ".join(_C6_ERR.get(i, WORDS[i]["text"]) for i in range(cursor + 1))


def _c6(ci, cursor, ayah, pos, complete, mistakes):
    return {
        "type": "feedback",
        "chunk_index": ci,
        "transcribed_text": _c6_tx(cursor),
        "current_ayah": ayah,
        "word_cursor": cursor,
        "position_in_verse": pos,
        "ayah_complete": complete,
        "skipped_ayahs": [],
        "repeated_ayahs": [],
        "word_feedback": _wf(cursor, _C6_OVR),
        "mistakes": mistakes,
    }


_C6_CHUNKS = [
    _c6(1,  0,  1, 0.05, True,  []),
    _c6(2,  1,  2, 0.10, False, []),
    _c6(3,  2,  2, 0.14, True,  []),
    _c6(4,  3,  3, 0.19, False, []),
    _c6(5,  4,  3, 0.24, True,  [_M6_INCR]),              # word 4: incorrect
    _c6(6,  5,  4, 0.29, False, [_M6_INCR]),
    _c6(7,  6,  4, 0.33, True,  [_M6_INCR]),
    _c6(8,  7,  5, 0.38, False, [_M6_INCR, _M6_LETTER]),  # word 7: letter error
    _c6(9,  8,  5, 0.43, False, [_M6_INCR, _M6_LETTER]),
    _c6(10, 9,  5, 0.48, True,  [_M6_INCR, _M6_LETTER]),
    _c6(11, 10, 6, 0.52, False, [_M6_INCR, _M6_LETTER]),
    _c6(12, 11, 6, 0.57, False, [_M6_INCR, _M6_LETTER, _M6_DIAC]),  # word 11: diacritic
    _c6(13, 12, 6, 0.62, True,  [_M6_INCR, _M6_LETTER, _M6_DIAC]),
    _c6(14, 13, 7, 0.67, False, [_M6_INCR, _M6_LETTER, _M6_DIAC]),
    _c6(15, 14, 7, 0.71, False, [_M6_INCR, _M6_LETTER, _M6_DIAC]),
    _c6(16, 15, 7, 0.76, False, [_M6_INCR, _M6_LETTER, _M6_DIAC]),
    _c6(17, 16, 7, 0.81, True,  [_M6_INCR, _M6_LETTER, _M6_DIAC]),
    _c6(18, 17, 8, 0.86, False, [_M6_INCR, _M6_LETTER, _M6_DIAC, _M6_VOWEL]),  # word 17: vowel
    _c6(19, 18, 8, 0.90, False, [_M6_INCR, _M6_LETTER, _M6_DIAC, _M6_VOWEL]),
    _c6(20, 19, 8, 0.95, False, [_M6_INCR, _M6_LETTER, _M6_DIAC, _M6_VOWEL]),
    _c6(21, 20, 8, 1.00, True,  [_M6_INCR, _M6_LETTER, _M6_DIAC, _M6_VOWEL]),
]

_C6_ALL_MISTAKES = [_M6_INCR, _M6_LETTER, _M6_DIAC, _M6_VOWEL]

_C6_SUMMARY = {
    "type": "session_summary",
    "verse_id": "55:1-8",
    "total_chunks": 21,
    "duration_seconds": 40,
    "full_transcription": _c6_tx(20),
    "total_words": 21,
    "words_correct": 17,
    "words_diacritic_error": 1,
    "words_vowel_error": 1,
    "words_letter_error": 1,
    "words_incorrect": 1,
    "words_not_recited": 0,
    "total_score": 80,
    "completion_percentage": 100,
    "skipped_ayahs": [],
    "repeated_ayahs": [],
    "skip_detail": [],
    "repetition_detail": [],
    "ayah_scores": [
        {"ayah": 1, "score": 100, "words_correct": 1, "words_errors": 0},
        {"ayah": 2, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 3, "score": 50,  "words_correct": 1, "words_errors": 1,
         "note": "الْإِنسَانَ recited incorrectly as 'الانس'"},
        {"ayah": 4, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 5, "score": 67,  "words_correct": 2, "words_errors": 1,
         "note": "الشَّمْسُ — shin (ش) recited as sad (ص)"},
        {"ayah": 6, "score": 67,  "words_correct": 2, "words_errors": 1,
         "note": "وَالشَّجَرُ — shadda on shin missing"},
        {"ayah": 7, "score": 100, "words_correct": 4, "words_errors": 0},
        {"ayah": 8, "score": 75,  "words_correct": 3, "words_errors": 1,
         "note": "أَلَّا — fatha on hamza recited as kasra"},
    ],
    "mistakes": _C6_ALL_MISTAKES,
    "overall_feedback": (
        "4 mistakes across 4 different categories: "
        "الْإِنسَانَ was truncated to 'الانس'; "
        "ش in الشَّمْسُ was substituted with ص; "
        "shadda was dropped from وَالشَّجَرُ; "
        "and فتحة on أَلَّا was recited as كسرة. "
        "Good completion — focus on letter precision and diacritics."
    ),
    "recording": _recording(6, 40),
}


# ─────────────────────────────────────────────────────────────────────────────
# Case 7 – Heavy mixed mistakes: incorrect + letter + 2 diacritics + vowel
#
# Scenario: User completes all 8 ayahs with five mistakes spread across
# multiple error types and ayahs.
#
# Mistakes:
#   Word  2  (الْقُرْآنَ)  – incorrect:       recited as "القراء"
#   Word  6  (الْبَيَانَ)  – letter_error:     ب (ba) → ف (fa)      → "الْفَيَانَ"
#   Word  9  (بِحُسْبَانٍ) – diacritic_error:  tanwīn kasra ٍ dropped → "بِحُسْبَانَ"
#   Word 12  (يَسْجُدَانِ) – diacritic_error:  sukūn ْ on sīn dropped → "يَسَجُدَانِ"
#   Word 16  (الْمِيزَانَ) – vowel_error:      kasra ِ on mīm → damma ُ → "الْمُيزَانَ"
# ─────────────────────────────────────────────────────────────────────────────

# ── Case 7 letter feedback ────────────────────────────────────────────────────

# Word 6 · الْبَيَانَ  → "الْفَيَانَ"  (ba ب substituted by fa ف)
# letters: ["ا","ل","ْ","ب","َ","ي","َ","ا","ن","َ"]
_LF_W6_C7_LETTER = [
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

# Word 9 · بِحُسْبَانٍ  → "بِحُسْبَانَ"  (tanwīn kasra ٍ dropped)
# letters: ["ب","ِ","ح","ُ","س","ْ","ب","َ","ا","ن","ٍ"]
_LF_W9_C7_DIAC = [
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

# Word 12 · يَسْجُدَانِ  → "يَسَجُدَانِ"  (sukūn ْ on sīn dropped)
# letters: ["ي","َ","س","ْ","ج","ُ","د","َ","ا","ن","ِ"]
_LF_W12_C7_DIAC = [
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

# Word 16 · الْمِيزَانَ  → "الْمُيزَانَ"  (kasra ِ on mīm → damma ُ)
# letters: ["ا","ل","ْ","م","ِ","ي","ز","َ","ا","ن","َ"]
_LF_W16_C7_VOWEL = [
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

_C7_STATUS = {
    "type": "status",
    "verse_id": "55:1-8",
    "message": "Session started. Ready to receive audio.",
    "total_words": 21,
    "total_ayahs": 8,
}

_C7_ERR = {
    2:  "القراء",
    6:  "الْفَيَانَ",
    9:  "بِحُسْبَانَ",
    12: "يَسَجُدَانِ",
    16: "الْمُيزَانَ",
}

_C7_OVR = {
    2:  ("incorrect",       _C7_ERR[2],  None),
    6:  ("letter_error",    _C7_ERR[6],  _LF_W6_C7_LETTER),
    9:  ("diacritic_error", _C7_ERR[9],  _LF_W9_C7_DIAC),
    12: ("diacritic_error", _C7_ERR[12], _LF_W12_C7_DIAC),
    16: ("vowel_error",     _C7_ERR[16], _LF_W16_C7_VOWEL),
}

# Mistake objects for Case 7
_M7_INCR = {
    "word_id": "55:2:2", "word_text": "الْقُرْآنَ",
    "type": "incorrect", "recited_text": _C7_ERR[2],
    "details": "الْقُرْآنَ recited as 'القراء' — wrong word form",
}
_M7_LETTER = {
    "word_id": "55:4:2", "word_text": "الْبَيَانَ",
    "type": "letter_error", "recited_text": _C7_ERR[6],
    "details": "ب (ba) recited as ف (fa) — bilabial/labiodental confusion",
    "letter_feedback": _LF_W6_C7_LETTER,
}
_M7_DIAC1 = {
    "word_id": "55:5:3", "word_text": "بِحُسْبَانٍ",
    "type": "diacritic_error", "recited_text": _C7_ERR[9],
    "details": "Tanwīn kasra (ٍ) missing at end — word ends without nunation",
    "letter_feedback": _LF_W9_C7_DIAC,
}
_M7_DIAC2 = {
    "word_id": "55:6:3", "word_text": "يَسْجُدَانِ",
    "type": "diacritic_error", "recited_text": _C7_ERR[12],
    "details": "Sukūn (ْ) missing on sīn — يَسْجُدَانِ recited as يَسَجُدَانِ",
    "letter_feedback": _LF_W12_C7_DIAC,
}
_M7_VOWEL = {
    "word_id": "55:7:4", "word_text": "الْمِيزَانَ",
    "type": "vowel_error", "recited_text": _C7_ERR[16],
    "details": "Kasra (ِ) on mīm recited as damma (ُ) — الْمِيزَانَ became الْمُيزَانَ",
    "letter_feedback": _LF_W16_C7_VOWEL,
}


def _c7_tx(cursor: int) -> str:
    return " ".join(_C7_ERR.get(i, WORDS[i]["text"]) for i in range(cursor + 1))


def _c7(ci, cursor, ayah, pos, complete, mistakes):
    return {
        "type": "feedback",
        "chunk_index": ci,
        "transcribed_text": _c7_tx(cursor),
        "current_ayah": ayah,
        "word_cursor": cursor,
        "position_in_verse": pos,
        "ayah_complete": complete,
        "skipped_ayahs": [],
        "repeated_ayahs": [],
        "word_feedback": _wf(cursor, _C7_OVR),
        "mistakes": mistakes,
    }


_C7_CHUNKS = [
    _c7(1,  0,  1, 0.05, True,  []),
    _c7(2,  1,  2, 0.10, False, []),
    _c7(3,  2,  2, 0.14, True,  [_M7_INCR]),               # word 2: incorrect
    _c7(4,  3,  3, 0.19, False, [_M7_INCR]),
    _c7(5,  4,  3, 0.24, True,  [_M7_INCR]),
    _c7(6,  5,  4, 0.29, False, [_M7_INCR]),
    _c7(7,  6,  4, 0.33, True,  [_M7_INCR, _M7_LETTER]),   # word 6: letter error
    _c7(8,  7,  5, 0.38, False, [_M7_INCR, _M7_LETTER]),
    _c7(9,  8,  5, 0.43, False, [_M7_INCR, _M7_LETTER]),
    _c7(10, 9,  5, 0.48, True,  [_M7_INCR, _M7_LETTER, _M7_DIAC1]),  # word 9: diacritic
    _c7(11, 10, 6, 0.52, False, [_M7_INCR, _M7_LETTER, _M7_DIAC1]),
    _c7(12, 11, 6, 0.57, False, [_M7_INCR, _M7_LETTER, _M7_DIAC1]),
    _c7(13, 12, 6, 0.62, True,  [_M7_INCR, _M7_LETTER, _M7_DIAC1, _M7_DIAC2]),  # word 12: diacritic
    _c7(14, 13, 7, 0.67, False, [_M7_INCR, _M7_LETTER, _M7_DIAC1, _M7_DIAC2]),
    _c7(15, 14, 7, 0.71, False, [_M7_INCR, _M7_LETTER, _M7_DIAC1, _M7_DIAC2]),
    _c7(16, 15, 7, 0.76, False, [_M7_INCR, _M7_LETTER, _M7_DIAC1, _M7_DIAC2]),
    _c7(17, 16, 7, 0.81, True,  [_M7_INCR, _M7_LETTER, _M7_DIAC1, _M7_DIAC2, _M7_VOWEL]),  # word 16: vowel
    _c7(18, 17, 8, 0.86, False, [_M7_INCR, _M7_LETTER, _M7_DIAC1, _M7_DIAC2, _M7_VOWEL]),
    _c7(19, 18, 8, 0.90, False, [_M7_INCR, _M7_LETTER, _M7_DIAC1, _M7_DIAC2, _M7_VOWEL]),
    _c7(20, 19, 8, 0.95, False, [_M7_INCR, _M7_LETTER, _M7_DIAC1, _M7_DIAC2, _M7_VOWEL]),
    _c7(21, 20, 8, 1.00, True,  [_M7_INCR, _M7_LETTER, _M7_DIAC1, _M7_DIAC2, _M7_VOWEL]),
]

_C7_ALL_MISTAKES = [_M7_INCR, _M7_LETTER, _M7_DIAC1, _M7_DIAC2, _M7_VOWEL]

_C7_SUMMARY = {
    "type": "session_summary",
    "verse_id": "55:1-8",
    "total_chunks": 21,
    "duration_seconds": 40,
    "full_transcription": _c7_tx(20),
    "total_words": 21,
    "words_correct": 16,
    "words_diacritic_error": 2,
    "words_vowel_error": 1,
    "words_letter_error": 1,
    "words_incorrect": 1,
    "words_not_recited": 0,
    "total_score": 68,
    "completion_percentage": 100,
    "skipped_ayahs": [],
    "repeated_ayahs": [],
    "skip_detail": [],
    "repetition_detail": [],
    "ayah_scores": [
        {"ayah": 1, "score": 100, "words_correct": 1, "words_errors": 0},
        {"ayah": 2, "score": 50,  "words_correct": 1, "words_errors": 1,
         "note": "الْقُرْآنَ recited incorrectly as 'القراء'"},
        {"ayah": 3, "score": 100, "words_correct": 2, "words_errors": 0},
        {"ayah": 4, "score": 50,  "words_correct": 1, "words_errors": 1,
         "note": "الْبَيَانَ — ba (ب) recited as fa (ف)"},
        {"ayah": 5, "score": 67,  "words_correct": 2, "words_errors": 1,
         "note": "بِحُسْبَانٍ — tanwīn kasra dropped at end"},
        {"ayah": 6, "score": 67,  "words_correct": 2, "words_errors": 1,
         "note": "يَسْجُدَانِ — sukūn on sīn dropped, adding extra syllable"},
        {"ayah": 7, "score": 75,  "words_correct": 3, "words_errors": 1,
         "note": "الْمِيزَانَ — kasra on mīm recited as damma"},
        {"ayah": 8, "score": 100, "words_correct": 4, "words_errors": 0},
    ],
    "mistakes": _C7_ALL_MISTAKES,
    "overall_feedback": (
        "5 mistakes detected across multiple types: "
        "الْقُرْآنَ was replaced with an incorrect word; "
        "ب in الْبَيَانَ was pronounced as ف; "
        "tanwīn was dropped from بِحُسْبَانٍ; "
        "sukūn was omitted from يَسْجُدَانِ causing an extra syllable; "
        "and kasra on الْمِيزَانَ was raised to damma. "
        "Review letter accuracy and nunation rules carefully."
    ),
    "recording": _recording(7, 40),
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
}
