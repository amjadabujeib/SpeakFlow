"""SpeakFlow executable composition root."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from speakflow.config import load_runtime_env

load_runtime_env()
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import uvicorn

from plp.database import dispose_engine
from plp.service import plp_service
from speakflow.app import create_application
from speakflow.app.health import build_health_router
from speakflow.features.auth.presentation import router as auth_router
from speakflow.features.admin.presentation import router as admin_router
from speakflow.features.language_tools.presentation import build_language_tools_router
from speakflow.features.learning_plan.presentation import router as learning_plan_router
from speakflow.features.news.presentation import build_news_router
from speakflow.features.pronunciation.presentation import build_pronunciation_router
from speakflow.features.roleplay.presentation import router as roleplay_router
from speakflow.features.roleplay.presentation.runtime_router import (
    build_roleplay_runtime_router,
)
from speakflow.runtime import language as language_runtime
from speakflow.runtime import models as model_runtime
from speakflow.runtime import news as news_runtime
from speakflow.runtime.language import (
    check_grammar,
    lookup_word,
)
from speakflow.runtime.news import (
    get_personalized_news,
    proxy_news_image,
)
from speakflow.runtime.pronunciation_endpoints import (
    check_pronunciation,
    transcribe_guided_speaking,
)
from speakflow.runtime.roleplay_finalize import finalize_roleplay_session
from speakflow.runtime.roleplay_session import (
    generate_roleplay_scenario_draft,
    legacy_roleplay_escape_route,
    translate_arabic,
    websocket_endpoint,
)
from speakflow.runtime.tts import (
    create_tts_audio,
    get_pronunciation_guide,
    get_tts_audio,
)

@asynccontextmanager
async def _application_lifespan(_application):
    print("Speech, grammar, TTS, and Practice models will load on first use.")
    plp_service.start_worker()
    try:
        yield
    finally:
        if plp_service.stop_worker():
            plp_service.close()
            dispose_engine()
        else:
            print(
                "PLP worker is still finishing provider work; keeping its "
                "database pool alive until process exit."
            )
        if language_runtime._general_groq_client is not None:
            language_runtime._general_groq_client.close()
        news_runtime._news_image_session.close()


def health() -> dict:
    """Report capability state without forcing heavyweight model loads."""
    return {
        "status": "ok",
        "speech": {
            "whisperx_installed": model_runtime.WHISPER_AVAILABLE,
            "whisperx_loaded": model_runtime.whisper_model is not None,
            "pronunciation_loaded": model_runtime.pronunciation_scorer is not None,
            "pronunciation_engine": "ctc",
        },
        "grammar_loaded": model_runtime.gector_model is not None,
        "tts_loaded": model_runtime.kokoro_pipeline is not None,
        "groq_configured": bool(os.environ.get("GROQ_API_KEY")),
        "plp": plp_service.health(),
    }


app = create_application(
    routers=(auth_router, learning_plan_router, roleplay_router, admin_router),
    lifespan=_application_lifespan,
)
app.include_router(
    build_language_tools_router(
        check_grammar=check_grammar,
        lookup_word=lookup_word,
        get_tts_audio=get_tts_audio,
        create_tts_audio=create_tts_audio,
        pronunciation_guide=get_pronunciation_guide,
    )
)
app.include_router(
    build_roleplay_runtime_router(
        generate_scenario_draft=generate_roleplay_scenario_draft,
        translate_arabic=translate_arabic,
        legacy_escape_route=legacy_roleplay_escape_route,
        finalize_session=finalize_roleplay_session,
        websocket_endpoint=websocket_endpoint,
    )
)
app.include_router(
    build_news_router(
        list_news=get_personalized_news,
        proxy_image=proxy_news_image,
    )
)
app.include_router(
    build_pronunciation_router(
        score_pronunciation=check_pronunciation,
        transcribe_speaking=transcribe_guided_speaking,
    )
)
app.include_router(build_health_router(health))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
