from tests.plp_test_support import *


class PlpGeneratorTestBase(unittest.TestCase):
    @staticmethod
    def _valid_listening_response():
        payload = {
            "title": "Listening for key details",
            "description": "Follow a clear conversation about technology.",
            "intro": "Listen for the main idea and its supporting detail.",
            "activities": {
                "concept": [
                    {
                        "explanation": "Contrast markers such as however signal that the speaker is changing direction.",
                        "key_points": [
                            "Listen for however before an important contrast",
                            "Write only the detail that answers the question",
                        ],
                        "examples": [
                            "The battery improved; however, the camera stayed the same."
                        ],
                        "native_hint": None,
                    }
                ],
                "listening_comprehension": [
                    {
                        "title": "A useful phone update",
                        "transcript": "The update improves battery life. However, the camera quality remains unchanged.",
                        "question": {
                            "prompt": "Which feature does the update improve?",
                            "options": [
                                {"id": "a", "text": "Battery life"},
                                {"id": "b", "text": "Screen size"},
                                {"id": "c", "text": "Call quality"},
                            ],
                            "correct_option_id": "a",
                            "explanation": "Battery life is the only feature described as improved.",
                        },
                        "voice": "american",
                    },
                    {
                        "title": "Choosing a smartwatch",
                        "transcript": "Maya compares three watches. She chooses the Nova because its battery lasts for five days.",
                        "question": {
                            "prompt": "Why does Maya choose the Nova watch?",
                            "options": [
                                {"id": "a", "text": "Its battery lasts longer"},
                                {"id": "b", "text": "It has a brighter screen"},
                                {"id": "c", "text": "It includes free headphones"},
                            ],
                            "correct_option_id": "a",
                            "explanation": "She chooses it because its battery lasts for five days.",
                        },
                        "voice": "american",
                    },
                ],
            },
        }
        response = Mock()
        response.choices = [Mock(message=Mock(content=json.dumps(payload)))]
        return response

    @staticmethod
    def _generate_listening(generator):
        return generator.generate(
            specification={
                "domain": "listening",
                "title": "Listening for key details",
                "description": "Follow clear speech.",
                "cefr_level": "B1",
                "skill_ids": ["listening.b1.core"],
            },
            lesson_key="w01_l01_listening",
            chunks=[
                RetrievedChunk(
                    id="core_b1_listening_001",
                    source_id="project_core_curriculum_v1",
                    content="Teach signposts and distinguish main ideas from details.",
                    metadata={"skill_ids": ["listening.b1.core"]},
                    score=1.0,
                )
            ],
            support_language="Arabic",
        )
