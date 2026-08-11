"""Learning-plan pronunciation target authorization."""

from sqlalchemy.exc import SQLAlchemyError

from .database import session_scope
from .service_errors import PlpInvalidAttemptError, PlpNotFoundError
from .service_grading import _normalize_text_answer, _practice_item_text
from .service_identity import _database_error


class PlpPronunciationMixin:
    def validate_pronunciation_target(self, activity_id: str, target: str) -> str:
        try:
            with session_scope() as session:
                lesson = self._find_active_lesson_by_activity(session, activity_id)
                activity = next(
                    item
                    for item in lesson.content["content"]["activities"]
                    if item["id"] == activity_id
                )
                if activity["type"] != "pronunciation_drill":
                    raise PlpInvalidAttemptError(
                        "the selected lesson activity is not a pronunciation check"
                    )
                normalized = _normalize_text_answer(target)
                allowed = {
                    _normalize_text_answer(_practice_item_text(item)): item
                    for item in activity["data"].get("practice_items", [])
                }
                if normalized not in allowed:
                    raise PlpInvalidAttemptError(
                        "choose one of this lesson's assigned pronunciation targets"
                    )
                return _practice_item_text(allowed[normalized])
        except StopIteration as exc:
            raise PlpNotFoundError("activity was not found in the active plan") from exc
        except SQLAlchemyError as exc:
            raise _database_error(exc) from exc
