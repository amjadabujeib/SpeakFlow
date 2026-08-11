from tests.learning_plan.support.weekly_mission_test_support import (
    RetrievedConcept,
    WeeklyMissionCompilerTestBase,
    WeeklyMissionGenerator,
    _compile,
    _failed_generation_json,
    _FakeStructuredWriter,
    _parse_weekly_draft,
    _replace_draft,
    _valid_draft,
    json,
    prepare_week,
    weekly_scenario_schema,
)


class WeeklyMissionCompilationTests(WeeklyMissionCompilerTestBase):
    def test_compiles_one_generated_validated_payload_for_each_week_lesson(self):
        expected_keys = {lesson["lesson_key"] for lesson in self.lessons}
        self.assertEqual(set(self.compiled), expected_keys)
        self.assertEqual(len(self.compiled), 5)

    def test_pronunciation_skill_keeps_a_spoken_checkpoint_activity(self):
        checkpoint_key = self.lessons[-1]["lesson_key"]
        activities = self.compiled[checkpoint_key][0]["content"]["activities"]
        pronunciation = [
            item for item in activities if item["type"] == "pronunciation_drill"
        ]

        self.assertEqual(len(pronunciation), 1)
        self.assertEqual(pronunciation[0]["skill_ids"], ["pronunciation.b1.core"])

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
            payload[bucket] = {item.pop("request_id"): item for item in payload[bucket]}

        parsed = _parse_weekly_draft(json.dumps(payload))

        self.assertEqual(
            {item.request_id for item in parsed.stimulus_realizations},
            set(self.prepared.stimulus_requests),
        )
        pack_ids = {
            payload["weekly_pack"]["id"] for payload, _ in self.compiled.values()
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
                    self.prepared.chunks_by_skill[skill_id].id: hash_by_chunk[
                        self.prepared.chunks_by_skill[skill_id].id
                    ]
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
            {"opening", "evidence", "closing"}.issubset(stimulus_schema["properties"])
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
            "definition": ("a group of connected computers, devices, or people"),
            "definition_origin": "reviewed_project_gloss",
            "definition_source_id": "princeton_wordnet_3_0",
            "pronunciation_source_id": "cmudict_local",
            "selection_tier": "direct_interest",
            "previously_seen": False,
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
                (
                    "network",
                    "an interconnected system of people or things",
                    "ˈnɛtˌwɝk",
                    "The network connects the project team.",
                ),
                (
                    "device",
                    "an instrument made for a particular purpose",
                    "dɪˈvaɪs",
                    "The group tests the device.",
                ),
            )
        ]
        prepared = prepare_week(
            lessons=self.lessons,
            chunks=self.chunks,
            lexical_palette=concepts,
            support_language="Arabic",
        )
        compiled = _compile(prepared, _valid_draft(prepared))
        vocabulary_lesson = next(
            item for item in self.lessons if item["type"] == "vocabulary"
        )
        activities = compiled[vocabulary_lesson["lesson_key"]][0]["content"][
            "activities"
        ]
        cards = [item for item in activities if item["type"] == "vocabulary_card"]
        self.assertEqual(
            [item["data"]["word"] for item in cards], ["network", "device"]
        )
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
            self.compiled[lesson["lesson_key"]][0]["title"] for lesson in self.lessons
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
            "scenario_title": "Android help desk practice",
            "setting": "A simulated office case about a real project.",
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
