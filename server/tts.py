import asyncio
import os
import tempfile

import httpx

KOKORO_URL = os.environ.get("KOKORO_URL", "http://localhost:8880/v1/audio/speech")
KOKORO_VOICE = os.environ.get("KOKORO_VOICE", "af_sky")


async def synthesize(text: str) -> bytes | None:
    text = text.strip()
    if not text:
        return None
    audio = await _try_kokoro(text)
    if audio is None:
        audio = await _try_macos_say(text)
    return audio


async def _try_kokoro(text: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(KOKORO_URL, json={
                "model": "kokoro",
                "input": text,
                "voice": KOKORO_VOICE,
                "response_format": "wav",
            })
            if r.status_code == 200:
                return r.content
    except Exception:
        pass
    return None


async def _try_macos_say(text: str) -> bytes | None:
    tmp_aiff = tempfile.mktemp(suffix=".aiff")
    tmp_wav = tempfile.mktemp(suffix=".wav")
    try:
        proc = await asyncio.create_subprocess_exec(
            "say", "-v", "Samantha", "-o", tmp_aiff, text,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        proc2 = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", tmp_aiff, "-ar", "22050", "-ac", "1", tmp_wav,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc2.wait()
        if os.path.exists(tmp_wav):
            with open(tmp_wav, "rb") as f:
                return f.read()
    except Exception:
        pass
    finally:
        for p in (tmp_aiff, tmp_wav):
            try:
                os.unlink(p)
            except Exception:
                pass
    return None
