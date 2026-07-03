"""
ELAF Backend – FastAPI server
Integrates: GECToR/RoBERTa grammar correction, Groq LLM, PLP lesson generation
"""
import os
import json
import uuid
import asyncio
from typing import Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# ── Environment ──────────────────────────────────────────────
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["GROQ_API_KEY"] = "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"

# ── Groq / OpenAI client ────────────────────────────────────
from openai import OpenAI

def _groq_client() -> Optional[OpenAI]:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    return OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)

GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# ── GECToR (RoBERTa grammar correction) ─────────────────────
GECTOR_AVAILABLE = False
gector_model = None
gector_tokenizer = None
gector_encode = None
gector_decode = None

try:
    import gector
    from gector import GECToR, predict as gector_predict, load_verb_dict
    from transformers import AutoTokenizer
    GECTOR_AVAILABLE = True
except ImportError:
    print("⚠ GECToR not installed. Grammar correction will use LLM fallback only.")

# ── FastAPI App ──────────────────────────────────────────────
app = FastAPI(title="ELAF Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory PLP lesson store ───────────────────────────────
plp_lessons: dict[str, dict] = {}

# ── Models ───────────────────────────────────────────────────
class GrammarCheckRequest(BaseModel):
    text: str

class PLPGenerateRequest(BaseModel):
    topic: str
    level: str = "B1"

class ProductionEvalRequest(BaseModel):
    content: str

class VocabularyLookupRequest(BaseModel):
    word: str


# ══════════════════════════════════════════════════════════════
#  STARTUP – Load GECToR model
# ══════════════════════════════════════════════════════════════

@app.on_event("startup")
def load_models():
    global gector_model, gector_tokenizer, gector_encode, gector_decode

    if GECTOR_AVAILABLE:
        try:
            print("Loading GECToR RoBERTa Grammar Model...")
            model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "roberta", "gector", "gector-roberta-base-5k")
            # Fallback paths
            for p in [model_path, "/home/amjad/Desktop/roberta/gector/gector-roberta-base-5k",
                       "/home/amjad/Desktop/ELAF/roberta/gector/gector-roberta-base-5k"]:
                if os.path.exists(p):
                    model_path = p
                    break

            verb_dict_path = model_path.replace("gector-roberta-base-5k", "data/verb-form-vocab.txt")
            for vp in [verb_dict_path,
                       "/home/amjad/Desktop/roberta/gector/data/verb-form-vocab.txt",
                       "/home/amjad/Desktop/ELAF/roberta/gector/data/verb-form-vocab.txt"]:
                if os.path.exists(vp):
                    verb_dict_path = vp
                    break

            gector_tokenizer = AutoTokenizer.from_pretrained(model_path)
            gector_model = GECToR.from_pretrained(model_path)
            gector_encode, gector_decode = load_verb_dict(verb_dict_path)
            print("✅ GECToR loaded successfully!")
        except Exception as e:
            print(f"⚠ Failed to load GECToR: {e}")
            gector_model = None

    print("✅ ELAF Backend ready!")


# ══════════════════════════════════════════════════════════════
#  GRAMMAR CHECK
# ══════════════════════════════════════════════════════════════

def _gector_correct(text: str) -> Optional[str]:
    """Run GECToR RoBERTa model on text. Returns corrected text or None."""
    if not GECTOR_AVAILABLE or not gector_model:
        return None
    try:
        corrected_list = gector_predict(
            gector_model, gector_tokenizer,
            [text], gector_encode, gector_decode,
            keep_confidence=0.0, min_error_prob=0.0,
            n_iteration=5, batch_size=2
        )
        if corrected_list and corrected_list[0] != text:
            return corrected_list[0]
    except Exception as e:
        print(f"GECToR error: {e}")
    return None


def _llm_grammar_check(text: str, roberta_corrected: Optional[str] = None) -> dict:
    """Use Groq LLM for grammar analysis. Returns corrections list."""
    client = _groq_client()
    if not client:
        return {"is_correct": True, "corrected_text": text, "corrections": []}

    try:
        if roberta_corrected and roberta_corrected != text:
            system_msg = (
                "You are an English grammar expert. The user wrote a sentence with grammar mistakes. "
                "I'll provide the original and RoBERTa-corrected version. "
                "Analyze each correction and provide explanations. "
                "Return a JSON object with: "
                '{"corrected_text": "...", "is_correct": false, '
                '"corrections": [{"original": "...", "corrected": "...", "explanation": "..."}]}'
            )
            user_msg = f'Original: "{text}"\nCorrected: "{roberta_corrected}"'
        else:
            system_msg = (
                "You are an English grammar expert. Analyze the given sentence for grammar, spelling, "
                "punctuation, and article errors. "
                "If the sentence is correct, return: "
                '{"corrected_text": "<same text>", "is_correct": true, "corrections": []}. '
                "If there are errors, return: "
                '{"corrected_text": "<fixed text>", "is_correct": false, '
                '"corrections": [{"original": "<wrong part>", "corrected": "<fixed part>", "explanation": "<why>"}]}. '
                "Return ONLY valid JSON, nothing else."
            )
            user_msg = f'Analyze this sentence:\n"{text}"'

        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            model=GROQ_MODEL,
            temperature=0.1,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.strip()
        result = json.loads(content)
        return result
    except Exception as e:
        print(f"LLM grammar error: {e}")
        if roberta_corrected and roberta_corrected != text:
            return {
                "corrected_text": roberta_corrected,
                "is_correct": False,
                "corrections": [{
                    "original": text,
                    "corrected": roberta_corrected,
                    "explanation": "Grammar correction detected by RoBERTa model."
                }]
            }
        return {"is_correct": True, "corrected_text": text, "corrections": []}


@app.post("/api/grammar/check")
async def check_grammar(req: GrammarCheckRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "Text cannot be empty")

    # Step 1: Run GECToR RoBERTa
    roberta_corrected = await asyncio.to_thread(_gector_correct, text)

    # Step 2: Run LLM analysis
    result = await asyncio.to_thread(_llm_grammar_check, text, roberta_corrected)

    return result


# ══════════════════════════════════════════════════════════════
#  PLP LESSON GENERATION
# ══════════════════════════════════════════════════════════════

def _generate_plp_lesson_llm(topic: str, level: str) -> dict:
    """Generate a complete PLP lesson using Groq LLM."""
    client = _groq_client()
    if not client:
        raise HTTPException(503, "Groq API not configured")

    system_prompt = f"""You are an expert ESL curriculum designer. Create a complete PLP (Presentation-Practice-Production) lesson.

IMPORTANT: Return ONLY valid JSON matching this exact structure:
{{
  "id": "<unique-uuid>",
  "title": "<lesson title>",
  "topic": "{topic}",
  "level": "{level}",
  "presentation": {{
    "vocabulary": [
      {{
        "word": "<word>",
        "definition": "<clear definition>",
        "arabic_translation": "<Arabic translation>",
        "part_of_speech": "<noun/verb/adj/adv>",
        "example_sentence": "<example using the word>"
      }}
    ],
    "grammar_points": [
      {{
        "title": "<grammar topic>",
        "explanation": "<clear explanation>",
        "formula": "<grammar formula/pattern>",
        "examples": ["<example 1>", "<example 2>"],
        "common_mistakes": ["<mistake 1>", "<mistake 2>"]
      }}
    ],
    "example_sentences": ["<sentence 1>", "<sentence 2>"],
    "cultural_notes": "<optional cultural context>"
  }},
  "practice": {{
    "exercises": [
      {{
        "id": "<exercise-id>",
        "type": "multiple_choice",
        "instruction": "<what to do>",
        "question": "<the question>",
        "options": ["<option A>", "<option B>", "<option C>", "<option D>"],
        "correct_answer": "<correct option>",
        "hint": "<optional hint>",
        "explanation": "<why this is correct>"
      }},
      {{
        "id": "<exercise-id>",
        "type": "fill_blank",
        "instruction": "Fill in the blank",
        "question": "<sentence with ___>",
        "correct_answer": "<answer>",
        "hint": "<hint>",
        "explanation": "<explanation>"
      }},
      {{
        "id": "<exercise-id>",
        "type": "correct_error",
        "instruction": "Find and correct the error",
        "question": "<sentence with error>",
        "correct_answer": "<corrected sentence>",
        "explanation": "<what was wrong>"
      }}
    ]
  }},
  "production": {{
    "tasks": [
      {{
        "id": "<task-id>",
        "type": "writing",
        "title": "<task title>",
        "description": "<what to do>",
        "prompts": ["<prompt 1>", "<prompt 2>"],
        "evaluation_criteria": ["<criterion 1>", "<criterion 2>"],
        "time_limit_minutes": 10
      }}
    ]
  }}
}}

Create 5-8 vocabulary items, 2-3 grammar points, 5-6 exercises (mix of types), and 2 production tasks.
Make it appropriate for {level} level learners. Topic: {topic}."""

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Create a {level}-level PLP lesson about: {topic}"}
            ],
            model=GROQ_MODEL,
            temperature=0.7,
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.strip()
        lesson = json.loads(content)

        # Ensure it has an id
        if not lesson.get("id"):
            lesson["id"] = str(uuid.uuid4())[:8]

        return lesson
    except Exception as e:
        print(f"PLP generation error: {e}")
        raise HTTPException(500, f"Failed to generate lesson: {e}")


@app.post("/api/plp/generate")
async def generate_plp_lesson(req: PLPGenerateRequest):
    lesson = await asyncio.to_thread(
        _generate_plp_lesson_llm, req.topic, req.level
    )
    # Store in memory
    lesson_id = lesson.get("id", str(uuid.uuid4())[:8])
    plp_lessons[lesson_id] = lesson
    return lesson


@app.get("/api/plp/lessons")
def list_plp_lessons():
    return {"lessons": list(plp_lessons.values())}


@app.get("/api/plp/lessons/{lesson_id}")
def get_plp_lesson(lesson_id: str):
    lesson = plp_lessons.get(lesson_id)
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    return lesson


@app.get("/api/plp/lessons/{lesson_id}/exercise/{exercise_id}/check")
def check_exercise(lesson_id: str, exercise_id: str, answer: str = ""):
    lesson = plp_lessons.get(lesson_id)
    if not lesson:
        raise HTTPException(404, "Lesson not found")

    exercises = lesson.get("practice", {}).get("exercises", [])
    exercise = next((e for e in exercises if e.get("id") == exercise_id), None)

    if not exercise:
        raise HTTPException(404, "Exercise not found")

    correct_answer = exercise.get("correct_answer", "")
    is_correct = answer.strip().lower() == correct_answer.strip().lower()

    return {
        "is_correct": is_correct,
        "correct_answer": correct_answer,
        "explanation": exercise.get("explanation", ""),
        "user_answer": answer
    }


@app.post("/api/plp/lessons/{lesson_id}/production/{task_id}/evaluate")
async def evaluate_production(lesson_id: str, task_id: str, req: ProductionEvalRequest):
    lesson = plp_lessons.get(lesson_id)
    if not lesson:
        raise HTTPException(404, "Lesson not found")

    tasks = lesson.get("production", {}).get("tasks", [])
    task = next((t for t in tasks if t.get("id") == task_id), None)
    if not task:
        raise HTTPException(404, "Task not found")

    client = _groq_client()
    if not client:
        return {"score": 70, "feedback": "AI evaluation unavailable."}

    try:
        level = lesson.get("level", "B1")
        criteria = task.get("evaluation_criteria", [])
        criteria_text = "\n".join(f"- {c}" for c in criteria) if criteria else "- Grammar\n- Vocabulary\n- Coherence"

        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": f"You are an ESL teacher evaluating a {level}-level student's writing. "
                    f"Evaluate based on these criteria:\n{criteria_text}\n"
                    "Return JSON: {\"score\": <0-100>, \"feedback\": \"<detailed feedback>\"}"},
                {"role": "user", "content": f"Task: {task.get('title', '')}\nDescription: {task.get('description', '')}\n\nStudent's response:\n{req.content}"}
            ],
            model=GROQ_MODEL,
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content.strip())
        return result
    except Exception as e:
        print(f"Production eval error: {e}")
        return {"score": 65, "feedback": f"Evaluation error: {e}"}


# ══════════════════════════════════════════════════════════════
#  VOCABULARY LOOKUP
# ══════════════════════════════════════════════════════════════

@app.post("/api/vocabulary/lookup")
async def lookup_word(req: VocabularyLookupRequest):
    client = _groq_client()
    if not client:
        return {"error": "Groq API not configured"}

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a dictionary API. For the given English word, return JSON: "
                    '{"word": "...", "phonetic": "/.../" , "part_of_speech": "...", '
                    '"definition": "...", "arabic_translation": "...", '
                    '"example_sentence": "...", "synonyms": ["...", "..."]}'
                    " Return ONLY valid JSON."},
                {"role": "user", "content": f"Look up: {req.word}"}
            ],
            model=GROQ_MODEL,
            temperature=0.1,
            max_tokens=300,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════
#  CHAT – WebSocket for live conversation
# ══════════════════════════════════════════════════════════════

def _get_chat_reply(user_text: str) -> str:
    """Get a conversational reply from Groq LLM."""
    client = _groq_client()
    if not client:
        return "Please configure GROQ_API_KEY to enable chat."
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": (
                    "You are a friendly conversational partner talking to an English learner. "
                    "Important: Assume the most common intended meaning for a beginner English learner. "
                    "Reply conversationally to keep the chat going. Keep your response friendly and brief (under 3 sentences). "
                    "DO NOT correct the user's grammar or point out any mistakes. Just reply naturally to what they meant to say."
                )},
                {"role": "user", "content": f'The user just said: "{user_text}"'}
            ],
            model=GROQ_MODEL,
            temperature=0.7,
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Chat error: {e}")
        return "I'm having trouble connecting right now. Could you try again?"


def _get_grammar_feedback(user_text: str, roberta_corrected: Optional[str] = None) -> str:
    """Get grammar feedback from Groq LLM."""
    client = _groq_client()
    if not client:
        return "Correct"
    try:
        if roberta_corrected and roberta_corrected != user_text:
            system_msg = (
                "You are an English teacher. The user made a grammar mistake. "
                "Give a very brief, concise 1-sentence explanation of the mistake."
            )
            user_msg = f'Original: "{user_text}"\nCorrected: "{roberta_corrected}"'
        else:
            system_msg = (
                "You are a strict English grammar teacher for an ESL student. "
                "If there is a mistake: provide a brief 1-sentence explanation followed by 'Corrected: [your corrected version]'. "
                "If the grammar is perfect: output EXACTLY 'Correct'. No extra chatter."
            )
            user_msg = f'Analyze for grammar errors: "{user_text}"'

        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            model=GROQ_MODEL,
            temperature=0.1,
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Grammar feedback error: {e}")
        if roberta_corrected and roberta_corrected != user_text:
            return f"Grammar tip: You should say '{roberta_corrected}'"
        return "Correct"


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    print("✅ Client connected to /ws/chat")

    try:
        while True:
            message = await websocket.receive()

            if "text" not in message or message["text"] is None:
                continue

            # Parse user text
            try:
                payload = json.loads(message["text"])
                user_text = payload.get("text", message["text"]).strip()
            except (json.JSONDecodeError, AttributeError):
                user_text = message["text"].strip()

            if not user_text:
                continue

            print(f"📩 User said: {user_text}")

            # Step 1: GECToR grammar check
            roberta_corrected = None
            if GECTOR_AVAILABLE and gector_model:
                roberta_corrected = await asyncio.to_thread(_gector_correct, user_text)

            # Step 2: Get chat reply + grammar feedback in parallel
            chat_reply, grammar_feedback = await asyncio.gather(
                asyncio.to_thread(_get_chat_reply, user_text),
                asyncio.to_thread(_get_grammar_feedback, user_text, roberta_corrected)
            )

            # Step 3: Send response back to Flutter
            response_payload = {
                "type": "bot_response",
                "text": chat_reply,
                "user_text": user_text,
                "grammar_feedback": grammar_feedback,
            }
            await websocket.send_text(json.dumps(response_payload))
            print(f"📤 Bot replied: {chat_reply[:60]}...")

    except WebSocketDisconnect:
        print("❌ Client disconnected from /ws/chat")
    except Exception as e:
        print(f"WebSocket error: {e}")


# ══════════════════════════════════════════════════════════════
#  HEALTH CHECK
# ══════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {
        "status": "ok",
        "gector_available": GECTOR_AVAILABLE and gector_model is not None,
        "groq_configured": bool(os.environ.get("GROQ_API_KEY")),
        "plp_lessons_count": len(plp_lessons),
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
