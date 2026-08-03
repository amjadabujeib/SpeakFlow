from tests.plp_service_test_support import *


class ExactRetrievalTests(unittest.TestCase):
    def test_exact_retrieval_skips_embeddings_and_returns_stable_hashes(self):
        rows = [
            SimpleNamespace(
                id="chunk-z",
                source_id="source-z",
                content="Later lexical ID",
                metadata_json={"cefr": ["B1"], "skill_ids": ["skill.two"]},
                content_hash="z" * 64,
            ),
            SimpleNamespace(
                id="chunk-a",
                source_id="source-a",
                content="Earlier lexical ID",
                metadata_json={"cefr": ["B1"], "skill_ids": ["skill.one"]},
                content_hash="a" * 64,
            ),
        ]
        session = Mock()
        session.execute.return_value = _scalar_result(rows)
        retriever = CurriculumRetriever(client=Mock())
        retriever.embed = Mock(side_effect=AssertionError("embed must not run"))

        chunks = retriever.retrieve_exact(
            session,
            cefr_level="B1",
            skill_ids=["skill.two", "skill.one"],
        )

        retriever.embed.assert_not_called()
        self.assertEqual([item.id for item in chunks], ["chunk-a", "chunk-z"])
        self.assertEqual(
            [item.content_hash for item in chunks],
            ["a" * 64, "z" * 64],
        )

    def test_exact_retrieval_reports_each_missing_skill(self):
        row = SimpleNamespace(
            id="chunk-a",
            source_id="source-a",
            content="Only one skill is present",
            metadata_json={"cefr": ["B1"], "skill_ids": ["skill.one"]},
            content_hash="a" * 64,
        )
        session = Mock()
        session.execute.return_value = _scalar_result([row])
        retriever = CurriculumRetriever(client=Mock())
        retriever.embed = Mock(side_effect=AssertionError("embed must not run"))

        with self.assertRaisesRegex(RetrievalError, "skill.missing"):
            retriever.retrieve_exact(
                session,
                cefr_level="B1",
                skill_ids=["skill.one", "skill.missing"],
            )

        retriever.embed.assert_not_called()
