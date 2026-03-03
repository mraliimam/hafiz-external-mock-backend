"""
Hafiz Mock Backend Server
=========================
Mimics the real backend API so frontend developers can test all 12
use-case scenarios without a live ML pipeline.

REST
----
  GET  http://localhost:8000/api/verses                      → verse list
  GET  http://localhost:8000/api/recordings/{use_case}       → download static mock WAV (1–12)
  GET  http://localhost:8000/api/session-recordings/{id}     → download the actual audio
                                                               captured during a session

WebSocket
---------
  ws://localhost:8000/ws/recitation

Flow
----
  1. Frontend opens WS connection.
  2. Frontend sends   { "type": "start", "verse_id": "55:1-8", "use_case": 1 }

     Harakat / letter / word-level mistake cases (1–9):
     • use_case  1 = mixed: 1 vowel + 1 letter + 1 diacritic + 1 incorrect  (4 mistakes)
     • use_case  2 = repeat ayah 1 + 1 diacritic + 1 vowel error             (2 mistakes)
     • use_case  3 = skip ayah 2 + 1 diacritic + 1 letter error              (2 mistakes)
     • use_case  4 = heavy: 1 letter + 3 diacritic + 2 vowel + 1 incorrect   (7 mistakes)
     • use_case  5 = letter focus: 2 letter + 2 vowel + 1 diacritic + 1 incr (6 mistakes)
     • use_case  6 = mixed moderate: 1 incr + 1 letter + 2 diac + 2 vowel    (6 mistakes)
     • use_case  7 = mixed heavy: 2 incr + 1 letter + 2 diac + 2 vowel       (7 mistakes)
     • use_case  8 = severe: 2 incr + 2 letter + 2 diac + 1 vowel            (7 mistakes)
     • use_case  9 = extreme: 1 incr + 3 letter + 2 diac + 2 vowel           (8 mistakes)

     Tajweed / pronunciation (makhraj) cases (10–12):
     • use_case 10 = tajweed – throat (الحلق) makhraj confusion               (4 mistakes)
                     ح/ع confused between upper_throat, middle_throat, lower_throat
     • use_case 11 = tajweed – tongue (اللسان) makhraj + tafkheem             (4 mistakes)
                     ش/ج confused with sibilant; ط recited without tafkheem as ت
     • use_case 12 = tajweed – mixed makhraj: velar/nasal/lips/sibilant        (4 mistakes)
                     ق→ك, ن→ل, ب→م, ز→س — each from a different articulation zone

  3. Server replies with a  status  message.

  4. Frontend sends  { "type": "audio", "audio": "<base64>" }  (one per ~2-second chunk).
     • The server accumulates the raw audio bytes from every chunk.
     • It also sends the next pre-built feedback message from the mock sequence.

  5. Frontend sends  { "type": "stop" }.
     • Server flushes remaining feedback chunks.
     • All accumulated audio bytes are concatenated and stored in memory.
     • session_summary includes a  recording  block with the real base64 audio
       (or the mock sine-wave WAV if no audio data was received).
     • recording.source = "recorded" | "mock"
     • recording.download_url = /api/session-recordings/{session_id}  (real audio)
                              or /api/recordings/{use_case}           (mock WAV)

session_summary fields
----------------------
  • "letter_mistakes"  – diacritic/vowel/letter errors with word_position + letter_feedback
  • "word_mistakes"    – incorrect words with word_position reference
  • "mistakes"         – flat combined list (backward-compat)
  • "tajweed_focus"    – present on cases 10–12; primary makhraj category
                         ("middle_throat" | "tongue_middle" | "mixed_makhraj")

tajweed_detail block  (cases 10–12 only)
-----------------------------------------
  Attached to every tajweed letter_error at two levels:
    • mistake["tajweed_detail"]
    • mistake["letter_feedback"][n]["tajweed_detail"]  (error position only)

  Both "expected_rule" and "recited_rule" carry the full Tajweed_rule.json schema:
    id, name, arabicName, description, letters,
    color (HEX), textColor (HEX), cx, cy, rx, ry

  cx/cy/rx/ry are SVG ellipse coordinates for highlighting articulation zones
  on the interactive mouth/throat diagram in the frontend.
  color/textColor are in HEX format (8-digit #RRGGBBAA where alpha < 1).
"""

import asyncio
import base64
import json
import uuid
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

import mock_data as md

# ─────────────────────────────────────────────────────────────────────────────
# App setup
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Hafiz Mock Backend", version="1.0.0")

# In-memory store for real session recordings.
# Keyed by session_id; capped at _MAX_STORED_SESSIONS to prevent unbounded growth.
_MAX_STORED_SESSIONS = 20
_session_recordings: "OrderedDict[str, Tuple[bytes, str]]" = OrderedDict()
# value = (raw_audio_bytes, mime_type)


def _store_recording(session_id: str, audio_bytes: bytes, mime: str) -> None:
    """Save a recording, evicting the oldest if the store is full."""
    if session_id in _session_recordings:
        _session_recordings.move_to_end(session_id)
    _session_recordings[session_id] = (audio_bytes, mime)
    while len(_session_recordings) > _MAX_STORED_SESSIONS:
        _session_recordings.popitem(last=False)


def _detect_audio_format(data: bytes) -> Tuple[str, str]:
    """Return (mime_type, file_extension) by inspecting magic bytes."""
    if data[:4] == b"RIFF":
        return "audio/wav", "wav"
    if data[:4] == b"OggS":
        return "audio/ogg", "ogg"
    if data[:3] == b"ID3" or data[:2] == b"\xff\xfb":
        return "audio/mpeg", "mp3"
    # WebM / MKV EBML magic
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "audio/webm", "webm"
    # Default: assume WebM (most common from browser MediaRecorder)
    return "audio/webm", "webm"


def _build_real_recording(
    session_id: str,
    audio_bytes: bytes,
    duration_seconds: int,
    use_case: int,
) -> dict:
    """Build the recording block from the actual captured audio."""
    mime, ext = _detect_audio_format(audio_bytes)
    return {
        "audio_data":       base64.b64encode(audio_bytes).decode("ascii"),
        "audio_format":     ext,
        "audio_size_bytes": len(audio_bytes),
        "duration_seconds": duration_seconds,
        "filename":         f"recitation_{session_id[:8]}.{ext}",
        "download_url":     f"/api/session-recordings/{session_id}",
        "source":           "recorded",
    }


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# REST
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"message": "Hafiz Mock Backend", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/api/verses")
async def get_verses():
    """Return the verse list (identical shape to the real backend)."""
    return md.VERSE_RESPONSE


@app.get("/api/recordings/{use_case}")
async def get_recording(use_case: int):
    """Download the mock WAV recording for a given use case (1–5).

    The same audio is embedded as base64 in the session_summary's
    recording.audio_data field; this endpoint lets the frontend offer
    a direct download link as well.
    """
    if use_case not in md.MOCK_WAVS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown use_case {use_case}. Valid values: {sorted(md.MOCK_WAVS)}",
        )
    wav_bytes = base64.b64decode(md.MOCK_WAVS[use_case])
    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={
            "Content-Disposition": f'attachment; filename="recitation_case_{use_case}.wav"',
            "Content-Length": str(len(wav_bytes)),
        },
    )


@app.get("/api/session-recordings/{session_id}")
async def get_session_recording(session_id: str):
    """Download the real audio recorded during a specific WebSocket session.

    The session_id comes from the recording.download_url in session_summary
    (only present when recording.source == "recorded").
    Recordings are kept in memory for the last 20 sessions.
    """
    entry = _session_recordings.get(session_id)
    if not entry:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No recording found for session '{session_id}'. "
                "It may have been evicted (only the last 20 sessions are kept), "
                "or the session sent no audio data."
            ),
        )
    audio_bytes, mime = entry
    _, ext = _detect_audio_format(audio_bytes)
    return Response(
        content=audio_bytes,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="recitation_{session_id[:8]}.{ext}"',
            "Content-Length": str(len(audio_bytes)),
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket
# ─────────────────────────────────────────────────────────────────────────────

@app.websocket("/ws/recitation")
async def ws_recitation(websocket: WebSocket):
    await websocket.accept()

    session_id: str = str(uuid.uuid4())
    use_case: Optional[int] = None
    chunks: list = []
    chunk_index: int = 0
    audio_buffer: List[bytes] = []   # accumulates raw bytes from every audio chunk

    print(f"[WS] Client connected  session={session_id}")

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = msg.get("type")

            # ── start ────────────────────────────────────────────────────────
            if msg_type == "start":
                use_case = int(msg.get("use_case", 1))

                if use_case not in md.CASE_DATA:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown use_case '{use_case}'. Valid values: 1–12",
                    })
                    continue

                case = md.CASE_DATA[use_case]
                chunks = case["chunks"]
                chunk_index = 0
                audio_buffer = []   # fresh buffer for each session

                status_msg = {**case["status"], "session_id": session_id}
                await websocket.send_json(status_msg)
                print(
                    f"[WS] start  use_case={use_case}  "
                    f"chunks={len(chunks)}  session={session_id}"
                )

            # ── audio ────────────────────────────────────────────────────────
            elif msg_type == "audio":
                if not chunks:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Send 'start' before sending audio chunks.",
                    })
                    continue

                # Accumulate raw audio bytes from this chunk (if any were sent)
                audio_b64: str = msg.get("audio", "") or msg.get("data", "")
                if audio_b64:
                    try:
                        audio_buffer.append(base64.b64decode(audio_b64))
                    except Exception:
                        pass  # ignore malformed base64; still send feedback

                if chunk_index < len(chunks):
                    feedback = {**chunks[chunk_index], "session_id": session_id}
                    # Simulate a short processing delay (realistic feel)
                    await asyncio.sleep(0.4)
                    await websocket.send_json(feedback)
                    print(
                        f"[WS] feedback  chunk={chunk_index + 1}/{len(chunks)}  "
                        f"cursor={feedback.get('word_cursor')}  "
                        f"ayah={feedback.get('current_ayah')}  "
                        f"audio_bytes_so_far={sum(len(b) for b in audio_buffer)}"
                    )
                    chunk_index += 1
                else:
                    # All mock chunks already sent; still buffer audio if present
                    print("[WS] audio received but all mock chunks already sent")

            # ── stop ─────────────────────────────────────────────────────────
            elif msg_type == "stop":
                if use_case is None or use_case not in md.CASE_DATA:
                    await websocket.send_json({
                        "type": "error",
                        "message": "No active session. Send 'start' first.",
                    })
                    continue

                # Flush any unsent feedback chunks
                while chunk_index < len(chunks):
                    feedback = {**chunks[chunk_index], "session_id": session_id}
                    await websocket.send_json(feedback)
                    chunk_index += 1

                # Build the recording block
                mock_summary = md.CASE_DATA[use_case]["summary"]
                duration = mock_summary.get("duration_seconds", 0)

                if audio_buffer:
                    # Real audio: concatenate all chunks and store in memory
                    full_audio = b"".join(audio_buffer)
                    mime, ext = _detect_audio_format(full_audio)
                    _store_recording(session_id, full_audio, mime)
                    recording = _build_real_recording(
                        session_id, full_audio, duration, use_case
                    )
                    print(
                        f"[WS] real recording stored  "
                        f"size={len(full_audio)}B  format={ext}  session={session_id}"
                    )
                else:
                    # No audio data was sent — fall back to the static mock WAV
                    recording = {
                        **mock_summary["recording"],
                        "source": "mock",
                    }
                    print(f"[WS] no audio data received — using mock WAV  session={session_id}")

                summary = {
                    **mock_summary,
                    "session_id": session_id,
                    "recording": recording,
                }
                await websocket.send_json(summary)
                print(f"[WS] session_summary sent  session={session_id}")

                # Reset so the client can start a new session on the same connection
                use_case = None
                chunks = []
                chunk_index = 0
                audio_buffer = []

            # ── unknown ───────────────────────────────────────────────────────
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: '{msg_type}'",
                })

    except WebSocketDisconnect:
        print(f"[WS] Client disconnected  session={session_id}")
    except Exception as exc:
        print(f"[WS] Error  session={session_id}  error={exc}")
        import traceback
        traceback.print_exc()
