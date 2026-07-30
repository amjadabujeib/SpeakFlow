from __future__ import annotations

import copy
import hashlib
import json
import unittest

from plp.planner import PlanningSkill, build_outline
from plp.retrieval import RetrievedChunk, RetrievedConcept
from plp.schemas import LearnerProfileInput
from plp.seed import seed_records
from plp.service import _sanitize_content
from plp.generator import GenerationError
from plp.weekly_mission import (
    ContextRealization,
    LessonSurface,
    StimulusRealization,
    ChoiceRealization,
    WeeklyMissionGenerator,
    WeeklyScenarioDraft,
    _parse_weekly_draft,
    _scored_fingerprints,
    _failed_generation_json,
    compile_week,
    prepare_week,
    weekly_scenario_schema,
)


def _week_one_fixture():
    source, skill_rows, chunk_rows = seed_records()
    skills = [
        PlanningSkill(
            id=item["id"],
            domain=item["domain"],
            level=item["cefr_level"],
            title=item["title"],
            description=item["description"],
            outcomes=item["outcomes"],
        )
        for item in skill_rows
    ]
    profile = LearnerProfileInput(
        cefr_level="B1",
        native_language="Arabic",
        learning_goals=["Speak confidently", "Communicate at work"],
        interests=["Technology", "Travel"],
    )
    outline = build_outline(profile, skills)
    week = outline["weeks"][0]
    lesson_shells = []
    for lesson in week["units"][0]["lessons"]:
        shell = copy.deepcopy(lesson)
        shell["week_sequence"] = week["sequence"]
        lesson_shells.append(shell)

    required_skill_ids = {
        skill_id
        for lesson in lesson_shells
        for skill_id in lesson["skill_ids"]
    }
    chunks = []
    for item in chunk_rows:
        if not required_skill_ids.intersection(item["metadata"]["skill_ids"]):
            continue
        chunks.append(
            RetrievedChunk(
                id=item["id"],
                source_id=item["source_id"],
                content=item["content"],
                metadata=copy.deepcopy(item["metadata"]),
                score=1.0,
                content_hash=hashlib.sha256(item["content"].encode("utf-8")).hexdigest(),
            )
        )
    prepared = prepare_week(
        lessons=lesson_shells,
        chunks=chunks,
        support_language="Arabic",
    )
    return source, lesson_shells, chunks, prepared


def _valid_draft(prepared) -> WeeklyScenarioDraft:
    lesson_surfaces = [
        LessonSurface(
            lesson_key=lesson["lesson_key"],
            title=f"Mission surface {index}",
            description=f"Complete part {index} of the fictional weekly mission.",
            intro=f"Use the supplied evidence to complete mission step {index}.",
        )
        for index, lesson in enumerate(prepared.lessons, start=1)
    ]
    contexts = []
    for index, request in enumerate(prepared.context_requests.values(), start=1):
        contexts.append(
            ContextRealization(
                request_id=request.request_id,
                sentence=(
                    f"The fictional case {index} uses {request.required_phrase} "
                    "in a clear context."
                ),
                learner_definition=(
                    {
                        "device": "an instrument made for one clear purpose",
                    }.get(
                        request.prototype_target.title.casefold(),
                        "a connected system used to share information",
                    )
                    if request.prototype_target is not None
                    else ""
                ),
            )
        )
    prototype_terms = [
        request.prototype_target.title
        for request in prepared.context_requests.values()
        if request.prototype_target is not None
    ]
    teaching_stimulus_ids = [
        request.request_id
        for request in prepared.stimulus_requests.values()
        if not request.checkpoint
    ]
    assigned_terms = {
        request_id: [
            term
            for term_index, term in enumerate(prototype_terms)
            if teaching_stimulus_ids
            and teaching_stimulus_ids[term_index % len(teaching_stimulus_ids)] == request_id
        ]
        for request_id in teaching_stimulus_ids
    }
    stimuli = []
    for index, request in enumerate(prepared.stimulus_requests.values(), start=1):
        stimuli.append(
            StimulusRealization(
                request_id=request.request_id,
                title=f"Fictional input {index}",
                text=(
                    f"{request.canonical_answer}. "
                    f"This supplied detail resolves fictional case {index}."
                    " The team reviews the supplied notes before meeting."
                    " Each member compares the available choices carefully."
                    " They discuss the evidence and agree on one practical next step."
                    + "".join(
                        f" The fictional team uses {term}."
                        for term in assigned_terms.get(request.request_id, [])
                    )
                ),
                prompt=f"Which detail resolves fictional input {index}?",
                distractors=[
                    f"Unsupported alternative {index} alpha",
                    f"Unsupported alternative {index} beta",
                ],
                explanation="The supplied input states this detail directly.",
            )
        )
    choices = []
    for index, request in enumerate(prepared.choice_requests.values(), start=1):
        choices.append(
            ChoiceRealization(
                request_id=request.request_id,
                prompt=f"Which response completes fictional checkpoint item {index}?",
                distractors=[
                    f"Unsupported checkpoint {index} alpha",
                    f"Unsupported checkpoint {index} beta",
                ],
                explanation="The reviewed language target supports this response.",
            )
        )
    return WeeklyScenarioDraft(
        scenario_title="A fictional team solves a familiar device problem",
        setting="A fictional community workshop with no current products or events.",
        roles=["learner", "fictional support partner"],
        lesson_surfaces=lesson_surfaces,
        context_realizations=contexts,
        stimulus_realizations=stimuli,
        choice_realizations=choices,
    )


def _compile(prepared, draft):
    return compile_week(
        prepared=prepared,
        draft=draft,
        provider="groq",
        model="test-scenario-writer",
        response_hash="a" * 64,
    )


def _replace_draft(draft: WeeklyScenarioDraft, **changes) -> WeeklyScenarioDraft:
    payload = draft.model_dump(mode="python")
    payload.update(changes)
    return WeeklyScenarioDraft.model_validate(payload)


class _FakeStructuredWriter:
    def __init__(self, draft: WeeklyScenarioDraft, *, provider: str = "groq"):
        self.provider = provider
        self.model_name = "fake-structured-writer"
        self.last_request_metadata = {
            "request_count": 1,
            "prompt_tokens": 100,
            "completion_tokens": 200,
            "total_tokens": 300,
        }
        self.draft = draft
        self.calls: list[dict] = []

    def request_structured(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return self.draft.model_dump_json()


class WeeklyMissionCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source, cls.lessons, cls.chunks, cls.prepared = _week_one_fixture()
        cls.draft = _valid_draft(cls.prepared)
        cls.compiled = _compile(cls.prepared, cls.draft)

    def test_compiles_one_generated_validated_payload_for_each_week_lesson(self):
        expected_keys = {lesson["lesson_key"] for lesson in self.lessons}
        self.assertEqual(set(self.compiled), expected_keys)
        self.assertEqual(len(self.compiled), 5)

    def test_provider_schema_uses_fixed_request_id_object_buckets(self):
        context_ids = list(self.prepared.context_requests)
        stimulus_ids = list(self.prepared.stimulus_requests)
        choice_ids = list(self.prepared.choice_requests)

        schema = weekly_scenario_schema(
            context_ids=context_ids,
            stimulus_ids=stimulus_ids,
            choice_ids=choice_ids,
            lesson_ids=[item["lesson_key"] for item in self.lessons],
        )

        properties = schema["properties"]
        for bucket, expected_ids in (
            ("context_realizations", context_ids),
            ("stimulus_realizations", stimulus_ids),
            ("choice_realizations", choice_ids),
        ):
            bucket_schema = properties[bucket]
            self.assertEqual(bucket_schema["type"], "object")
            self.assertEqual(bucket_schema["required"], expected_ids)
            self.assertEqual(set(bucket_schema["properties"]), set(expected_ids))
            self.assertFalse(bucket_schema["additionalProperties"])

    def test_fixed_request_id_objects_parse_into_typed_records(self):
        payload = self.draft.model_dump(mode="python")
        for bucket in (
            "context_realizations",
            "stimulus_realizations",
            "choice_realizations",
        ):
            payload[bucket] = {
                item.pop("request_id"): item for item in payload[bucket]
            }

        parsed = _parse_weekly_draft(json.dumps(payload))

        self.assertEqual(
            {item.request_id for item in parsed.stimulus_realizations},
            set(self.prepared.stimulus_requests),
        )
        pack_ids = {
            payload["weekly_pack"]["id"]
            for payload, _ in self.compiled.values()
        }
        self.assertEqual(len(pack_ids), 1)
        self.assertEqual(
            len(
                {
                    payload["content_instance_id"]
                    for payload, _ in self.compiled.values()
                }
            ),
            5,
        )

        hash_by_chunk = {chunk.id: chunk.content_hash for chunk in self.chunks}
        for lesson in self.lessons:
            payload, source_ids = self.compiled[lesson["lesson_key"]]
            provenance = payload["provenance"]
            self.assertEqual(provenance["origin"], "retrieval_generated")
            self.assertEqual(provenance["review_status"], "generated_validated")
            self.assertEqual(provenance["provider"], "groq")
            self.assertEqual(provenance["model"], "test-scenario-writer")
            self.assertEqual(
                provenance["validation"],
                {
                    "schema": "passed",
                    "cefr_limits": "passed",
                    "context_personalization": "passed",
                    "answer_support": "passed",
                    "checkpoint_freshness": "passed",
                },
            )
            self.assertEqual(provenance["answer_evidence_inserted"], [])
            self.assertTrue(
                set(provenance["input_context_extended"]).issubset(
                    self.prepared.stimulus_requests
                )
            )
            self.assertEqual(provenance["reviewed_anchor_preserved"], [])
            self.assertEqual(source_ids, [self.source["id"]])
            expected_chunk_ids = set(lesson["skill_ids"])
            actual_refs = {
                item["chunk_id"]: item["content_hash"]
                for item in provenance["source_chunks"]
            }
            self.assertEqual(
                actual_refs,
                {
                    self.prepared.chunks_by_skill[skill_id].id:
                    hash_by_chunk[self.prepared.chunks_by_skill[skill_id].id]
                    for skill_id in expected_chunk_ids
                },
            )
            self.assertTrue(all(actual_refs.values()))

    def test_weekly_generator_uses_one_structured_call_for_all_five_lessons(self):
        writer = _FakeStructuredWriter(self.draft)
        generated = WeeklyMissionGenerator(writer).generate(
            lessons=self.lessons,
            chunks=self.chunks,
            support_language="Arabic",
        )
        self.assertEqual(len(writer.calls), 1)
        self.assertEqual(writer.calls[0]["schema_name"], "plp_weekly_scenario")
        self.assertEqual(writer.calls[0]["max_tokens"], 3400)
        self.assertIn("messages", writer.calls[0])
        self.assertIn("schema", writer.calls[0])
        stimulus_bucket = writer.calls[0]["schema"]["properties"][
            "stimulus_realizations"
        ]
        stimulus_schema = next(iter(stimulus_bucket["properties"].values()))
        self.assertTrue(
            {"opening", "evidence", "closing"}.issubset(
                stimulus_schema["properties"]
            )
        )
        self.assertNotIn("sentences", stimulus_schema["properties"])
        self.assertEqual(
            set(generated),
            {lesson["lesson_key"] for lesson in self.lessons},
        )
        self.assertEqual(len(generated), 5)

    def test_source_palette_is_optional_framing_and_recorded_in_provenance(self):
        concept = RetrievedConcept(
            id="cefr_j_profiles_2020:vocabulary:network",
            source_id="cefr_j_profiles_2020",
            title="network",
            cefr_level="B1",
            part_of_speech="noun",
            topic_tags=["technology"],
            definition="an interconnected system of people or things",
            ipa="ˈnɛtˌwɝk",
            reference_examples=("The network links every office.",),
            definition_source_id="princeton_wordnet_3_0",
            pronunciation_source_id="cmudict_local",
        )
        prepared = prepare_week(
            lessons=self.lessons,
            chunks=self.chunks,
            lexical_palette=[concept],
            support_language="Arabic",
        )
        self.assertFalse(
            any(
                request.purpose == "fill_blank"
                for request in prepared.context_requests.values()
            )
        )
        draft = _valid_draft(prepared)
        writer = _FakeStructuredWriter(draft)
        generated = WeeklyMissionGenerator(writer).generate(
            lessons=self.lessons,
            chunks=self.chunks,
            lexical_palette=[concept],
            support_language="Arabic",
        )

        request = json.loads(writer.calls[0]["messages"][1]["content"])
        expected = {
            "concept_id": concept.id,
            "source_id": concept.source_id,
            "term": "network",
            "part_of_speech": "noun",
            "cefr_level": "B1",
            "topic_tags": ["technology"],
            "definition": "an interconnected system of people or things",
            "definition_source_id": "princeton_wordnet_3_0",
            "pronunciation_source_id": "cmudict_local",
            "prototype_target": False,
        }
        self.assertEqual(request["lexical_palette"], [expected])
        for payload, _ in generated.values():
            self.assertEqual(
                payload["provenance"]["writer_request"]["candidate_concepts"],
                [expected],
            )
            self.assertEqual(
                payload["provenance"]["writer_request"]["prototype_targets"],
                [],
            )
        self.assertFalse(
            any(
                activity["data"].get("concept_id") == concept.id
                for payload, _ in generated.values()
                for activity in payload["content"]["activities"]
                if activity["type"] == "vocabulary_card"
            )
        )

    def test_prototype_definition_must_be_short_and_non_circular(self):
        concept = RetrievedConcept(
            id="cefr_j_profiles_2020:vocabulary:website",
            source_id="cefr_j_profiles_2020",
            title="website",
            cefr_level="A2",
            part_of_speech="noun",
            topic_tags=["technology"],
            definition="a computer connected to the internet that maintains pages",
            ipa="ˈwɛbˌsaɪt",
            reference_examples=(),
            definition_source_id="princeton_wordnet_3_0",
            pronunciation_source_id="cmudict_local",
        )
        companion = RetrievedConcept(
            id="cefr_j_profiles_2020:vocabulary:device",
            source_id="cefr_j_profiles_2020",
            title="device",
            cefr_level="B1",
            part_of_speech="noun",
            topic_tags=["technology"],
            definition="an instrument made for a particular purpose",
            ipa="dɪˈvaɪs",
            reference_examples=("The team checks the device.",),
            definition_source_id="princeton_wordnet_3_0",
            pronunciation_source_id="cmudict_local",
        )
        prepared = prepare_week(
            lessons=self.lessons,
            chunks=self.chunks,
            lexical_palette=[concept, companion],
            support_language="Arabic",
        )
        # The reviewed learner gloss repairs this known dated WordNet entry
        # even if the surface writer repeats a circular source definition.
        draft = _valid_draft(prepared)
        values = [item.model_dump() for item in draft.context_realizations]
        prototype = next(
            item for item in values if "prototype_vocab" in item["request_id"]
        )
        prototype["learner_definition"] = "a website on the internet"
        compiled = _compile(
            prepared,
            _replace_draft(draft, context_realizations=values),
        )
        card = next(
            activity
            for payload, _ in compiled.values()
            for activity in payload["content"]["activities"]
            if activity["type"] == "vocabulary_card"
            and activity["data"].get("concept_id") == concept.id
        )
        self.assertEqual(
            card["data"]["definition"],
            "a group of connected pages that you can visit on the internet",
        )
        self.assertEqual(
            card["data"]["definition_origin"],
            "reviewed_project_gloss",
        )

    def test_two_weekly_words_replace_vocabulary_placeholders_and_checks(self):
        concepts = [
            RetrievedConcept(
                id=f"cefr_j_profiles_2020:vocabulary:{word}",
                source_id="cefr_j_profiles_2020",
                title=word,
                cefr_level="B1",
                part_of_speech="noun",
                topic_tags=["technology"],
                definition=definition,
                ipa=ipa,
                reference_examples=(example,),
                definition_source_id="princeton_wordnet_3_0",
                pronunciation_source_id="cmudict_local",
            )
            for word, definition, ipa, example in (
                ("network", "an interconnected system of people or things", "ˈnɛtˌwɝk", "The network connects the project team."),
                ("device", "an instrument made for a particular purpose", "dɪˈvaɪs", "The group tests the device."),
            )
        ]
        prepared = prepare_week(
            lessons=self.lessons,
            chunks=self.chunks,
            lexical_palette=concepts,
            support_language="Arabic",
        )
        compiled = _compile(prepared, _valid_draft(prepared))
        vocabulary_lesson = next(item for item in self.lessons if item["type"] == "vocabulary")
        activities = compiled[vocabulary_lesson["lesson_key"]][0]["content"]["activities"]
        cards = [item for item in activities if item["type"] == "vocabulary_card"]
        self.assertEqual([item["data"]["word"] for item in cards], ["network", "device"])
        choice = next(item for item in activities if item["type"] == "multiple_choice")
        correct = next(
            option["text"]
            for option in choice["data"]["options"]
            if option["id"] == choice["data"]["correct_option_id"]
        )
        self.assertEqual(correct, "network")
        fill = next(item for item in activities if item["type"] == "fill_blank")
        self.assertEqual(fill["data"]["accepted_answers"], ["device"])
        self.assertIn("___", fill["data"]["prompt"])

    def test_generated_stimulus_owns_a_supported_scenario_fact(self):
        values = [item.model_dump() for item in self.draft.stimulus_realizations]
        request = self.prepared.stimulus_requests[values[0]["request_id"]]
        values[0]["answer"] = "Project board"
        values[0]["text"] = (
            "The team records every task on the Project board. "
            "Members check the board before their daily meeting. "
            "They compare the listed deadlines and assigned roles. "
            "Everyone then confirms one practical next step for the project."
        )
        values[0]["distractors"] = ["Private notebook", "Paper calendar"]
        compiled = _compile(
            self.prepared,
            _replace_draft(self.draft, stimulus_realizations=values),
        )
        activity = compiled[request.lesson_key][0]["content"]["activities"][
            request.activity_index
        ]
        question = activity["data"]["question"]
        correct = next(
            option["text"]
            for option in question["options"]
            if option["id"] == question["correct_option_id"]
        )
        self.assertEqual(correct, "Project board")
        self.assertNotEqual(correct, request.canonical_answer)

    def test_lesson_titles_are_specific_and_compiler_owned(self):
        titles = [
            self.compiled[lesson["lesson_key"]][0]["title"]
            for lesson in self.lessons
        ]
        self.assertEqual(len(titles), len(set(titles)))
        self.assertEqual(
            titles[0],
            "Listen for details about a familiar technology issue",
        )
        self.assertTrue(titles[-1].startswith("Mission check: "))
        self.assertNotIn("Mission surface", " ".join(titles))

    def test_duplicate_writer_distractors_retain_reviewed_parallel_options(self):
        values = [item.model_dump() for item in self.draft.choice_realizations]
        request_id = next(
            item["request_id"]
            for item in values
            if self.prepared.choice_requests[item["request_id"]].checkpoint
        )
        request = self.prepared.choice_requests[request_id]
        value = next(item for item in values if item["request_id"] == request_id)
        value["distractors"] = ["Repeated wrong answer", "Repeated wrong answer"]
        malformed = _replace_draft(self.draft, choice_realizations=values)

        compiled = _compile(self.prepared, malformed)
        checkpoint_key = self.lessons[-1]["lesson_key"]
        payload = compiled[checkpoint_key][0]
        activity_index = int(request_id.rsplit(":", 1)[1])
        option_texts = {
            item["text"]
            for item in payload["content"]["activities"][activity_index]["data"][
                "options"
            ]
        }

        self.assertTrue(set(request.reviewed_distractors).issubset(option_texts))
        self.assertIn(
            request_id,
            payload["provenance"]["reviewed_distractors_preserved"],
        )

    def test_duplicate_cosmetic_surface_ids_are_rebound_to_planner_order(self):
        values = [item.model_dump() for item in self.draft.lesson_surfaces]
        values[1]["lesson_key"] = values[0]["lesson_key"]
        malformed = _replace_draft(self.draft, lesson_surfaces=values)

        compiled = _compile(self.prepared, malformed)

        self.assertEqual(
            set(compiled),
            {lesson["lesson_key"] for lesson in self.lessons},
        )
        self.assertTrue(
            all(
                payload["provenance"]["surface_ids_rebound"]
                for payload, _ in compiled.values()
            )
        )

    def test_failed_generation_cleanup_only_removes_non_output_fields(self):
        raw = {
            "scenario_title": "Fictional help desk",
            "setting": "A fictional office.",
            "roles": ["learner"],
            "lesson_surfaces": [],
            "context_realizations": [],
            "stimulus_realizations": [],
            "choice_realizations": [
                {
                    "request_id": "choice-1",
                    "prompt": "Which response fits?",
                    "distractors": ["Wrong one", "Wrong two"],
                    "explanation": "The reviewed target supports the answer.",
                    "prompt_goal": "echoed request metadata",
                    "canonical_correct_answer": "private input echo",
                }
            ],
            "unexpected_top_level": "discard me",
        }

        cleaned = json.loads(
            _failed_generation_json({"failed_generation": raw}) or "{}"
        )

        self.assertNotIn("unexpected_top_level", cleaned)
        choice = cleaned["choice_realizations"][0]
        self.assertEqual(choice["request_id"], "choice-1")
        self.assertNotIn("prompt_goal", choice)
        self.assertNotIn("canonical_correct_answer", choice)

    def test_writer_sentence_budget_has_headroom_below_the_hard_cefr_limit(self):
        hard_limit = self.lessons[0]["specification"]["cefr_realization"][
            "maximum_sentence_words"
        ]
        payload = self.prepared.writer_payload
        self.assertEqual(hard_limit, 18)
        self.assertEqual(payload["cefr_constraints"]["maximum_sentence_words"], 14)
        self.assertTrue(
            all(item["maximum_words"] == 14 for item in payload["context_requests"])
        )
        self.assertTrue(
            all(
                item["maximum_words_per_sentence"] == 14
                for item in payload["stimulus_requests"]
            )
        )

    def test_writer_payload_exposes_only_choice_intent_not_receptive_answers(self):
        serialized = json.dumps(self.prepared.writer_payload, ensure_ascii=False)
        for source_prompt in [
            request.source_prompt
            for request in self.prepared.stimulus_requests.values()
        ]:
            self.assertNotIn(source_prompt, serialized)
        for request in self.prepared.choice_requests.values():
            self.assertIn(request.source_prompt, serialized)

    def test_generation_attempt_changes_the_writer_variant_and_provenance(self):
        writer = _FakeStructuredWriter(self.draft)
        generated = WeeklyMissionGenerator(writer).generate(
            lessons=self.lessons,
            chunks=self.chunks,
            support_language="Arabic",
            generation_attempt=2,
        )
        request_payload = json.loads(writer.calls[0]["messages"][1]["content"])
        self.assertEqual(request_payload["generation_attempt"], 2)
        self.assertEqual(writer.calls[0]["temperature"], 0)
        self.assertEqual(len(request_payload["surface_retry_seed"]), 24)
        for payload, _ in generated.values():
            self.assertEqual(
                payload["provenance"]["writer_request"]["generation_attempt"],
                2,
            )
            self.assertEqual(
                payload["provenance"]["writer_request"]["surface_retry_seed"],
                request_payload["surface_retry_seed"],
            )

    def test_semantic_failure_still_spends_only_one_provider_call(self):
        values = [item.model_dump() for item in self.draft.stimulus_realizations]
        request = self.prepared.stimulus_requests[values[0]["request_id"]]
        values[0]["text"] = "This text omits the reviewed answer entirely."
        self.assertNotIn(request.canonical_answer, values[0]["text"])
        invalid = _replace_draft(self.draft, stimulus_realizations=values)
        writer = _FakeStructuredWriter(invalid)
        with self.assertRaisesRegex(
            GenerationError,
            r"weekly scenario failed local semantic validation",
        ):
            WeeklyMissionGenerator(writer).generate(
                lessons=self.lessons,
                chunks=self.chunks,
                support_language="Arabic",
            )
        self.assertEqual(len(writer.calls), 1)

    def test_weekly_generator_rejects_curated_provider_before_a_writer_call(self):
        writer = _FakeStructuredWriter(self.draft, provider="curated")
        with self.assertRaisesRegex(
            GenerationError,
            r"mission-v3 requires an explicit Groq or Ollama scenario writer",
        ):
            WeeklyMissionGenerator(writer).generate(
                lessons=self.lessons,
                chunks=self.chunks,
                support_language="Arabic",
            )
        self.assertEqual(writer.calls, [])

    def test_compiler_assigns_explicit_phases_and_exact_skill_bindings(self):
        for lesson in self.lessons[:-1]:
            payload, _ = self.compiled[lesson["lesson_key"]]
            activities = payload["content"]["activities"]
            self.assertTrue(activities)
            for activity in activities:
                self.assertIn(
                    activity["phase"],
                    {"learn", "guided_practice", "independent_check", "review"},
                )
                self.assertEqual(activity["skill_ids"], lesson["skill_ids"])
            if lesson["specification"]["lesson_role"] == "independent_transfer":
                scored = {
                    "multiple_choice", "fill_blank", "reading_comprehension",
                    "listening_comprehension", "sentence_order",
                }
                self.assertTrue(
                    all(
                        item["phase"] == "independent_check"
                        for item in activities
                        if item["type"] in scored
                    )
                )

        checkpoint = self.lessons[-1]
        checkpoint_payload, _ = self.compiled[checkpoint["lesson_key"]]
        checkpoint_activities = checkpoint_payload["content"]["activities"]
        self.assertEqual(
            [item["skill_ids"] for item in checkpoint_activities],
            [[skill_id] for skill_id in checkpoint["skill_ids"]],
        )
        self.assertEqual(
            {item["phase"] for item in checkpoint_activities},
            {"independent_check"},
        )

    def test_compiled_answers_are_compatible_with_public_sanitization(self):
        for lesson in self.lessons:
            private_content = self.compiled[lesson["lesson_key"]][0]["content"]
            public_content = _sanitize_content(private_content)
            self.assertIsNotNone(public_content)
            for private, public in zip(
                private_content["activities"],
                public_content["activities"],
                strict=True,
            ):
                self.assertEqual(public["phase"], private["phase"])
                self.assertEqual(public["skill_ids"], private["skill_ids"])
                data = public["data"]
                private_data = private["data"]
                if public["type"] == "multiple_choice":
                    self.assertIn("correct_option_id", private_data)
                    self.assertNotIn("correct_option_id", data)
                elif public["type"] == "fill_blank":
                    self.assertIn("accepted_answers", private_data)
                    self.assertNotIn("accepted_answers", data)
                elif public["type"] in {
                    "reading_comprehension", "listening_comprehension",
                }:
                    self.assertIn("correct_option_id", private_data["question"])
                    self.assertNotIn("correct_option_id", data["question"])
                elif public["type"] == "sentence_order":
                    self.assertIn("correct_order", private_data)
                    self.assertNotIn("correct_order", data)

    def test_checkpoint_does_not_reuse_a_teaching_prompt_answer_fingerprint(self):
        teaching = set()
        for lesson in self.lessons[:-1]:
            teaching.update(
                _scored_fingerprints(
                    self.compiled[lesson["lesson_key"]][0]["content"]
                )
            )
        checkpoint = _scored_fingerprints(
            self.compiled[self.lessons[-1]["lesson_key"]][0]["content"]
        )
        self.assertTrue(teaching)
        self.assertTrue(checkpoint)
        self.assertTrue(teaching.isdisjoint(checkpoint))

    def test_rejects_missing_request_ids(self):
        incomplete = _replace_draft(
            self.draft,
            context_realizations=self.draft.context_realizations[1:],
        )
        with self.assertRaisesRegex(ValueError, r"context realizations mismatch; missing="):
            _compile(self.prepared, incomplete)

    def test_contextualizes_a_copied_teaching_prompt_without_changing_its_answer(self):
        stimulus = self.draft.stimulus_realizations[0]
        request = self.prepared.stimulus_requests[stimulus.request_id]
        self.assertFalse(request.checkpoint)
        values = [item.model_dump() for item in self.draft.stimulus_realizations]
        values[0]["prompt"] = request.source_prompt
        copied = _replace_draft(self.draft, stimulus_realizations=values)
        compiled = _compile(self.prepared, copied)
        activity = compiled[request.lesson_key][0]["content"]["activities"][
            request.activity_index
        ]
        prompt = activity["data"]["question"]["prompt"]
        self.assertNotEqual(prompt, request.source_prompt)
        self.assertTrue(prompt.startswith("In lesson"))

    def test_duplicate_teaching_prompt_wording_gets_unique_position_context(self):
        values = [item.model_dump() for item in self.draft.stimulus_realizations]
        teaching_indexes = [
            index
            for index, item in enumerate(values)
            if not self.prepared.stimulus_requests[item["request_id"]].checkpoint
        ]
        self.assertGreaterEqual(len(teaching_indexes), 2)
        for index in teaching_indexes[:2]:
            values[index]["prompt"] = "Which supplied detail answers the question?"
        duplicate = _replace_draft(self.draft, stimulus_realizations=values)
        compiled = _compile(self.prepared, duplicate)
        prompts = []
        for index in teaching_indexes[:2]:
            request = self.prepared.stimulus_requests[values[index]["request_id"]]
            activity = compiled[request.lesson_key][0]["content"]["activities"][
                request.activity_index
            ]
            prompts.append(activity["data"]["question"]["prompt"])
        self.assertEqual(len(set(prompts)), 2)

    def test_checkpoint_uses_a_compiler_owned_literal_fact_prompt(self):
        values = [item.model_dump() for item in self.draft.stimulus_realizations]
        checkpoint_index = next(
            index
            for index, item in enumerate(values)
            if self.prepared.stimulus_requests[item["request_id"]].checkpoint
        )
        request = self.prepared.stimulus_requests[values[checkpoint_index]["request_id"]]
        values[checkpoint_index]["prompt"] = request.source_prompt
        copied = _replace_draft(self.draft, stimulus_realizations=values)
        compiled = _compile(self.prepared, copied)
        checkpoint = compiled[request.lesson_key][0]["content"]["activities"]
        index = int(request.request_id.rsplit(":", 1)[1])
        prompt = checkpoint[index]["data"]["question"]["prompt"]
        self.assertEqual(
            prompt,
            f"In checkpoint transcript {index + 1}, what key detail is stated?",
        )

    def test_rejects_stimulus_without_its_canonical_answer(self):
        values = [item.model_dump() for item in self.draft.stimulus_realizations]
        values[0]["text"] = "Only unrelated fictional evidence appears in this input."
        missing_answer = _replace_draft(self.draft, stimulus_realizations=values)
        with self.assertRaisesRegex(ValueError, r"does not state its declared answer"):
            _compile(self.prepared, missing_answer)

    def test_stated_writer_distractor_uses_reviewed_alternatives(self):
        values = [item.model_dump() for item in self.draft.stimulus_realizations]
        request = self.prepared.stimulus_requests[values[0]["request_id"]]
        leaked = values[0]["distractors"][0]
        values[0]["text"] = f"{values[0]['text']} {leaked}."
        leaked_distractor = _replace_draft(self.draft, stimulus_realizations=values)
        compiled = _compile(self.prepared, leaked_distractor)
        payload = compiled[request.lesson_key][0]
        activity = payload["content"]["activities"][request.activity_index]
        option_texts = {item["text"] for item in activity["data"]["question"]["options"]}
        self.assertNotIn(leaked, option_texts)
        self.assertTrue(set(request.reviewed_distractors).issubset(option_texts))
        self.assertIn(
            request.request_id,
            payload["provenance"]["reviewed_distractors_preserved"],
        )

    def test_structured_dialogue_turns_are_counted_separately(self):
        values = [item.model_dump() for item in self.draft.stimulus_realizations]
        request = self.prepared.stimulus_requests[values[0]["request_id"]]
        values[0]["text"] = ""
        values[0]["sentences"] = [
            f"Speaker one: {request.canonical_answer} with clear supporting evidence",
            "Speaker two: This separate fictional turn confirms the schedule",
            "Speaker one: The team checks every supplied detail before deciding",
            "Speaker two: Everyone agrees on one practical next step today",
        ]
        dialogue = _replace_draft(self.draft, stimulus_realizations=values)
        compiled = _compile(self.prepared, dialogue)
        self.assertEqual(len(compiled), 5)

    def test_fixed_three_part_provider_stimulus_compiles(self):
        values = [item.model_dump() for item in self.draft.stimulus_realizations]
        request = self.prepared.stimulus_requests[values[0]["request_id"]]
        values[0]["text"] = ""
        values[0]["opening"] = "The fictional team compares two tools for its project."
        values[0]["evidence"] = (
            f"The supplied notes identify {request.canonical_answer} as the key detail."
        )
        values[0]["closing"] = (
            "Everyone checks the evidence before agreeing on a practical next step."
        )
        fixed = _replace_draft(self.draft, stimulus_realizations=values)
        compiled = _compile(self.prepared, fixed)
        self.assertEqual(len(compiled), 5)

    def test_short_input_is_rejected_instead_of_padded_with_boilerplate(self):
        values = [item.model_dump() for item in self.draft.stimulus_realizations]
        request = self.prepared.stimulus_requests[values[0]["request_id"]]
        values[0]["text"] = (
            f"{request.canonical_answer}. Team checks. They agree."
        )
        short = _replace_draft(self.draft, stimulus_realizations=values)
        with self.assertRaisesRegex(ValueError, r"input minimum"):
            _compile(self.prepared, short)

    def test_rejects_learner_instruction_inside_listening_input(self):
        values = [item.model_dump() for item in self.draft.stimulus_realizations]
        request = next(
            self.prepared.stimulus_requests[item["request_id"]]
            for item in values
            if self.prepared.stimulus_requests[item["request_id"]].mode
            == "listening"
        )
        target = next(
            item for item in values if item["request_id"] == request.request_id
        )
        target["text"] = ""
        target["sentences"] = []
        target["opening"] = "The club shares a clear update with every member."
        target["evidence"] = (
            f"The notice identifies {request.canonical_answer} as the confirmed detail."
        )
        target["closing"] = "Please answer."
        malformed = _replace_draft(self.draft, stimulus_realizations=values)
        with self.assertRaisesRegex(ValueError, r"learner instructions"):
            _compile(self.prepared, malformed)

    def test_rejects_stimulus_prompt_repeated_inside_its_input(self):
        values = [item.model_dump() for item in self.draft.stimulus_realizations]
        request = self.prepared.stimulus_requests[values[0]["request_id"]]
        target = values[0]
        target["text"] = ""
        target["sentences"] = []
        target["opening"] = target["prompt"]
        target["evidence"] = (
            f"The supplied update confirms {request.canonical_answer} for the group."
        )
        target["closing"] = (
            "Everyone records the confirmed detail before making the final plan."
        )
        malformed = _replace_draft(self.draft, stimulus_realizations=values)
        with self.assertRaisesRegex(ValueError, r"learner instructions"):
            _compile(self.prepared, malformed)

    def test_rejects_multiple_sentences_inside_one_structured_element(self):
        values = [item.model_dump() for item in self.draft.stimulus_realizations]
        request = self.prepared.stimulus_requests[values[0]["request_id"]]
        values[0]["text"] = ""
        values[0]["sentences"] = [
            f"{request.canonical_answer}. Another sentence is hidden here."
        ]
        malformed = _replace_draft(self.draft, stimulus_realizations=values)
        with self.assertRaisesRegex(ValueError, r"one complete sentence or turn"):
            _compile(self.prepared, malformed)

    def test_preserves_reviewed_anchor_when_context_exceeds_cefr_limit(self):
        values = [item.model_dump() for item in self.draft.context_realizations]
        request = self.prepared.context_requests[values[0]["request_id"]]
        maximum = self.lessons[0]["specification"]["cefr_realization"][
            "maximum_sentence_words"
        ]
        values[0]["sentence"] = (
            f"{request.required_phrase} " + " ".join(f"extra{index}" for index in range(maximum + 1))
        )
        over_limit = _replace_draft(self.draft, context_realizations=values)
        compiled = _compile(self.prepared, over_limit)
        payload = compiled[request.lesson_key][0]
        self.assertEqual(
            payload["content"]["activities"][request.activity_index]["data"],
            self.prepared.templates[request.lesson_key]["activities"][
                request.activity_index
            ]["data"],
        )
        self.assertEqual(
            payload["provenance"]["reviewed_anchor_preserved"],
            [request.request_id],
        )
        self.assertEqual(
            payload["provenance"]["validation"]["context_personalization"],
            "reviewed_anchor_preserved",
        )

    def test_preserves_reviewed_anchor_when_required_phrase_is_missing(self):
        values = [item.model_dump() for item in self.draft.context_realizations]
        request = self.prepared.context_requests[values[0]["request_id"]]
        values[0]["sentence"] = "The fictional team discusses a different topic."
        missing_phrase = _replace_draft(self.draft, context_realizations=values)
        compiled = _compile(self.prepared, missing_phrase)
        payload = compiled[request.lesson_key][0]
        self.assertEqual(
            payload["provenance"]["reviewed_anchor_preserved"],
            [request.request_id],
        )

    def test_accepts_context_at_the_exact_hard_cefr_sentence_limit(self):
        values = [item.model_dump() for item in self.draft.context_realizations]
        request = self.prepared.context_requests[values[0]["request_id"]]
        maximum = self.lessons[0]["specification"]["cefr_realization"][
            "maximum_sentence_words"
        ]
        self.assertEqual(len(request.required_phrase.split()), 1)
        values[0]["sentence"] = (
            f"{request.required_phrase} "
            + " ".join(f"boundary{index}" for index in range(maximum - 1))
        )
        at_limit = _replace_draft(self.draft, context_realizations=values)
        compiled = _compile(self.prepared, at_limit)
        self.assertEqual(len(compiled), 5)

    def test_rejects_duplicate_output_ids(self):
        values = [item.model_dump() for item in self.draft.context_realizations]
        values[1]["request_id"] = values[0]["request_id"]
        duplicate = _replace_draft(self.draft, context_realizations=values)
        with self.assertRaisesRegex(ValueError, r"duplicate context ID"):
            _compile(self.prepared, duplicate)


if __name__ == "__main__":
    unittest.main()
