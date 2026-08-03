from __future__ import annotations

import hashlib
import json

from .curated_lessons import get_curated_template, template_search_text


SOURCE = {
    "id": "project_core_a1_b2_v1",
    "title": "English Tutor Reviewed Core Curriculum A1–B2",
    "author": "English Tutor project curriculum team",
    "locator": "repo:backend/plp/seed.py",
    "license": "Project-authored",
    "version": "2026.07.26",
}


# These are intentionally compact, complete teaching objects. They provide a
# reviewed baseline for retrieval; expanding the corpus happens through the
# ingestion command rather than by letting the runtime model invent sources.
_LEVEL_CONTENT = {
    "A1": {
        "grammar": ("Basic present statements", "Use be and common present-simple verbs in short affirmative and negative sentences.", ["I am ready.", "She works here.", "They do not drive."]),
        "vocabulary": ("Personal and everyday essentials", "Teach high-frequency words for identity, family, time, food, places, and daily routines in short useful phrases.", ["My name is …", "I need some water.", "The shop opens at nine."]),
        "reading": ("Reading signs and short messages", "Use names, numbers, familiar words, and layout to understand signs, labels, schedules, and very short messages.", ["Platform 2", "Closed on Friday", "Meet me at six."]),
        "listening": ("Understanding careful basic speech", "Recognize familiar words and short questions when speech is clear, slow, and supported by context.", ["Where are you from?", "Would you like tea?", "Turn left here."]),
        "speaking": ("Basic personal exchanges", "Give simple personal information and respond to predictable everyday questions with memorized and recombined phrases.", ["I live in Damascus.", "I like football.", "Could I have coffee, please?"]),
        "pronunciation": ("Core English sound contrasts", "Use visible mouth position, air, and voicing to distinguish useful /p/–/b/ and /f/–/v/ contrasts.", ["pat–bat", "fan–van", "safe–save"]),
        "discourse": ("Joining short ideas", "Connect two short clauses with and, but, or because while keeping word order clear.", ["I work and I study.", "I like it, but it is expensive.", "I stayed home because I was tired."]),
    },
    "A2": {
        "grammar": ("Past events and future intentions", "Contrast the past simple for finished events with going to for intentions, using common time expressions.", ["I visited Aleppo last year.", "We did not miss the bus.", "I am going to apply tomorrow."]),
        "vocabulary": ("Travel, services, and work routines", "Build practical lexical sets with collocations for journeys, appointments, shopping, health, and routine workplace communication.", ["book a ticket", "make an appointment", "send an email"]),
        "reading": ("Reading connected everyday texts", "Find the main purpose and specific details in short emails, notices, menus, simple articles, and instructions.", ["Read for who, why, when, and what action is needed."]),
        "listening": ("Following everyday exchanges", "Follow the main point and key details in short announcements and familiar conversations at a clear natural pace.", ["Listen for destination, time, price, and requested action."]),
        "speaking": ("Handling routine transactions", "Ask follow-up questions, make requests, describe recent experiences, and repair simple misunderstandings.", ["Could you say that again?", "I went there two days ago.", "Do you mean this entrance?"]),
        "pronunciation": ("Dental fricatives and final clusters", "Practice /θ/ and /ð/ without replacing them with /t/, /d/, /s/, or /z/, then keep audible final consonants in common clusters.", ["think–sink", "then–den", "asked", "worked"]),
        "discourse": ("Sequencing a short account", "Organize a short story or explanation with first, then, after that, and finally.", ["First, we checked in. Then, we went through security."]),
    },
    "B1": {
        "grammar": ("Connected time and experience", "Use present perfect for experience or current relevance, past simple for finished time, and common future forms for arrangements and predictions.", ["I have finished the report.", "I finished it yesterday.", "We are meeting the client on Monday."]),
        "vocabulary": ("Independent life, work, and technology", "Develop topic vocabulary through definitions, word families, collocations, and reusable phrases for travel, projects, study, media, and technology.", ["meet a deadline", "solve a technical issue", "gain practical experience"]),
        "reading": ("Reading for main ideas and evidence", "Identify a text's main claim, supporting details, sequence, attitude, and the likely meaning of unfamiliar words from context.", ["Separate the writer's main point from examples and background details."]),
        "listening": ("Following clear extended speech", "Track the main points and important details of clear conversations, interviews, instructions, and short talks on familiar subjects.", ["Use signposts such as first, however, for example, and in conclusion."]),
        "speaking": ("Sustaining familiar conversations", "Give reasons, compare options, narrate events, and maintain a conversation with follow-up questions and clarification strategies.", ["In my view … because …", "The main difference is …", "What do you think about that?"]),
        "pronunciation": ("Stress, rhythm, and consonant contrasts", "Practice /p/–/b/, /f/–/v/, /θ/–/ð/ and place prominence on important content words in short thought groups.", ["I SENT the FILE on MONday.", "very–ferry", "three–tree"]),
        "discourse": ("Linking opinions and explanations", "Use contrast, reason, result, and example markers to produce a coherent extended turn.", ["Although it costs more, it is more reliable.", "For example, …", "As a result, …"]),
    },
    "B2": {
        "grammar": ("Flexible complex sentences", "Control conditionals, passive forms, relative clauses, reported ideas, and modal nuance while avoiding unnecessary complexity.", ["If we had tested it earlier, we would have found the fault.", "The proposal, which was revised twice, was approved."]),
        "vocabulary": ("Precise academic and professional lexis", "Choose precise words, natural collocations, stance phrases, and appropriate register for abstract topics, study, and professional discussion.", ["raise a concern", "a broadly effective approach", "The evidence suggests that …"]),
        "reading": ("Evaluating argument and viewpoint", "Recognize claims, evidence, implication, tone, bias, and contrasting viewpoints in longer factual and opinion texts.", ["Ask what the writer claims, what evidence supports it, and what assumptions remain unstated."]),
        "listening": ("Following detailed discussion", "Follow argument, attitude, implied agreement, and changes of direction in extended standard speech and familiar professional discussions.", ["Notice hedges, contrastive stress, and discourse markers that signal the speaker's position."]),
        "speaking": ("Developing and defending a position", "Present a clear viewpoint, respond to counterarguments, negotiate, and adjust register in sustained interaction.", ["I take your point; however, …", "A practical compromise would be …", "Let me clarify what I mean."]),
        "pronunciation": ("Prominence, reduction, and intelligibility", "Use thought groups, contrastive stress, common vowel reductions, and controlled linking to sound fluent without sacrificing intelligibility.", ["I said TUESday, not THURSday.", "We could have asked them earlier."]),
        "discourse": ("Structuring extended arguments", "Frame, develop, qualify, exemplify, and conclude an argument while making relationships between ideas explicit.", ["There are two main considerations.", "That said, …", "Taken together, these points suggest …"]),
    },
}


_DESIGN_GUIDANCE = {
    "vocabulary": (
        "Teach a small lexical set through definition, natural collocation, and a complete example. "
        "Then check meaning in a new context and require recall of the same word or phrase."
    ),
    "grammar": (
        "Explain one form-meaning contrast, show a positive and contrasting example, then progress "
        "from recognition to a controlled blank and sentence construction."
    ),
    "reading": (
        "Teach one explicit reading strategy. Each text question must point to one sentence of evidence; "
        "distractors must be plausible but absent or contradicted, never additional true details."
    ),
    "listening": (
        "Teach one explicit listening strategy such as signposts or key-detail notes. Each transcript must "
        "support exactly one option; do not ask plural questions when only one answer can be selected."
    ),
    "speaking": (
        "Teach a reusable interaction move such as giving a reason, comparing, clarifying, or asking a "
        "follow-up. Practise the language used to perform that move; never grade the learner's opinion."
    ),
    "pronunciation": (
        "Give concrete articulation or prominence guidance. Every practice item must actually contain its "
        "target sound or pattern, and contrast examples must not be recycled under unrelated sounds."
    ),
    "discourse": (
        "Teach the meaning and position of one relationship marker, then practise choosing it and ordering "
        "ideas into a coherent short turn."
    ),
}


def seed_records() -> tuple[dict, list[dict], list[dict]]:
    source = dict(SOURCE)
    curated_templates = {
        level: {
            domain: get_curated_template(level, domain)
            for domain in domains
        }
        for level, domains in _LEVEL_CONTENT.items()
    }
    source["checksum"] = hashlib.sha256(
        json.dumps(
            {
                "level_content": _LEVEL_CONTENT,
                "design_guidance": _DESIGN_GUIDANCE,
                "curated_templates": curated_templates,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    skills: list[dict] = []
    chunks: list[dict] = []
    previous_by_domain: dict[str, str] = {}
    for level, domains in _LEVEL_CONTENT.items():
        for domain, (title, explanation, examples) in domains.items():
            skill_id = f"{domain}.{level.lower()}.core"
            lesson_template = curated_templates[level][domain]
            skills.append(
                {
                    "id": skill_id,
                    "domain": domain,
                    "cefr_level": level,
                    "title": title,
                    "description": explanation,
                    "outcomes": [f"Use {title.lower()} in a level-appropriate task."],
                    "l1_tags": [],
                    "prerequisites": [previous_by_domain[domain]] if domain in previous_by_domain else [],
                }
            )
            content = (
                f"Teaching objective: {title}.\n"
                f"Reviewed guidance: {explanation}\n"
                f"Examples: {' | '.join(examples)}\n"
                f"Reviewed activity design: {_DESIGN_GUIDANCE[domain]}\n"
                f"Reviewed lesson anchors:\n{template_search_text(lesson_template)}\n"
                "Use the examples as language anchors rather than trivia. Keep all language within the "
                "tagged CEFR level and make every scored task have one demonstrably correct answer."
            )
            chunks.append(
                {
                    "id": f"core_{level.lower()}_{domain}_001",
                    "source_id": source["id"],
                    "object_type": f"{domain}_teaching_object",
                    "content": content,
                    "metadata": {
                        "cefr": [level],
                        "skill_ids": [skill_id],
                        "activity_types": [
                            item["type"] for item in lesson_template["activities"]
                        ],
                        "topics": ["everyday", "work", "travel", "technology"],
                        "l1_tags": [],
                        "prerequisite_skill_ids": skills[-1]["prerequisites"],
                        "lesson_template": lesson_template,
                    },
                    "review_status": "reviewed",
                }
            )
            previous_by_domain[domain] = skill_id
    return source, skills, chunks
