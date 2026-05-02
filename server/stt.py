import asyncio
import re
from math import gcd

import numpy as np

SUBMIT_PHRASES = ["submit prompt", "send prompt"]
_model = None


def _get_model():
    global _model
    if _model is None:
        import os
        from faster_whisper import WhisperModel
        model_size = os.environ.get("WHISPER_MODEL", "base.en")
        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _model


def _transcribe_sync(audio: np.ndarray) -> str:
    model = _get_model()
    segments, _ = model.transcribe(
        audio,
        language="en",
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
    )
    return " ".join(seg.text.strip() for seg in segments).strip()


def _resample(audio: np.ndarray, src_rate: int, dst_rate: int = 16000) -> np.ndarray:
    if src_rate == dst_rate:
        return audio
    from scipy.signal import resample_poly
    g = gcd(src_rate, dst_rate)
    return resample_poly(audio, dst_rate // g, src_rate // g).astype(np.float32)


class STTProcessor:
    def __init__(self):
        self._parts: list[str] = []

    async def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        resampled = _resample(audio, sample_rate)
        return await asyncio.to_thread(_transcribe_sync, resampled)

    def add(self, text: str) -> None:
        if text:
            self._parts.append(text)

    def full_transcript(self) -> str:
        return " ".join(self._parts)

    def check_trigger(self) -> str | None:
        """Return the prompt text (before the trigger phrase) if detected, else None."""
        full = self.full_transcript()
        lower = full.lower()
        for phrase in SUBMIT_PHRASES:
            idx = lower.rfind(phrase)
            if idx >= 0:
                prompt = full[:idx].strip()
                self._parts = []
                return prompt
        return None

    def clear(self) -> None:
        self._parts = []
