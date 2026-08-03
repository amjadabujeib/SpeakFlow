from tests.plp_test_support import *


class RetrievalIntegrationTests(unittest.TestCase):
    def test_reviewed_b1_pronunciation_query(self):
        try:
            retriever = CurriculumRetriever()
            try:
                with session_scope() as session:
                    results = retriever.retrieve(
                        session,
                        query="Arabic learner B1 TH sounds and sentence stress",
                        cefr_level="B1",
                        skill_ids=["pronunciation.b1.core"],
                    )
            finally:
                retriever.close()
        except Exception as exc:
            self.skipTest(f"local PostgreSQL/EmbeddingGemma unavailable: {exc}")
        self.assertEqual(results[0].id, "core_b1_pronunciation_001")
        self.assertTrue(all(item.metadata["cefr"] == ["B1"] for item in results))

    @classmethod
    def tearDownClass(cls):
        get_engine().dispose()


if __name__ == "__main__":
    unittest.main()
