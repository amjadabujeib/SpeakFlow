from tests.weekly_mission_test_support import *


class WeeklyMissionValidationTests(WeeklyMissionCompilerTestBase):
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
            r"weekly missions require the Groq scenario writer",
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
