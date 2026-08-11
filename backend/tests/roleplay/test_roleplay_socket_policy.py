from __future__ import annotations

import unittest

from speakflow.features.learning_plan.engine.service import PlpConflictError
from speakflow.features.roleplay.application.roleplay_socket_policy import (
    RoleplayTurnInputError,
    safe_roleplay_turn_error,
    validate_roleplay_session_binding,
)


class RoleplaySocketPolicyTests(unittest.TestCase):
    def test_connection_cannot_switch_between_roleplay_sessions(self) -> None:
        validate_roleplay_session_binding(None, "session-one")
        validate_roleplay_session_binding("session-one", "session-one")
        with self.assertRaises(PlpConflictError):
            validate_roleplay_session_binding("session-one", "session-two")

    def test_only_deliberately_safe_turn_errors_are_exposed(self) -> None:
        safe = RoleplayTurnInputError("no clear speech was detected")
        self.assertEqual(safe_roleplay_turn_error(safe), str(safe))
        self.assertEqual(
            safe_roleplay_turn_error(ValueError("/tmp/private-decoder-path")),
            "The roleplay turn could not be processed.",
        )


if __name__ == "__main__":
    unittest.main()
