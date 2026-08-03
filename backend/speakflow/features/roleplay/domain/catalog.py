from __future__ import annotations

import re


MIN_TURNS_FOR_EVALUATION = 4
MIN_WORDS_FOR_LANGUAGE_EVALUATION = 30
MIN_SPOKEN_WORDS = 30
MIN_VOICED_SECONDS = 15.0

_WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")

_OBJECTIVE_EVIDENCE_PATTERNS: dict[str, dict[str, tuple[str, ...]]] = {
    "airport_check_in": {
        "destination": (
            r"\b(?:fly|flying|travel|travelling|going)\b.{0,35}\bto\b",
            r"\bdestination\s+(?:is|will be)\b",
        ),
        "identification": (r"\b(?:passport|identification|id)\b",),
        "baggage": (r"\b(?:bag|bags|baggage|luggage|suitcase|suitcases)\b",),
        "seat": (r"\b(?:window|aisle|middle|seat)\b",),
    },
    "hotel_check_in": {
        "reservation": (r"\b(?:reservation|booking|booked|room)\b",),
        "name": (r"\b(?:my name is|under the name|name is)\b",),
        "dates": (r"\b(?:night|nights|staying|until|check out|checkout)\b",),
        "request": (r"\b(?:could i|can i|may i|i would like)\b",),
    },
    "asking_directions": {
        "destination": (r"\b(?:get to|find|go to|looking for)\b",),
        "route": (r"\b(?:how do i|how can i|which way|directions)\b",),
        "clarify": (r"\b(?:repeat|again|do you mean|left or right)\b",),
        "confirm": (r"\b(?:so i|then i|i should)\b",),
    },
    "restaurant_order": {
        "meal": (r"\b(?:i would like|i'll have|i will have|order)\b",),
        "drink": (r"\b(?:drink|water|coffee|tea|juice|soda)\b",),
        "bill": (r"\b(?:bill|check|pay)\b",),
    },
    "cafe_small_talk": {
        "question": (r"\?$",),
        "closing": (r"\b(?:goodbye|see you|nice talking|have a good)\b",),
    },
    "job_interview": {
        "introduction": (r"\b(?:my name is|i am|i'm)\b",),
        "experience": (r"\b(?:experience|worked|work at|work in)\b",),
        "strength": (r"\b(?:strength|good at|skilled|skill)\b",),
        "question": (r"\?$",),
    },
    "business_meeting": {
        "idea": (r"\b(?:i suggest|i propose|my idea|we should)\b",),
        "reason": (r"\b(?:because|reason|so that|in order to)\b",),
        "concern": (r"\b(?:i understand|however|but|concern)\b",),
        "next_step": (r"\b(?:next step|let's|we will|we should now)\b",),
    },
}


def _objective(
    objective_id: str,
    label: str,
    *,
    weight: int = 1,
    required: bool = True,
) -> dict:
    return {
        "id": objective_id,
        "label": label,
        "weight": weight,
        "required": required,
    }


def _rubric(
    rubric_id: str,
    label: str,
    description: str,
    *,
    weight: int = 1,
) -> dict:
    return {
        "id": rubric_id,
        "label": label,
        "description": description,
        "weight": weight,
    }


BUILTIN_SCENARIOS: tuple[dict, ...] = (
    {
        "id": "airport_check_in",
        "category": "Travel",
        "icon": "✈️",
        "title": "Airport Check-in",
        "description": "Check in for a flight and obtain your boarding pass.",
        "ai_role": "airline check-in agent",
        "learner_role": "passenger",
        "opening": "Good morning. Welcome to the check-in desk. Where are you flying today?",
        "objectives": [
            _objective("destination", "State your destination", weight=2),
            _objective("identification", "Respond to the identification request"),
            _objective("baggage", "Answer a baggage question"),
            _objective("seat", "Choose or confirm a seat preference"),
        ],
        "target_language": [
            "I am flying to",
            "Here is my passport",
            "I have one bag",
            "I would prefer",
        ],
        "evaluation_rubric": [
            _rubric(
                "travel_information",
                "Travel information",
                "Communicates the requested flight, identity, baggage, and seat details clearly and consistently.",
                weight=2,
            ),
            _rubric(
                "check_in_management",
                "Check-in management",
                "Responds appropriately to the agent and moves the check-in transaction toward completion.",
            ),
        ],
    },
    {
        "id": "hotel_check_in",
        "category": "Travel",
        "icon": "🏨",
        "title": "Hotel Check-in",
        "description": "Check into a hotel and confirm the important booking details.",
        "ai_role": "hotel receptionist",
        "learner_role": "guest",
        "opening": "Welcome to the hotel. How may I help you?",
        "objectives": [
            _objective("reservation", "Explain that you have or need a reservation", weight=2),
            _objective("name", "Give the reservation name"),
            _objective("dates", "Confirm the stay dates"),
            _objective("request", "Make one practical room request"),
        ],
        "target_language": [
            "I have a reservation",
            "It is under the name",
            "I am staying until",
            "Could I have",
        ],
        "evaluation_rubric": [
            _rubric(
                "booking_clarity",
                "Booking clarity",
                "Communicates reservation names, dates, and booking details without contradictions.",
                weight=2,
            ),
            _rubric(
                "request_politeness",
                "Practical requests",
                "Makes a clear, appropriately polite hotel request and responds to follow-up questions.",
            ),
        ],
    },
    {
        "id": "asking_directions",
        "category": "Travel",
        "icon": "🗺️",
        "title": "Asking for Directions",
        "description": "Ask for directions, clarify the route, and confirm where to go.",
        "ai_role": "helpful local resident",
        "learner_role": "visitor",
        "opening": "Hello. You look a little lost. Can I help you find somewhere?",
        "objectives": [
            _objective("destination", "Say where you want to go", weight=2),
            _objective("route", "Ask how to reach it"),
            _objective("clarify", "Clarify one part of the directions"),
            _objective("confirm", "Confirm the route before leaving"),
        ],
        "target_language": [
            "How can I get to",
            "Do I turn",
            "Could you repeat",
            "So I should",
        ],
        "evaluation_rubric": [
            _rubric(
                "route_clarification",
                "Route clarification",
                "Asks focused questions when a direction or landmark is unclear.",
            ),
            _rubric(
                "route_confirmation",
                "Route confirmation",
                "Accurately restates the essential route before ending the exchange.",
                weight=2,
            ),
        ],
    },
    {
        "id": "restaurant_order",
        "category": "Food & Dining",
        "icon": "🍽️",
        "title": "Ordering at a Restaurant",
        "description": "Order a meal, handle a follow-up question, and request the bill.",
        "ai_role": "restaurant server",
        "learner_role": "customer",
        "opening": "Welcome. Are you ready to order, or would you like another minute?",
        "objectives": [
            _objective("meal", "Order a meal", weight=2),
            _objective("drink", "Choose a drink"),
            _objective("follow_up", "Answer a follow-up question about the order"),
            _objective("bill", "Request the bill"),
        ],
        "target_language": [
            "I would like",
            "Could I have",
            "Without",
            "Could we have the bill",
        ],
        "evaluation_rubric": [
            _rubric(
                "order_specificity",
                "Order specificity",
                "Makes the meal and drink order sufficiently specific and handles requested choices.",
                weight=2,
            ),
            _rubric(
                "service_language",
                "Service language",
                "Uses clear, appropriately polite language for requests, changes, and the bill.",
            ),
        ],
    },
    {
        "id": "cafe_small_talk",
        "category": "Food & Dining",
        "icon": "☕",
        "title": "Café Small Talk",
        "description": "Start and maintain a friendly short conversation at a café.",
        "ai_role": "friendly café customer",
        "learner_role": "another customer",
        "opening": "Hi. Is anyone sitting here?",
        "objectives": [
            _objective("opening", "Respond naturally to the opening"),
            _objective("topic", "Introduce or develop a small-talk topic", weight=2),
            _objective("question", "Ask a relevant follow-up question"),
            _objective("closing", "Close the conversation politely"),
        ],
        "target_language": [
            "Of course",
            "What do you think about",
            "How about you",
            "It was nice talking to you",
        ],
        "evaluation_rubric": [
            _rubric(
                "reciprocity",
                "Conversational reciprocity",
                "Builds on the partner's responses and balances sharing with relevant questions.",
                weight=2,
            ),
            _rubric(
                "natural_closing",
                "Natural closing",
                "Recognizes an appropriate moment to close and ends the conversation politely.",
            ),
        ],
    },
    {
        "id": "job_interview",
        "category": "Business",
        "icon": "💼",
        "title": "Job Interview",
        "description": "Introduce yourself and answer common interview questions with evidence.",
        "ai_role": "job interviewer",
        "learner_role": "candidate",
        "opening": "Thank you for coming today. Could you start by telling me about yourself?",
        "objectives": [
            _objective("introduction", "Give a relevant professional introduction", weight=2),
            _objective("experience", "Describe one useful experience", weight=2),
            _objective("strength", "Explain one strength with an example"),
            _objective("question", "Ask the interviewer one relevant question"),
        ],
        "target_language": [
            "I have experience in",
            "For example",
            "One of my strengths is",
            "Could you tell me more about",
        ],
        "evaluation_rubric": [
            _rubric(
                "professional_relevance",
                "Professional relevance",
                "Keeps answers relevant to the role and presents experience in a professional way.",
            ),
            _rubric(
                "supporting_evidence",
                "Supporting evidence",
                "Supports strengths and experience with concrete, understandable examples.",
                weight=2,
            ),
        ],
    },
    {
        "id": "business_meeting",
        "category": "Business",
        "icon": "📊",
        "title": "Business Meeting",
        "description": "Present an idea, respond to a concern, and agree on a next step.",
        "ai_role": "meeting colleague",
        "learner_role": "team member",
        "opening": "Let us begin. What idea would you like the team to consider?",
        "objectives": [
            _objective("idea", "Present a clear idea", weight=2),
            _objective("reason", "Give a reason or supporting detail"),
            _objective("concern", "Respond to a concern or question", weight=2),
            _objective("next_step", "Agree on a concrete next step"),
        ],
        "target_language": [
            "I suggest",
            "The main reason is",
            "I understand your concern",
            "The next step should be",
        ],
        "evaluation_rubric": [
            _rubric(
                "proposal_clarity",
                "Proposal clarity",
                "Presents a focused proposal with a relevant reason or supporting detail.",
                weight=2,
            ),
            _rubric(
                "collaborative_response",
                "Collaborative response",
                "Acknowledges concerns constructively and helps establish a concrete next step.",
            ),
        ],
    },
)

_BUILTIN_BY_ID = {item["id"]: item for item in BUILTIN_SCENARIOS}
