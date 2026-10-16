# Codex Universalis

> **Speak, and knowledge becomes art — in every language.**

A real-time collaborative classroom for the CSI KJSSE Renaissance Buildathon. Built in a single day by two people, designed to scale globally.

---

## 4 Pillars Mapping

| Pillar | Feature | What it does |
|--------|---------|--------------|
| **Human Potential** | Divine Dictation | Speak a description → NVIDIA Nemotron converts it into a Mermaid.js flowchart diagram, broadcast live to all students. |
| **Knowledge Without Borders** | Rosetta Engine | Teacher speaks Hinglish/Marathi/Hindi → code-switches to pure academic English, or translates into Marathi/Hindi. Offline lexicon + API fallback chain, never crashes. |
| **A New Worldview** | Live collaborative classroom | Teacher (Maestro) types → every student (Apprentice) sees notes instantly over WebSockets. One shared feed, one shared whiteboard. |
| **Challenge the Perspective** | Avatar Professor | Upload a face → stick-figure avatar with speech bubble. Revision Mode → NVIDIA summarizes the last 20 lecture messages into a 3-sentence teacher-style recap. |

---

## Setup

```bash
cd /Users/abhinav/codex-universalis
python3 main.py
```

Then open:
- **Teacher:** `http://localhost:8000/maestro.html`
- **Student:** `http://localhost:8000/apprentice.html`

Requirements: `fastapi`, `uvicorn`, `websockets`, `deep-translator`, `requests`.  
Optional: `NVIDIA_API_KEY` environment variable for LLM-powered translation, diagram generation, and revision summaries.

---

## Architecture

- **Backend:** FastAPI + WebSockets (single `main.py`, in-memory state)
- **Real-time:** WebSocket `/ws` broadcasts every message to all connected clients
- **LLM:** NVIDIA NIM — `nvidia/nemotron-3.5-super-vl-120b-a12b` via `https://integrate.api.nvidia.com/v1`
- **Translation:** `deep-translator` (GoogleTranslator, MyMemoryTranslator) with offline lexicon cache
- **Diagrams:** Mermaid.js (CDN, `look: 'handDrawn'`, `theme: 'neutral'`)
- **Voice:** Browser `webkitSpeechRecognition` (Maestro), `prompt()` fallback
- **Frontend:** Vanilla JS, inline CSS, no build steps, no frameworks

---

## Sprint History

1. **WebSocket broadcast** — Maestro types, Apprentices receive instantly
2. **Rosetta Engine** — Multilingual translation (EN ↔ MR ↔ HI) with lexicon + API chain + cache
3. **Divine Dictation** — Voice → Mermaid.js flowchart via NVIDIA LLM
4. **Code-switching to English** — Hinglish/Marathi/Hindi → pure academic English
5. **Avatar Professor** — Face upload, stick-figure avatar, Revision Mode summaries

---

## License

MIT. Built for CSI KJSSE Renaissance Buildathon, 16 Oct 2026.