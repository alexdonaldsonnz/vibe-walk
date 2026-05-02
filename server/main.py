import json
import os
import re
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .claude_session import ClaudeSession
from .stt import STTProcessor
from .tts import synthesize

load_dotenv()

app = FastAPI()
CLIENT_DIR = Path(__file__).parent.parent / "client"
app.mount("/static", StaticFiles(directory=str(CLIENT_DIR)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(CLIENT_DIR / "index.html"))


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()

    cwd = os.environ.get("VIBE_WALK_CWD", str(Path.home()))
    permission = os.environ.get("VIBE_WALK_PERMISSION", "bypassPermissions")

    stt = STTProcessor()
    claude = ClaudeSession(cwd=cwd, permission_mode=permission)

    sample_rate: int | None = None
    audio_buffer: list[np.ndarray] = []
    is_processing = False

    try:
        await ws.send_json({"type": "status", "state": "connecting"})
        await claude.start()
        await ws.send_json({"type": "status", "state": "listening"})

        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break

            if "text" in msg:
                data = json.loads(msg["text"])
                if data.get("type") == "hello":
                    sample_rate = int(data["sample_rate"])
                    await ws.send_json({"type": "ready"})

            elif "bytes" in msg and not is_processing and sample_rate:
                chunk = np.frombuffer(msg["bytes"], dtype=np.float32).copy()
                audio_buffer.append(chunk)

                total_samples = sum(len(c) for c in audio_buffer)
                if total_samples >= sample_rate * 3:
                    audio = np.concatenate(audio_buffer)
                    audio_buffer = []

                    text = await stt.transcribe(audio, sample_rate)
                    if text:
                        stt.add(text)
                        await ws.send_json({
                            "type": "transcript",
                            "text": text,
                            "full": stt.full_transcript(),
                        })

                        prompt = stt.check_trigger()
                        if prompt is not None:
                            is_processing = True
                            await ws.send_json({"type": "status", "state": "thinking"})
                            await ws.send_json({"type": "prompt", "text": prompt})

                            try:
                                await _respond(ws, claude, prompt)
                            except Exception as e:
                                await ws.send_json({"type": "error", "message": str(e)})

                            is_processing = False
                            audio_buffer = []
                            await ws.send_json({"type": "status", "state": "listening"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        await claude.stop()


async def _respond(ws: WebSocket, claude: ClaudeSession, prompt: str) -> None:
    sentence_buf = ""
    full_response = ""

    async for chunk in claude.send_prompt(prompt):
        full_response += chunk
        await ws.send_json({"type": "response_chunk", "text": chunk})

        sentence_buf += chunk
        while True:
            m = re.search(r"(?<=[.!?])\s+", sentence_buf)
            if not m:
                break
            sentence = sentence_buf[: m.start() + 1].strip()
            sentence_buf = sentence_buf[m.end():]
            if sentence:
                audio = await synthesize(sentence)
                if audio:
                    await ws.send_bytes(audio)

    if sentence_buf.strip():
        audio = await synthesize(sentence_buf.strip())
        if audio:
            await ws.send_bytes(audio)

    await ws.send_json({"type": "response_done", "full_text": full_response})
