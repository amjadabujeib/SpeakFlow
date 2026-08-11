"""Authenticated roleplay WebSocket session state machine."""

from __future__ import annotations

import asyncio
import json
import re
import tempfile

import librosa
from fastapi import WebSocket, WebSocketDisconnect

from speakflow.features.auth.application.errors import (
    AuthInvalidCredentialsError,
    AuthUnavailableError,
)
from speakflow.features.auth.infrastructure.service import auth_service
from speakflow.features.language_tools.infrastructure.tts import (
    _remove_temporary_file,
)
from speakflow.features.learning_plan.engine.identity import bind_user
from speakflow.features.learning_plan.engine.service import (
    PlpConflictError,
    PlpInvalidAttemptError,
    PlpNotFoundError,
)
from speakflow.features.pronunciation.infrastructure.pronunciation_audio import (
    _speech_activity,
)
from speakflow.features.roleplay.application.chat_delivery import (
    _chat_delivery_metrics,
    _correct_chat_grammar,
    _transcribe_chat_audio,
)
from speakflow.features.roleplay.application.roleplay_socket_policy import (
    RoleplayTurnInputError,
    safe_roleplay_turn_error,
    validate_roleplay_session_binding,
)
from speakflow.features.roleplay.application.roleplay_turn import process_roleplay_turn
from speakflow.features.roleplay.application.service import roleplay_service
from speakflow.features.roleplay.domain.turn_policy import (
    typed_roleplay_turn_error,
)
from speakflow.features.roleplay.presentation.evaluation import (
    _finalize_disconnected_roleplay,
    _send_roleplay_tts,
)
from speakflow.runtime import models as runtime


async def websocket_endpoint(websocket: WebSocket):
    scheme, _, token = websocket.headers.get("authorization", "").partition(" ")
    if scheme.casefold() != "bearer":
        token = ""
    token = token.strip()
    try:
        user = await asyncio.to_thread(auth_service.authenticate, token)
    except (AuthInvalidCredentialsError, AuthUnavailableError):
        await websocket.accept()
        await websocket.close(code=4401, reason="authentication required")
        return
    with bind_user(user.user_id):
        await _roleplay_websocket_session(websocket)


_roleplay_turn_locks: dict[str, tuple[asyncio.Lock, int]] = {}
_roleplay_turn_locks_guard = asyncio.Lock()


async def _acquire_roleplay_turn_lock(client_session_id: str) -> asyncio.Lock:
    async with _roleplay_turn_locks_guard:
        lock, users = _roleplay_turn_locks.get(
            client_session_id,
            (asyncio.Lock(), 0),
        )
        _roleplay_turn_locks[client_session_id] = (lock, users + 1)
    try:
        await lock.acquire()
    except BaseException:
        await _release_roleplay_turn_lock(client_session_id, lock, acquired=False)
        raise
    return lock


async def _release_roleplay_turn_lock(
    client_session_id: str,
    lock: asyncio.Lock,
    *,
    acquired: bool = True,
) -> None:
    if acquired:
        lock.release()
    async with _roleplay_turn_locks_guard:
        current = _roleplay_turn_locks.get(client_session_id)
        if current is None or current[0] is not lock:
            return
        remaining = current[1] - 1
        if remaining <= 0:
            _roleplay_turn_locks.pop(client_session_id, None)
        else:
            _roleplay_turn_locks[client_session_id] = (lock, remaining)


async def _roleplay_websocket_session(websocket: WebSocket):
    await websocket.accept()
    client_session_id: str | None = None
    pending_audio: dict | None = None
    tts_tasks: set[asyncio.Task] = set()
    message_times: list[float] = []
    try:
        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=120,
                )
            except TimeoutError:
                await websocket.close(code=4408, reason="idle timeout")
                break
            except WebSocketDisconnect:
                break
            now = asyncio.get_running_loop().time()
            message_times = [value for value in message_times if now - value < 60]
            if len(message_times) >= 60:
                await websocket.close(code=4429, reason="message rate exceeded")
                break
            message_times.append(now)
            if message.get("type") == "websocket.disconnect":
                break
            raw_bytes = message.get("bytes")
            raw_text = message.get("text")
            payload: dict = {}
            if raw_text is not None:
                if len(raw_text) > 10_000:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "protocol_error",
                                "error": "WebSocket message exceeds 10,000 characters",
                            }
                        )
                    )
                    continue
                try:
                    decoded = json.loads(raw_text)
                    if not isinstance(decoded, dict):
                        raise ValueError("WebSocket message must be an object")
                    payload = decoded
                except (json.JSONDecodeError, TypeError, ValueError) as exc:
                    await websocket.send_text(
                        json.dumps({"type": "protocol_error", "error": str(exc)})
                    )
                    continue
                event_type = payload.get("type")
                if event_type == "session_context":
                    pending_audio = None
                    supplied = str(payload.get("client_session_id", "")).strip()
                    if not re.fullmatch(r"[a-zA-Z0-9_\-]{8,80}", supplied):
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "protocol_error",
                                    "error": "invalid roleplay session ID",
                                }
                            )
                        )
                        continue
                    try:
                        validate_roleplay_session_binding(
                            client_session_id,
                            supplied,
                        )
                        context = await asyncio.to_thread(
                            roleplay_service.context, supplied
                        )
                        if context["status"] != "active":
                            raise PlpConflictError("roleplay session is not active")
                    except Exception as exc:
                        safe_error = (
                            str(exc)
                            if isinstance(
                                exc,
                                (
                                    PlpNotFoundError,
                                    PlpConflictError,
                                    PlpInvalidAttemptError,
                                ),
                            )
                            else "The roleplay session could not be loaded."
                        )
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "protocol_error",
                                    "error": safe_error,
                                }
                            )
                        )
                        continue
                    client_session_id = supplied
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "session_ready",
                                "client_session_id": supplied,
                                "objective_state": context["objective_state"],
                            }
                        )
                    )
                    continue
                if client_session_id is None:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "protocol_error",
                                "error": "start and bind a roleplay session first",
                            }
                        )
                    )
                    continue
                if event_type == "audio_turn":
                    turn_id = str(payload.get("turn_id", "")).strip()
                    if not re.fullmatch(r"[a-zA-Z0-9_\-]{8,80}", turn_id):
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "turn_error",
                                    "turn_id": turn_id,
                                    "error": "invalid turn ID",
                                }
                            )
                        )
                        continue
                    if pending_audio is not None:
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "turn_error",
                                    "turn_id": turn_id,
                                    "error": "send the pending audio bytes before starting another audio turn",
                                }
                            )
                        )
                        continue
                    pending_audio = {"turn_id": turn_id}
                    continue
                if event_type != "user_turn":
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "protocol_error",
                                "error": "unsupported WebSocket event",
                            }
                        )
                    )
                    continue
                turn_id = str(payload.get("turn_id", "")).strip()
                user_text = str(payload.get("text", "")).strip()
                pending_audio = None
                input_mode = "text"
                if (
                    not re.fullmatch(r"[a-zA-Z0-9_\-]{8,80}", turn_id)
                    or not user_text
                    or len(user_text) > 3000
                ):
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "turn_error",
                                "turn_id": turn_id,
                                "error": "text turns require a valid ID and 1-3000 characters",
                            }
                        )
                    )
                    continue
                language_error = typed_roleplay_turn_error(user_text)
                if language_error is not None:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "turn_error",
                                "turn_id": turn_id,
                                "error": language_error,
                            }
                        )
                    )
                    continue
                audio_data = None
            elif raw_bytes is not None:
                if client_session_id is None or pending_audio is None:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "protocol_error",
                                "error": "audio bytes require an audio_turn header",
                            }
                        )
                    )
                    continue
                if len(raw_bytes) > 10 * 1024 * 1024:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "turn_error",
                                "turn_id": pending_audio["turn_id"],
                                "error": "recording exceeds the 10 MB limit",
                            }
                        )
                    )
                    pending_audio = None
                    continue
                turn_id = pending_audio["turn_id"]
                pending_audio = None
                input_mode = "audio"
                audio_data = raw_bytes
                user_text = ""
            else:
                continue

            assert client_session_id is not None
            turn_lock = await _acquire_roleplay_turn_lock(client_session_id)
            temp_audio_path = None
            try:
                word_feedback: list[dict] = []
                delivery_metrics: dict = {}
                if audio_data is not None:
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".wav"
                    ) as temp_audio:
                        temp_audio.write(audio_data)
                        temp_audio_path = temp_audio.name
                    audio_array, _ = await asyncio.to_thread(
                        librosa.load, temp_audio_path, sr=16000
                    )
                    duration = len(audio_array) / 16000.0
                    if duration > 90:
                        raise RoleplayTurnInputError(
                            "recording exceeds the 90-second limit"
                        )
                    activity = await asyncio.to_thread(
                        _speech_activity, audio_array, 16000
                    )
                    if not activity["has_speech"]:
                        raise RoleplayTurnInputError(
                            "no clear speech was detected"
                        )
                    async with runtime._chat_inference_lock:
                        whisper_ready = await asyncio.to_thread(
                            runtime._load_whisper_models
                        )
                        if not whisper_ready:
                            raise RuntimeError("speech recognition is unavailable")
                        user_text, word_feedback = await asyncio.to_thread(
                            _transcribe_chat_audio, temp_audio_path
                        )
                    if not user_text:
                        raise RoleplayTurnInputError(
                            "no clear English sentence was recognized"
                        )
                    fluency, pitch_variation = await asyncio.to_thread(
                        _chat_delivery_metrics,
                        audio_array,
                        activity,
                        word_feedback,
                    )
                    delivery_metrics = {
                        "fluency": fluency,
                        "pitch_variation": pitch_variation,
                        "voiced_seconds": activity["voiced_duration_seconds"],
                        "recording_seconds": round(duration, 3),
                        "timed_word_count": sum(
                            1
                            for item in word_feedback
                            if item.get("start") is not None
                            and item.get("end") is not None
                        ),
                    }

                corrected_text = None
                grammar_evaluated = await asyncio.to_thread(
                    runtime._load_gector_model
                )
                if grammar_evaluated:
                    async with runtime._chat_inference_lock:
                        corrected_text = await asyncio.to_thread(
                            _correct_chat_grammar, user_text
                        )
                recorded = await asyncio.to_thread(
                    process_roleplay_turn,
                    client_session_id=client_session_id,
                    turn_id=turn_id,
                    input_mode=input_mode,
                    user_text=user_text,
                    corrected_text=corrected_text,
                    word_feedback=word_feedback,
                    delivery_metrics=delivery_metrics,
                    grammar_evaluated=grammar_evaluated,
                )
                stored_turn = recorded["turn"]
                stored_state = recorded["objective_state"]
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "turn_response",
                            "turn_id": turn_id,
                            "input_mode": stored_turn["input_mode"],
                            "user_text": stored_turn["user_text"],
                            "text": stored_turn["assistant_text"],
                            "turn_status": stored_turn["turn_status"],
                            "grammar_feedback": stored_turn["grammar_feedback"],
                            "grammar_corrected_text": stored_turn[
                                "grammar_corrected_text"
                            ],
                            "word_confidence": stored_turn["word_feedback"] or None,
                            "delivery_metrics": stored_turn["delivery_metrics"],
                            "objective_state": stored_state,
                            "objective_progress": recorded["objective_progress"],
                            "scenario_complete": recorded["scenario_complete"],
                        }
                    )
                )
                task = asyncio.create_task(
                    _send_roleplay_tts(
                        websocket,
                        turn_id=turn_id,
                        text=stored_turn["assistant_text"],
                    )
                )
                tts_tasks.add(task)
                task.add_done_callback(tts_tasks.discard)
            except Exception as exc:
                safe_error = safe_roleplay_turn_error(exc)
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "turn_error",
                            "turn_id": turn_id,
                            "error": safe_error,
                        }
                    )
                )
            finally:
                if temp_audio_path:
                    _remove_temporary_file(temp_audio_path)
                await _release_roleplay_turn_lock(client_session_id, turn_lock)
    except WebSocketDisconnect:
        pass
    finally:
        for task in tts_tasks:
            task.cancel()
        if tts_tasks:
            await asyncio.gather(*tts_tasks, return_exceptions=True)
        await _finalize_disconnected_roleplay(client_session_id)
