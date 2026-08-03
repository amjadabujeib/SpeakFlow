import asyncio
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
from fastapi import HTTPException

from main import app
from plp.service import plp_service
from speakflow.runtime.pronunciation.core import PronunciationScoringError, calculate_overall_score
from speakflow.features.language_tools.presentation.schemas import (
    VocabularyLookupRequest,
)
from speakflow.runtime import language as language_runtime
from speakflow.runtime import models as model_runtime
from speakflow.runtime import news as news_runtime
from speakflow.runtime import pronunciation_audio
from speakflow.runtime import pronunciation_endpoints
from speakflow.runtime import pronunciation_text
from speakflow.runtime import roleplay_evaluation
from speakflow.runtime import roleplay_scenario
from speakflow.runtime.chat_delivery import (
    _chat_delivery_metrics,
    _chat_word_feedback,
)
from speakflow.runtime.language import (
    _first_sentences,
    _get_groq_chat_response,
    lookup_word,
)
from speakflow.runtime.news import get_personalized_news, rewrite_news
from speakflow.runtime.pronunciation_audio import (
    _apply_sentence_word_alignment,
    _read_upload_limited,
    _sentence_completeness,
    _single_word_transcript_matches,
    _speech_activity,
)
from speakflow.runtime.pronunciation_endpoints import (
    check_pronunciation,
    transcribe_guided_speaking,
)
from speakflow.runtime.pronunciation_text import (
    get_pronunciation_coaching,
    local_pronunciation_coaching,
)
from speakflow.runtime.roleplay_evaluation import (
    _arabic_translation_options,
    _roleplay_external_evaluation,
)
from speakflow.runtime.roleplay_scenario import (
    _roleplay_scenario_draft,
    _roleplay_turn_reply,
)
from speakflow.runtime.roleplay_session import translate_arabic
from speakflow.runtime.pronunciation.scoring import SCORING_METHOD
from plp.schemas import ArabicTranslationInput, RoleplayScenarioDraftInput
from speakflow.features.roleplay.domain.engine import (
    apply_objective_updates,
    get_builtin_scenario,
    initial_objective_state,
)


# Tests exercise helpers through their owning modules while keeping a compact
# call surface for the split runtime test files.
main = SimpleNamespace(
    app=app,
    VocabularyLookupRequest=VocabularyLookupRequest,
    _apply_sentence_word_alignment=_apply_sentence_word_alignment,
    _arabic_translation_options=_arabic_translation_options,
    _chat_delivery_metrics=_chat_delivery_metrics,
    _chat_word_feedback=_chat_word_feedback,
    _first_sentences=_first_sentences,
    _get_groq_chat_response=_get_groq_chat_response,
    _read_upload_limited=_read_upload_limited,
    _roleplay_external_evaluation=_roleplay_external_evaluation,
    _roleplay_scenario_draft=_roleplay_scenario_draft,
    _roleplay_turn_reply=_roleplay_turn_reply,
    _sentence_completeness=_sentence_completeness,
    _single_word_transcript_matches=_single_word_transcript_matches,
    _speech_activity=_speech_activity,
    calculate_overall_score=calculate_overall_score,
    check_pronunciation=check_pronunciation,
    get_personalized_news=get_personalized_news,
    get_pronunciation_coaching=get_pronunciation_coaching,
    librosa=pronunciation_endpoints.librosa,
    local_pronunciation_coaching=local_pronunciation_coaching,
    lookup_word=lookup_word,
    plp_service=plp_service,
    pronunciation_guide=model_runtime.pronunciation_guide,
    requests=news_runtime.requests,
    rewrite_news=rewrite_news,
    sf=pronunciation_endpoints.sf,
    transcribe_guided_speaking=transcribe_guided_speaking,
    translate_arabic=translate_arabic,
)

FAKE_SPEECH = (
    np.sin(2 * np.pi * 220 * np.arange(16000, dtype=np.float32) / 16000) * 0.05
).astype(np.float32)


class FakeUpload:
    def __init__(self, data=b"wav-bytes"):
        self._data = data
        self._consumed = False

    async def read(self, _size=-1):
        if self._consumed:
            return b""
        self._consumed = True
        return self._data


class FakeScorer:
    def __init__(self, error=None, flagged=False, acoustically_contradicted=False):
        self.error = error
        self.flagged = flagged
        self.acoustically_contradicted = acoustically_contradicted
        self.call_count = 0

    def score(self, audio_path, target):
        self.call_count += 1
        if self.error:
            raise self.error
        expected_phones = ("K", "AA", "R")
        likely_phones = (
            ("B", "IY", "P")
            if self.acoustically_contradicted
            else expected_phones
        )
        result = {
            "target": target,
            "spoken": None,
            "target_ipa": ["k", "ˈɑ", "ɹ"],
            "analysis": [
                {
                    "char": "k",
                    "arpabet": "K",
                    "status": "correct",
                    "score": 91,
                    "error_probability": 3.0,
                    "likely_arpabet": likely_phones[0],
                    "likely_phone_probability": 80.0,
                    "deletion_probability": 1.0,
                },
                {
                    "char": "ˈɑ",
                    "arpabet": "AA1",
                    "status": "correct",
                    "score": 84,
                    "error_probability": 6.0,
                    "likely_arpabet": likely_phones[1],
                    "likely_phone_probability": 80.0,
                    "deletion_probability": 1.0,
                },
                {
                    "char": "ɹ",
                    "arpabet": "R",
                    "status": "incorrect" if self.flagged else "correct",
                    "score": 48 if self.flagged else 88,
                    "error_probability": 32.0 if self.flagged else 4.0,
                    "likely_arpabet": likely_phones[2],
                    "likely_phone_probability": 80.0,
                    "deletion_probability": 1.0,
                },
            ],
            "word_scores": [{"word": "car", "accuracy": 88}],
            "feedback": "Strong pronunciation across the aligned sounds.",
            "scores": {
                "accuracy": 88,
                "fluency": 80,
                "prosody": 76,
                "completeness": 100,
                "overall_score": 87,
                "gop_score": 87,
            },
            "scoring_method": SCORING_METHOD,
            "flagged_phones": ([{
                "phoneme": "ɹ",
                "arpabet": "R",
                "status": "incorrect",
                "score": 48,
                "error_probability": 32.0,
            }] if self.flagged else []),
            "warnings": [],
            "calibration": {"substitution_confidence_threshold": 20.0},
        }
        return result


__all__ = [name for name in globals() if not name.startswith("__")]
