# Vibe Walk — Product Plan

Rough priority order. Items later in the list are more complex or less urgent.

---

## 1. Settings Menu

A slide-out or modal settings panel accessible from the main UI. Houses all user-configurable options below. Build this first so subsequent features have a home.

**Settings to include (see individual items below):**
- Show intermediate Claude responses
- TTS mode (what gets spoken aloud)
- "I think you said…" STT echo
- Voice input method
- Auto-submit mode
- Text-only mode

---

## 2. Streaming / Intermediate Claude Responses

**Problem:** Claude only surfaces its final response; intermediate streamed tokens are discarded.

**Plan:**
- Wire up the WebSocket to forward partial Claude output tokens as they arrive.
- In the UI, display a "Claude is thinking…" section that updates in real time.
- Setting: **Show intermediate responses** (toggle, default: on).

---

## 3. TTS Mode Setting

Control what gets spoken aloud via Kokoro TTS.

**Options (radio/select, default: All — intermediate + final):**
- Off — never speak Claude's response
- Final answer only — speak only after Claude finishes
- Intermediate + final — speak tokens as they stream in

Connects directly to item 2; intermediate audio only makes sense when streaming is enabled.

---

## 4. "I Think You Said…" STT Echo

After the user's speech is transcribed, read it back via TTS so the user can confirm without looking at the screen.

**Format:** "I think you said: [transcript]"

**Setting:** **Echo transcription aloud** (toggle, default: on).

This plays before Claude's response and should be skippable (tap to interrupt).

---

## 5. Text Input Mode

Allow sending messages to Claude by typing rather than speaking — useful as a fallback or for quiet environments.

**Plan:**
- Add a persistent text input field (hidden by default, toggled by a setting).
- The existing voice-transcript edit field can double as this when voice input is inactive.
- Setting: **Input mode** (Voice / Text, default: Voice).

In text mode the mic button is hidden and a keyboard input + Send button are shown instead.

---

## 6. Voice Input Method Setting

Expand beyond the current push-to-record button.

**Setting: Voice input method** (select, default: Button)

### Option A — Button (current default)
Tap to start recording, tap again (or tap Send) to stop and submit.

### Option B — VAD, No Wake Word
Continuous listening. Automatically detects speech start/end via Voice Activity Detection. No button press required.

### Option C — Wake Word ("Hey Claude")
Listens passively. Activating phrase "Hey Claude" starts transcription. Saying "over" followed by ~1 s of silence ends the recording.

**Sub-setting (applies to VAD modes): Auto-submit**
- On — recording is submitted to Claude immediately when silence is detected / "over" is said.
- Off — transcript is shown for review; user taps Send to submit (the STT echo from item 4 plays here).

Default: user's choice; no strong default prescribed yet.

**Implementation notes:**
- VAD can use the WebRTC VAD WASM port or a simple energy-threshold approach server-side.
- Wake word detection needs an on-device model (e.g. openWakeWord or similar) to avoid round-tripping audio.

---

## 7. Conversation History & Resume

**Problem:** Each session is stateless; there is no way to resume a previous conversation with Claude.

**Plan:**
- Store conversation sessions server-side (SQLite or JSON files), keyed by session ID.
- Home / landing screen shows:
  - **New conversation** button
  - List of past conversations (timestamp + first user message as preview)
- Selecting a past conversation restores context and resumes the Claude session.
- Claude Code SDK session will need to be initialised with prior transcript as context.

This is the most architecturally significant item — it touches the server session model, storage, and the home-screen UI.

---

## 8. Background / Tab-Unfocus Reconnection

**Problem:** When the Firefox tab loses focus on mobile (e.g. switching apps via Tailscale), the WebSocket disconnects. Reloading is required to reconnect.

**Plan:**
- Client: implement WebSocket reconnection with exponential back-off on `onclose` / `onerror`.
- Server: keep Claude session alive for a grace period (e.g. 60 s) after the socket drops, so resuming mid-conversation is seamless.
- UI: show a "Reconnecting…" banner rather than a hard error; auto-dismiss on success.
- Investigate whether the Page Visibility API (`visibilitychange`) can be used to proactively pause/resume the audio pipeline rather than letting the socket die.

This is left last because it depends on the session persistence work in item 7, and mobile browser behaviour varies enough that thorough testing is needed.

---

## Out of Scope / Future

- Multi-user / shared sessions
- Custom wake words
- On-device Whisper (to reduce STT latency further)
- Push notifications when Claude finishes a long response
