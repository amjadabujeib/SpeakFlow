"""Cached and request-coalesced Kokoro speech synthesis."""

from __future__ import annotations

import asyncio
import os
import tempfile
import threading
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi import HTTPException, Query
from fastapi.responses import Response

from speakflow.runtime.pronunciation.core import PronunciationScoringError
from speakflow.features.language_tools.presentation.schemas import TtsInput
from . import models as runtime


def generate_tts_audio(text: str, output_path: str):
    """
    Synthesizes speech from text using Kokoro-82M.
    """
    if not runtime._load_kokoro_pipeline():
        return False

    try:
        with runtime._kokoro_inference_lock:
            generator = runtime.kokoro_pipeline(
                text,
                voice=str(runtime._kokoro_voice_path),
                speed=1.0,
                split_pattern=r"\n+",
            )
            audio_chunks = [audio for _, _, audio in generator]
            if audio_chunks:
                full_audio = np.concatenate(
                    [
                        audio.numpy() if hasattr(audio, "numpy") else audio
                        for audio in audio_chunks
                    ]
                )
                sf.write(output_path, full_audio, 24000)
                return True

    except Exception as e:
        print(f"Kokoro TTS generation failed: {e}")
        return False

_tts_cache: dict[str, bytes] = {}
_tts_cache_order: list[str] = []
_tts_cache_lock = threading.Lock()
_TTS_CACHE_LIMIT = 64
_TTS_CACHE_MAX_BYTES = 32 * 1024 * 1024
_tts_cache_bytes = 0
_tts_key_locks: dict[str, tuple[asyncio.Lock, int]] = {}


async def _acquire_tts_key_lock(key: str) -> asyncio.Lock:
    with _tts_cache_lock:
        lock, users = _tts_key_locks.get(key, (asyncio.Lock(), 0))
        _tts_key_locks[key] = (lock, users + 1)
    try:
        await lock.acquire()
    except BaseException:
        with _tts_cache_lock:
            current, users = _tts_key_locks[key]
            if current is lock and users == 1:
                _tts_key_locks.pop(key, None)
            elif current is lock:
                _tts_key_locks[key] = (lock, users - 1)
        raise
    return lock


def _release_tts_key_lock(key: str, lock: asyncio.Lock) -> None:
    lock.release()
    with _tts_cache_lock:
        current, users = _tts_key_locks[key]
        if current is not lock:
            raise RuntimeError("TTS lock registry became inconsistent")
        if users == 1:
            _tts_key_locks.pop(key, None)
        else:
            _tts_key_locks[key] = (lock, users - 1)


async def _tts_response(text: str) -> Response:
    global _tts_cache_bytes
    if not runtime.KOKORO_AVAILABLE:
        raise HTTPException(status_code=503, detail="TTS service is unavailable")

    normalized = " ".join(text.split())
    if not normalized:
        raise HTTPException(status_code=422, detail="text must not be blank")
    with _tts_cache_lock:
        cached = _tts_cache.get(normalized)
    if cached is not None:
        return Response(
            content=cached,
            media_type="audio/wav",
            headers={"Cache-Control": "private, max-age=3600"},
        )

    key_lock = await _acquire_tts_key_lock(normalized)
    try:
        with _tts_cache_lock:
            cached = _tts_cache.get(normalized)
        if cached is not None:
            return Response(
                content=cached,
                media_type="audio/wav",
                headers={"Cache-Control": "private, max-age=3600"},
            )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
            tts_path = temp_audio.name
        success = await asyncio.to_thread(generate_tts_audio, normalized, tts_path)
        if not success:
            _remove_temporary_file(tts_path)
            raise HTTPException(status_code=500, detail="Failed to generate TTS audio")
        try:
            audio = await asyncio.to_thread(Path(tts_path).read_bytes)
        finally:
            _remove_temporary_file(tts_path)
        with _tts_cache_lock:
            if normalized not in _tts_cache and len(audio) <= _TTS_CACHE_MAX_BYTES:
                _tts_cache[normalized] = audio
                _tts_cache_order.append(normalized)
                _tts_cache_bytes += len(audio)
                while (
                    len(_tts_cache_order) > _TTS_CACHE_LIMIT
                    or _tts_cache_bytes > _TTS_CACHE_MAX_BYTES
                ):
                    expired = _tts_cache_order.pop(0)
                    removed = _tts_cache.pop(expired, None)
                    if removed is not None:
                        _tts_cache_bytes -= len(removed)
    finally:
        _release_tts_key_lock(normalized, key_lock)
    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"Cache-Control": "private, max-age=3600"},
    )


async def get_tts_audio(
    text: str = Query(..., min_length=1, max_length=500),
) -> Response:
    """Compatibility endpoint for unauthenticated media players."""
    return await _tts_response(text)


async def create_tts_audio(payload: TtsInput) -> Response:
    return await _tts_response(payload.text)


async def get_pronunciation_guide(text: str = Query(..., max_length=120)) -> dict:
    try:
        return await asyncio.to_thread(runtime.pronunciation_guide, text)
    except PronunciationScoringError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _remove_temporary_file(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
