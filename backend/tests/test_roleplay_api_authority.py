from tests.pronunciation_test_support import *


class RoleplayApiAuthorityTests(unittest.TestCase):
    def test_client_authored_session_summary_endpoint_is_not_exposed(self):
        methods = {
            method
            for route in main.app.routes
            if getattr(route, "path", None) == "/api/roleplay/sessions"
            for method in (getattr(route, "methods", None) or set())
        }

        self.assertNotIn("POST", methods)

