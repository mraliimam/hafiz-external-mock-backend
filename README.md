# Hafiz Mock Backend

A lightweight mock server for frontend developers.  
No ML models, no database — just pre-built JSON responses that match the
real backend API exactly.

---

## Setup

```bash
cd mock_backend

# Install dependencies (works on Windows, macOS, Linux)
pip install -r requirements.txt

# Start the server
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

Server is now live at `http://localhost:8000`.

---

## Endpoints

### REST

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/verses` | Returns the verse list (Surah Ar-Rahman 55:1–8) |
| `GET` | `/api/recordings/{use_case}` | Download mock WAV audio for a session (use_case 1–5) |
| `GET` | `/health` | Health check |

### WebSocket

```
ws://localhost:8000/ws/recitation
```

---

## Use-Case Selection

The `use_case` field is sent in the **`start`** message.
The server will replay the matching pre-recorded response sequence.

| `use_case` | Scenario | Mistake types |
|------------|----------|---------------|
| `1` | Smooth recitation — 1 diacritic error + 1 incorrect word | `diacritic_error`, `incorrect` |
| `2` | User repeats Ayah 1 before continuing | — (perfect recitation, repetition flag) |
| `3` | User skips Ayah 2 and jumps to Ayah 3 | — (skip flag, 2 `not_recited` words) |
| `4` | Heavy harakat mistakes — 3 diacritic + 2 vowel errors | `diacritic_error`, `vowel_error` |
| `5` | Letter-level mistakes — 2 consonant substitutions + 2 vowel errors | `letter_error`, `vowel_error` |

---

## Word-Feedback Status Values

Each word in the `word_feedback` array carries a `status` field:

| `status` | Meaning |
|----------|---------|
| `correct` | Base consonants **and** all harakat match perfectly |
| `diacritic_error` | Base consonants correct; a non-vowel diacritic is wrong or missing (shadda ّ, tanwin ٍ, sukun ْ …) |
| `vowel_error` | Base consonants correct; a **short vowel** is wrong (fatha ↔ kasra ↔ damma) |
| `letter_error` | A specific **consonant** is substituted (e.g. خ recited as ح) |
| `incorrect` | Wrong word entirely — consonants differ significantly |
| `not_recited` | Word not yet reached or deliberately skipped |

### Letter-level feedback

Words with `status` of `vowel_error` or `letter_error` also carry a
`letter_feedback` array that pins the mistake to the exact letter position:

```json
{
  "word_id": "55:3:1",
  "word_text": "خَلَقَ",
  "status": "letter_error",
  "recited_text": "حَلَقَ",
  "letter_feedback": [
    { "position": 0, "expected_letter": "خ", "recited_letter": "ح", "status": "letter_error" },
    { "position": 1, "expected_letter": "َ", "recited_letter": "َ", "status": "correct" },
    { "position": 2, "expected_letter": "ل", "recited_letter": "ل", "status": "correct" },
    ...
  ]
}
```

`status` values inside `letter_feedback`: `correct` | `diacritic_error` | `vowel_error` | `letter_error`

---

## Session Summary — Recording Field

Every `session_summary` message includes a `recording` block so the
frontend can let the user play back the session audio:

```json
{
  "type": "session_summary",
  ...
  "recording": {
    "audio_data":       "<base64-encoded WAV>",
    "audio_format":     "wav",
    "audio_size_bytes": 32044,
    "duration_seconds": 38,
    "filename":         "recitation_case_1.wav",
    "download_url":     "/api/recordings/1"
  }
}
```

**Two ways to play the audio:**

1. **Inline base64** — decode `recording.audio_data` directly into a Blob:
   ```js
   const bytes = Uint8Array.from(atob(summary.recording.audio_data), c => c.charCodeAt(0));
   const blob  = new Blob([bytes], { type: "audio/wav" });
   const url   = URL.createObjectURL(blob);
   document.querySelector("audio").src = url;
   ```

2. **REST download** — link to `recording.download_url`:
   ```js
   window.open(`http://localhost:8000${summary.recording.download_url}`);
   ```

> The mock WAV is a short 1-second sine-wave tone (different pitch per
> use case). Replace with real recorded audio in production.

---

## Summary Word-Count Fields

| Field | Counts |
|-------|--------|
| `words_correct` | Only truly correct words |
| `words_diacritic_error` | Non-vowel diacritic mistakes |
| `words_vowel_error` | Short-vowel mistakes |
| `words_letter_error` | Consonant substitution mistakes |
| `words_incorrect` | Completely wrong word |
| `words_not_recited` | Skipped or unreached |

---

## Message Flow

```
Frontend                              Mock Server
────────                              ───────────
{ type: "start",
  verse_id: "55:1-8",       ──────►  sends  { type: "status", session_id, ... }
  use_case: 1 }

{ type: "audio", audio: "..." }  ──► sends  { type: "feedback", chunk_index: 1, ... }
{ type: "audio", audio: "..." }  ──► sends  { type: "feedback", chunk_index: 2, ... }
        ...                                           ...
{ type: "stop" }             ──────► sends  { type: "session_summary", recording: {...}, ... }
```

> Sending more `audio` messages than there are mock chunks is safe — the server
> simply ignores the extras. All remaining chunks are flushed when `stop` arrives.

---

## Example (JavaScript)

```js
const ws = new WebSocket("ws://localhost:8000/ws/recitation");

ws.onopen = () => {
  ws.send(JSON.stringify({ type: "start", verse_id: "55:1-8", use_case: 5 }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === "status") {
    console.log("Session started:", msg.session_id);
    ws.send(JSON.stringify({ type: "audio", audio: "<base64>" }));
  }

  if (msg.type === "feedback") {
    console.log(`Chunk ${msg.chunk_index} | ayah ${msg.current_ayah} | cursor ${msg.word_cursor}`);

    // Words with letter_error or vowel_error carry per-letter breakdown
    msg.word_feedback.forEach(w => {
      if (w.status === "letter_error" || w.status === "vowel_error") {
        console.log(`  ${w.word_text} → ${w.recited_text}`);
        w.letter_feedback?.forEach(lf => {
          if (lf.status !== "correct")
            console.log(`    pos ${lf.position}: expected '${lf.expected_letter}' got '${lf.recited_letter}'`);
        });
      }
    });

    ws.send(JSON.stringify({ type: "audio", audio: "<base64>" }));
  }

  if (msg.type === "session_summary") {
    console.log("Score:", msg.total_score, "| Mistakes:", msg.mistakes.length);

    // Play back the session recording
    const bytes = Uint8Array.from(atob(msg.recording.audio_data), c => c.charCodeAt(0));
    const blob  = new Blob([bytes], { type: "audio/wav" });
    document.querySelector("audio").src = URL.createObjectURL(blob);

    ws.close();
  }
};
```

---

## Switching Between Use Cases

After receiving `session_summary`, send a new `start` message with a
different `use_case` to begin the next scenario on the same connection.

---

## File Overview

| File | Purpose |
|------|---------|
| `server.py` | FastAPI app — REST + WebSocket handlers |
| `mock_data.py` | All pre-built response sequences for all 5 cases |
| `requirements.txt` | Python dependencies (no `uvloop` — works on Windows) |
