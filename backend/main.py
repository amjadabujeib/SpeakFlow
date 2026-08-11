"""SpeakFlow executable composition root."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from speakflow.config import load_runtime_env

load_runtime_env()
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import uvicorn
from fastapi.responses import JSONResponse

from speakflow.app import create_application
from speakflow.app.health import build_health_router
from speakflow.features.admin.presentation import router as admin_router
from speakflow.features.auth.presentation import router as auth_router
from speakflow.features.language_tools.infrastructure import (
    language as language_runtime,
)
from speakflow.features.language_tools.infrastructure.language import (
    check_grammar,
    lookup_word,
)
from speakflow.features.language_tools.infrastructure.tts import (
    create_tts_audio,
    get_pronunciation_guide,
)
from speakflow.features.language_tools.presentation import build_language_tools_router
from speakflow.features.learning_plan.application import (
    learning_plan_lifecycle,
)
from speakflow.features.learning_plan.engine.database import dispose_engine
from speakflow.features.learning_plan.presentation import router as learning_plan_router
from speakflow.features.news.infrastructure import provider as news_runtime
from speakflow.features.news.infrastructure.provider import (
    get_personalized_news,
    proxy_news_image,
)
from speakflow.features.news.presentation import build_news_router
from speakflow.features.pronunciation.infrastructure.pronunciation_endpoints import (
    check_pronunciation,
    transcribe_guided_speaking,
)
from speakflow.features.pronunciation.presentation import build_pronunciation_router
from speakflow.features.roleplay.presentation import router as roleplay_router
from speakflow.features.roleplay.presentation.finalize import (
    finalize_roleplay_session,
)
from speakflow.features.roleplay.presentation.runtime_router import (
    build_roleplay_runtime_router,
)
from speakflow.features.roleplay.presentation.translation import (
    generate_roleplay_scenario_draft,
    legacy_roleplay_escape_route,
    translate_arabic,
)
from speakflow.features.roleplay.presentation.websocket_session import (
    websocket_endpoint,
)
from speakflow.runtime import models as model_runtime


@asynccontextmanager
async def _application_lifespan(_application):
    loading_mode = getattr(
        _application.state,
        "runtime_model_loading",
        model_runtime.model_loading_mode(),
    )
    if loading_mode == "eager":
        report = await asyncio.to_thread(model_runtime.eager_load_runtime_models)
        _application.state.runtime_model_report = report
    else:
        print("Runtime model loading is lazy; models will load on first use.")
        _application.state.runtime_model_report = None
    learning_plan_lifecycle.start()
    try:
        yield
    finally:
        if learning_plan_lifecycle.stop():
            learning_plan_lifecycle.close()
            dispose_engine()
        else:
            print(
                "PLP worker is still finishing provider work; keeping its "
                "database pool alive until process exit."
            )
        language_runtime.close_language_runtime()
        news_runtime.close_news_runtime()


def health() -> JSONResponse:
    """Expose only readiness; detailed capability state belongs under /admin."""
    plp_health = learning_plan_lifecycle.health()
    model_report = getattr(app.state, "runtime_model_report", None)
    ready = (
        plp_health.get("database") == "ready"
        and plp_health.get("curriculum") == "ready"
        and plp_health.get("worker") is True
        and (model_report is None or model_report.ready)
    )
    if ready:
        return JSONResponse(status_code=200, content={"status": "ok"})
    return JSONResponse(status_code=503, content={"status": "degraded"})


app = create_application(
    routers=(auth_router, learning_plan_router, roleplay_router, admin_router),
    lifespan=_application_lifespan,
)
app.include_router(
    build_language_tools_router(
        check_grammar=check_grammar,
        lookup_word=lookup_word,
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
    uvicorn.run(
        "main:app",
        host=os.environ.get("SPEAKFLOW_HOST", "127.0.0.1"),
        port=int(os.environ.get("SPEAKFLOW_PORT", "8000")),
        reload=False,
    )
