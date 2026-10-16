# Manus AI Prompt — One-Shot Frontend for Codex Universalis

Copy and paste this entire block into Manus AI to generate the complete frontend in one shot.

---

## PROMPT

Build a complete, production-ready frontend for "Codex Universalis" — a real-time collaborative classroom web app for a hackathon demo. The app has two roles: Maestro (teacher) and Apprentice (student). It connects to a FastAPI WebSocket backend at `ws://localhost:8000/ws`.

### Pages required:
1. **maestro.html** — Teacher interface
2. **apprentice.html** — Student interface

### Shared design system (use inline CSS, no frameworks, no build steps):
- Dark slate theme: bg `#020617`, panels `#0f172a`, borders `#334155`, accent cyan `#22d3ee`, accent purple `#a855f7`, text `#f8fafc`, muted `#94a3b8`
- Font: system sans-serif (`-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`)
- Glassmorphism panels with `backdrop-filter: blur(8px)`, rounded corners (12px-14px)
- Smooth animations: fadeIn, slideUp, bounce (for avatar speaking), pulse (for recording)
- Connection status dot (green when online, red when offline)
- Mobile-responsive, single-column on small screens

### maestro.html features:
- Header with "MAESTRO" title and live connection dot
- Large monospace textarea for lesson notes (placeholder: "Type your lesson notes here…")
- Two buttons: "Broadcast" (cyan) and "Dictate" (purple)
- Broadcast: sends textarea text as plain text via WebSocket → all apprentices receive it as English
- Dictate: uses `webkitSpeechRecognition` → on result, puts transcript in textarea AND sends `{"type":"voice","text": transcript}` via WebSocket. If SpeechRecognition is unsupported or errors, fall back to `prompt()` labeled "Dictation mode"
- Listening state: red pulse animation on Dictate button
- Auto-reconnect on disconnect (reload page after 3s)

### Live Whiteboard (on maestro.html):
- Full-width canvas, 260px height, black background
- Maestro can draw with mouse/touch
- Color picker: 6 color pills (cyan, purple, green, red, amber, white)
- Size slider: 1-10
- Clear button
- Every draw action sends via WebSocket: `{"type":"draw","action":"start|move|end|clear","x":..,"y":..,"color":"..","size":..}`

### apprentice.html features:
- Header with "APPRENTICE" title and live connection dot
- Language toggle bar: English | मराठी | हिंदी (always displays English feed, buttons are cosmetic for future)
- Live feed div: messages appear newest on top, each with timestamp `[HH:MM]` and `[EN]` tag
- Empty state: "Waiting for maestro…"
- Private Marginalia: textarea, local-only, never sent to server
- Receive `{"type":"note","en":"...","mr":"...","hi":"...","ts":..}` → display only `en` field
- Receive `{"type":"mermaid","code":"...","ts":..}` → render Mermaid.js diagram (CDN: `https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js`, `mermaid.initialize({startOnLoad:false, theme:'neutral', look:'handDrawn'})`)
- Receive `{"type":"draw",...}` → mirror drawing on a read-only canvas (same dimensions as maestro)
- Receive `{"type":"revision","text":"...","ts":..}` → show purple speech bubble next to avatar, avatar bounces (CSS keyframe `bounce` 1.2s infinite), button shows "Speaking…" for 6 seconds then resets

### Avatar Professor (on apprentice.html):
- Upload face button → file input → draws image on 170x200 canvas → saves to localStorage as data URL
- Default state: "No face uploaded" dashed box
- Revision Mode button: sends `{"type":"revision_request"}` via WebSocket
- Speech bubble: purple, appears next to avatar when revision received, auto-hides after 6s
- Button pulse animation while speaking

### WebSocket connection:
- `const ws = new WebSocket(\`ws://${location.host}/ws\`)`
- Handle onopen, onclose, onerror, onmessage
- onmessage: parse JSON, dispatch by msg.type (note, mermaid, draw, revision)
- Never crash on malformed JSON (try/catch)

### Deliverables:
- maestro.html (complete, single file, inline CSS + JS)
- apprentice.html (complete, single file, inline CSS + JS)
- Both must work when opened directly in browser against a running FastAPI WebSocket server at localhost:8000
- No external dependencies except mermaid.min.js CDN
- No console errors
- Tested flow: maestro broadcasts text → apprentice sees it; maestro dictates → apprentice gets mermaid diagram; maestro draws → apprentice mirrors; apprentice clicks revision → gets speech bubble

Write clean, commented code. Make it look like a real product, not a student project.

---

## How to use:
1. Copy the prompt above
2. Paste into Manus AI
3. Get two complete HTML files in one shot
4. Open `maestro.html` and `apprentice.html` against your running backend
