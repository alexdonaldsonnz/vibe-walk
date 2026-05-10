# Vibe Walk

Voice-to-Claude-Code interface for use while walking. Captures mic audio, transcribes via Whisper, sends to Claude Code SDK, streams TTS response back.

## Running the server

```bash
./start.sh
```

Starts Kokoro TTS (Docker), sets up Tailscale HTTPS, and launches uvicorn on port 8000.

**Important:** `start.sh` unsets `ANTHROPIC_API_KEY` before starting so Claude Code uses your subscription login rather than API credits. If you see "credit balance too low" errors, check that env var isn't leaking in.

## Testing without a microphone

A test audio file is provided at `client/test-audio.wav` ("Hi, what is the name of this project?").

1. Start the server: `./start.sh`
2. Open the phone URL printed in the terminal (must be `https://`)
3. Tap **Start Session** and wait for the green dot
4. Tap **Upload** (top-right of the "You said" section)
5. Select `test-audio.wav`
6. Watch the transcript populate, then tap **Send** to submit to Claude

To generate a new test audio file (macOS):

```bash
say -o /tmp/test.aiff "Your phrase here" && \
afconvert /tmp/test.aiff client/test-audio.wav -f WAVE -d LEI16@16000
```

## Architecture

- `server/main.py` — FastAPI + WebSocket handler; accumulates 2s audio chunks, routes STT → Claude → TTS
- `server/stt.py` — Whisper transcription via faster-whisper
- `server/claude_session.py` — Claude Code SDK session (spawns `claude` CLI subprocess)
- `server/tts.py` — Kokoro TTS (Docker) with macOS `say` fallback
- `client/index.html` — Single-page app; AudioWorklet mic capture, WebSocket binary audio, AudioContext playback

## Git workflow

After every change: test it, fix any issues found, then `git commit` and `git push` to the remote repo.

## Testing requirement

Before reporting any frontend change as complete, test it in Chrome using the browser tools. Fix any issues found before declaring done.

## Browser testing notes

**Use JavaScript clicks, not CDP mouse events.** The `computer` tool's mouse click actions (`left_click`) are unreliable in this setup — they frequently time out or misfire (appearing as right-clicks). Use `javascript_tool` to trigger interactions instead:

```js
// Click a button
document.getElementById('settings-btn').click();

// Fire a change event on a select
el.value = 'vad';
el.dispatchEvent(new Event('change'));
```

**The server runs on HTTPS port 8000.** Navigate to `https://alexs-macbook-pro.tailb97163.ts.net:8000/` — the plain Tailscale URL (port 443) may be down if tailscale serve isn't active.

**Coordinate system mismatch.** The browser viewport is 1728×936 CSS pixels (devicePixelRatio=2) but screenshots capture at a different scale. Don't rely on screenshot pixel coordinates for mouse clicks — use JS instead.

**Script/DOM ordering matters.** Any `<script>` block that references elements defined later in the HTML will fail to find them at parse time. Place dynamic HTML (modals, drawers) *before* the `<script>` tag, not after.

## Frontend work

Use the `frontend-design` skill whenever doing frontend work.

## HTTPS requirement

`navigator.mediaDevices` (mic access) requires HTTPS. The server auto-provisions Tailscale TLS certs via `tailscale cert`. If certs aren't available it falls back to `tailscale serve --bg` as an HTTPS proxy. HTTP-only mode will show an error on mic access.
