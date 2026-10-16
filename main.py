from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pathlib import Path
from deep_translator import GoogleTranslator
import time

app = FastAPI()
BASE_DIR = Path(__file__).parent

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

def translate_safe(text: str, target: str) -> str:
    """Translate text to target language. On any error, return original text."""
    try:
        return GoogleTranslator(source='auto', target=target).translate(text)
    except Exception:
        return text

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
            original = data
            mr = translate_safe(original, 'mr')
            hi = translate_safe(original, 'hi')
            payload = {
                "type": "note",
                "en": original,
                "mr": mr,
                "hi": hi,
                "ts": time.time()
            }
            import json
            await manager.broadcast(json.dumps(payload))
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)