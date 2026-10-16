import os
import re
import time
import json
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pathlib import Path
from deep_translator import GoogleTranslator, MyMemoryTranslator
import requests

app = FastAPI()
BASE_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# In-memory translation cache: keyed by (lang, text)
# ---------------------------------------------------------------------------
_translate_cache: dict[tuple[str, str], str] = {}

# ---------------------------------------------------------------------------
# In-memory mermaid cache: keyed by spoken text
# ---------------------------------------------------------------------------
_mermaid_cache: dict[str, str] = {}

# ---------------------------------------------------------------------------
# Recent messages buffer for revision mode (last 20)
# ---------------------------------------------------------------------------
_recent_messages: list[dict] = []

def _add_recent_message(msg: dict):
    _recent_messages.append(msg)
    if len(_recent_messages) > 20:
        _recent_messages.pop(0)

# ---------------------------------------------------------------------------
# L0 OFFLINE LEXICON — exact match, case-insensitive, punctuation-tolerant
# ---------------------------------------------------------------------------
LEXICON: dict[str, dict[str, str]] = {
    "the water cycle has four stages": {
        "mr": "पाणी चक्रात चार टप्पे असतात.",
        "hi": "जल चक्र में चार चरण होते हैं।",
    },
    "evaporation turns water into vapor": {
        "mr": "बाष्पीभवनामुळे पाण्याची वाफ बनते.",
        "hi": "वाष्पीकरण से पानी वाष्प बनता है।",
    },
    "condensation forms clouds in the sky": {
        "mr": "संघननामुळे आकाशात ढग तयार होतात.",
        "hi": "संघनन से आकाश में बादल बनते हैं।",
    },
    "precipitation falls as rain": {
        "mr": "वर्षाव म्हणून पाऊस पडतो.",
        "hi": "वर्षा के रूप में बारिश गिरती है।",
    },
    "good morning students today we study the water cycle": {
        "mr": "सुप्रभात विद्यार्थ्यांनो, आज आपण पाणी चक्राचा अभ्यास करू.",
        "hi": "सुप्रभात विद्यार्थियों, आज हम जल चक्र का अध्ययन करेंगे।",
    },
}

# ---------------------------------------------------------------------------
# Reverse lexicon: Marathi/Hindi -> English (code-switching to English)
# ---------------------------------------------------------------------------
_REVERSE_LEXICON: dict[str, str] = {}
for _en_text, _translations in LEXICON.items():
    for _lang, _text in _translations.items():
        _REVERSE_LEXICON[_text] = _en_text
# Manual Hinglish -> English additions
_REVERSE_LEXICON["aaj hum water cycle padhenge"] = "Today we will study the water cycle"
_REVERSE_LEXICON["aaj hum paani cycle padhenge"] = "Today we will study the water cycle"


def _norm_key(text: str) -> str:
    """Normalize for lexicon lookup: lowercase, strip trailing punctuation/whitespace."""
    return re.sub(r'[.!?\s]+$', '', text.strip().lower())


# ---------------------------------------------------------------------------
# L1 NVIDIA LLM translator
# ---------------------------------------------------------------------------
def _translate_nvidia(text: str, target: str, system_prompt: Optional[str] = None) -> str:
    """POST to NVIDIA API integrate.chat.completions. Hard 8s timeout."""
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY not set in environment")

    if system_prompt is None:
        target_name = {"mr": "Marathi", "hi": "Hindi"}.get(target, target)
        system_prompt = f"Translate the user text into {target_name}. Output ONLY the translated text."

    payload = {
        "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
        "max_tokens": 500,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = requests.post(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=8,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


# ---------------------------------------------------------------------------
# Divine Dictation — NVIDIA LLM to Mermaid flowchart
# ---------------------------------------------------------------------------
def _diagram_nvidia(spoken_text: str) -> str:
    """Convert spoken description into Mermaid.js flowchart via NVIDIA LLM. 10s timeout."""
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY not set in environment")

    system_prompt = "Convert this spoken description into valid Mermaid.js flowchart syntax. Output ONLY the mermaid code."

    payload = {
        "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": spoken_text},
        ],
        "temperature": 0.2,
        "max_tokens": 500,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = requests.post(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    code = data["choices"][0]["message"]["content"].strip()
    # Strip markdown fences if present
    code = re.sub(r'^```mermaid\s*', '', code, flags=re.MULTILINE)
    code = re.sub(r'^```\s*$', '', code, flags=re.MULTILINE)
    code = code.strip()
    if not code:
        raise ValueError("Empty mermaid code from LLM")
    return code


def _fallback_mermaid(spoken_text: str) -> str:
    """Build a 3-node flowchart from the first 3 spoken words. Never crashes."""
    words = spoken_text.strip().split()
    if len(words) == 0:
        words = ["Silence"]
    if len(words) == 1:
        words = [words[0], "is", "heard"]
    if len(words) == 2:
        words = [words[0], words[1], "flow"]
    a, b, c = words[0], words[1], words[2]
    # Sanitize node labels (alphanumeric only)
    safe = lambda w: re.sub(r'[^A-Za-z0-9]', '', w) or "Node"
    return f"graph TD\n    {safe(a)} --> {safe(b)}\n    {safe(b)} --> {safe(c)}"


def speak_to_mermaid(spoken_text: str) -> str:
    """4-layer chain for voice->mermaid: cache → NVIDIA → fallback → never crash."""
    if spoken_text in _mermaid_cache:
        return _mermaid_cache[spoken_text]

    code = None
    try:
        code = _diagram_nvidia(spoken_text)
    except Exception:
        code = None

    if not code:
        code = _fallback_mermaid(spoken_text)

    _mermaid_cache[spoken_text] = code
    return code


# ---------------------------------------------------------------------------
# Avatar Professor — Revision Mode (NVIDIA LLM revision summary)
# ---------------------------------------------------------------------------
def _revision_nvidia(messages: list[dict]) -> str:
    """Generate a 3-sentence revision summary from recent lecture messages."""
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY not set in environment")

    # Build context from recent messages (text content only)
    context_parts = []
    for m in messages:
        if m.get("type") == "note":
            context_parts.append(f"Teacher said: {m.get('en', '')}")
        elif m.get("type") == "mermaid":
            context_parts.append(f"Teacher drew a diagram: {m.get('code', '')[:200]}")

    context = "\n".join(context_parts) if context_parts else "No lecture content yet."

    system_prompt = (
        "Create a 3-sentence revision summary of this lecture in simple English. "
        "Make it sound like a teacher explaining to a student. Output ONLY the summary."
    )

    payload = {
        "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Lecture content:\n{context}"},
        ],
        "temperature": 0.3,
        "max_tokens": 300,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = requests.post(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def _fallback_revision(messages: list[dict]) -> str:
    """Fallback revision summary when NVIDIA is unavailable."""
    note_count = sum(1 for m in messages if m.get("type") == "note")
    diagram_count = sum(1 for m in messages if m.get("type") == "mermaid")
    return (
        f"Today we covered {note_count} teaching point{'s' if note_count != 1 else ''} "
        f"and {diagram_count} diagram{'s' if diagram_count != 1 else ''}. "
        "Please review your notes and the diagrams shared during class. "
        "Come prepared with questions for our next session."
    )


def speak_revision(messages: list[dict]) -> str:
    """Generate revision summary: NVIDIA → fallback → never crash."""
    try:
        return _revision_nvidia(messages)
    except Exception:
        return _fallback_revision(messages)


# ---------------------------------------------------------------------------
# L3 MyMemoryTranslator fallback chain
# ---------------------------------------------------------------------------
def _try_mymemory(text: str, target: str) -> str:
    """Try MyMemoryTranslator with specific region codes, then language names."""
    candidates = {
        'mr': ['mr-IN', 'marathi'],
        'hi': ['hi-IN', 'hindi'],
    }.get(target, [target])
    last_err = None
    for code in candidates:
        try:
            return MyMemoryTranslator(source='en-GB', target=code).translate(text)
        except Exception as e:
            last_err = e
            continue
    raise last_err if last_err else Exception("MyMemoryTranslator failed")


# ---------------------------------------------------------------------------
# 4-layer translate chain: L0 lexicon → L1 NVIDIA → L2 Google → L3 MyMemory → L4 original
# ---------------------------------------------------------------------------
def translate_safe(text: str, target: str) -> str:
    """Translate text via 4-layer chain. Never crashes the server.
    Caches every successful translation from any layer.
    For target='en': reverse lexicon -> NVIDIA Hinglish->English -> original."""
    cache_key = (target, text)
    if cache_key in _translate_cache:
        return _translate_cache[cache_key]

    result = text

    if target == 'en':
        # Code-switching to English: L0 reverse lexicon first
        try:
            norm = _norm_key(text)
            if norm in _REVERSE_LEXICON:
                result = _REVERSE_LEXICON[norm]
        except Exception:
            pass

        # L1: NVIDIA LLM — Hinglish / Marathi / Hindi -> pure academic English
        if result == text:
            try:
                result = _translate_nvidia(
                    text,
                    'en',
                    system_prompt=(
                        "You are a translator for an Indian classroom. "
                        "The teacher is speaking a mix of English, Marathi, and Hindi (Hinglish). "
                        "Translate this text into pure, academic English. "
                        "Output ONLY the English text."
                    ),
                )
            except Exception:
                pass

        # L4: original text — but never show raw Devanagari on the English feed
        if result == text and re.search(r'[\u0900-\u097F]', text):
            result = f"[untranslated: {text}]"
    else:
        # Existing 4-layer chain for Marathi / Hindi targets
        # L0: Offline lexicon (exact match, case-insensitive)
        try:
            lex_entry = LEXICON.get(_norm_key(text), {})
            if target in lex_entry:
                result = lex_entry[target]
        except Exception:
            pass

        # L1: NVIDIA LLM
        if result == text:
            try:
                result = _translate_nvidia(text, target)
            except Exception:
                pass

        # L2: GoogleTranslator
        if result == text:
            try:
                result = GoogleTranslator(source='auto', target=target).translate(text)
            except Exception:
                pass

        # L3: MyMemoryTranslator
        if result == text:
            try:
                result = _try_mymemory(text, target)
            except Exception:
                pass

        # L4: original text (already in `result`)

    if result != text:
        _translate_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# FastAPI routes
# ---------------------------------------------------------------------------
@app.get("/maestro.html")
async def maestro():
    return FileResponse(BASE_DIR / "maestro.html")


@app.get("/apprentice.html")
async def apprentice():
    return FileResponse(BASE_DIR / "apprentice.html")


@app.get("/")
async def root():
    return {"status": "ok", "endpoints": ["/maestro.html", "/apprentice.html", "/ws"]}


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Try to parse as JSON message
            try:
                msg = json.loads(data)
                if isinstance(msg, dict):
                    mtype = msg.get("type")

                    if mtype == "voice":
                        spoken_text = msg.get("text", "")
                        mermaid_code = speak_to_mermaid(spoken_text)
                        out = {
                            "type": "mermaid",
                            "code": mermaid_code,
                            "ts": time.time()
                        }
                        _add_recent_message(out)
                        await manager.broadcast(json.dumps(out))
                        continue

                    if mtype == "revision_request":
                        summary = speak_revision(list(_recent_messages))
                        out = {
                            "type": "revision",
                            "text": summary,
                            "ts": time.time()
                        }
                        _add_recent_message(out)
                        await manager.broadcast(json.dumps(out))
                        continue

            except (json.JSONDecodeError, AttributeError):
                pass

            # Plain text note — existing translation path
            original = data
            en = translate_safe(original, 'en')
            mr = translate_safe(original, 'mr')
            hi = translate_safe(original, 'hi')
            payload = {
                "type": "note",
                "en": en,
                "mr": mr,
                "hi": hi,
                "ts": time.time()
            }
            _add_recent_message(payload)
            await manager.broadcast(json.dumps(payload))
    except WebSocketDisconnect:
        manager.disconnect(websocket)


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, message: str):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)