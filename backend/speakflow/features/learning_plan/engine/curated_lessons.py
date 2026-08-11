from __future__ import annotations

import copy

SCORED_TYPES = {"pronunciation_drill", "multiple_choice", "fill_blank", "reading_comprehension", "listening_comprehension", "sentence_order"}


def get_curated_template(level: str, domain: str) -> dict:
    """Return a reviewed lesson object whose answer logic is human-authored."""
    try:
        return copy.deepcopy(_CURATED_LESSONS[level][domain])
    except KeyError as exc:
        raise ValueError(f"no curated lesson exists for {level} {domain}") from exc


def assessment_candidates(template: dict) -> list[dict]:
    return [copy.deepcopy(item) for item in template["activities"] if item["type"] in SCORED_TYPES]


def template_search_text(template: dict) -> str:
    parts = [template["title"], template["description"], template["intro"]]
    for item in template["activities"]:
        data = item["data"]
        parts.extend(str(data[key]) for key in ("word", "explanation", "sound_label", "prompt", "title", "passage", "transcript") if data.get(key))
        question = data.get("question")
        if question:
            parts.append(question["prompt"])
    return "\n".join(parts)


def _choice(prompt: str, correct: str, distractors: tuple[str, str], explanation: str, *, correct_position: int) -> dict:
    texts = list(distractors)
    texts.insert(correct_position, correct)
    options = [{"id": f"option_{index + 1}", "text": text} for index, text in enumerate(texts)]
    return {"prompt": prompt, "options": options, "correct_option_id": options[correct_position]["id"], "explanation": explanation}


def _fill(prompt: str, answer: str, explanation: str) -> dict:
    return {"prompt": prompt, "accepted_answers": [answer], "explanation": explanation}


def _order(prompt: str, chunks: tuple[str, ...], explanation: str) -> dict:
    correct_ids = [f"chunk_{index + 1}" for index in range(len(chunks))]
    # The visible chips must not start in the answer order.
    display_indexes = list(range(1, len(chunks), 2)) + list(range(0, len(chunks), 2))
    return {"prompt": prompt, "tokens": [{"id": correct_ids[index], "text": chunks[index]} for index in display_indexes], "correct_order": correct_ids, "explanation": explanation}


def _concept(explanation: str, key_points: list[str], examples: list[str]) -> dict:
    return {"explanation": explanation, "key_points": key_points, "examples": examples, "native_hint": None}


def _vocab(*, title: str, description: str, cards: tuple[dict, dict], check: dict, recall: dict) -> dict:
    return {"title": title, "description": description, "intro": "Learn two useful items in context, recognize their meaning, then recall one without options.", "activities": [*[{"type": "vocabulary_card", "data": card} for card in cards], {"type": "multiple_choice", "data": check}, {"type": "fill_blank", "data": recall}]}


def _card(word: str, part_of_speech: str, ipa: str, definition: str, example: str, collocations: list[str]) -> dict:
    return {"word": word, "part_of_speech": part_of_speech, "ipa": ipa, "definition": definition, "examples": [example], "collocations": collocations, "native_hint": None}


def _skill_lesson(title: str, description: str, intro: str, activities: list[dict]) -> dict:
    return {"title": title, "description": description, "intro": intro, "activities": activities}


def _nested(kind: str, *, title: str, text: str, question: dict) -> dict:
    data = {"title": title, "question": question}
    if kind == "reading_comprehension":
        data.update({"passage": text, "native_hint": None})
    else:
        data.update({"transcript": text, "voice": "american"})
    return {"type": kind, "data": data}


_CURATED_LESSONS = {
    "A1": {
        "vocabulary": _vocab(
            title="Everyday routine words",
            description="Use two high-frequency words to describe normal places and habits.",
            cards=(_card("usually", "adverb", "/ˈjuːʒuəli/", "on most days or in most situations", "I usually start work at nine.", ["usually go", "usually eat"]), _card("nearby", "adverb/adjective", "/ˌnɪrˈbaɪ/", "not far away", "There is a small shop nearby.", ["live nearby", "nearby shop"])),
            check=_choice("Which word means ‘not far away’?", "nearby", ("usually", "tomorrow"), "Nearby means ‘not far away.’", correct_position=1),
            recall=_fill("I ___ take the bus to school; I do it on most days.", "usually", "Usually describes something that happens on most days."),
        ),
        "grammar": _skill_lesson(
            "Be and the present simple",
            "Choose be for states and do-support for present-simple negatives.",
            "Notice the verb pattern first, then complete and build short present statements.",
            [
                {"type": "concept", "data": _concept("Use am, is, or are before a noun, adjective, or place. Use do not or does not before the base form of another present-simple verb.", ["I am; he or she is; you, we, and they are.", "After do not or does not, use the base verb."], ["She is at home.", "They do not drive."])},
                {"type": "multiple_choice", "data": _choice("Choose the correct sentence about one woman.", "She is ready.", ("She are ready.", "She do ready."), "She is ready is correct because she takes is.", correct_position=2)},
                {"type": "fill_blank", "data": _fill("They ___ not drive to work.", "do", "Use do in They do not drive because drive is the base verb.")},
                {"type": "sentence_order", "data": _order("Build a present-simple routine.", ("She", "works", "here", "every day."), "The complete sentence is: She works here every day.")},
            ],
        ),
        "reading": _skill_lesson(
            "Find practical details",
            "Use names, times, places, and action words in short messages and signs.",
            "First learn a simple scanning strategy, then use it on two short texts.",
            [
                {"type": "concept", "data": _concept("For a short practical text, read the question first and scan for the matching place, time, or action. You do not need to translate every word.", ["Circle the key word in the question.", "Match it to the same kind of detail in the text."], ["A where question needs a place.", "A when question needs a time or day."])},
                _nested("reading_comprehension", title="A change of place", text="Hi Lina. The café is closed today, so please meet me at the library at six. —Maya", question=_choice("Where should Lina meet Maya?", "At the library", ("At the café", "At the station"), "The message says, ‘meet me at the library,’ so the answer is At the library.", correct_position=1)),
                _nested("reading_comprehension", title="Bus information", text="BUS 12 — City Centre. Leaves from Gate 4 at 9:15. Tickets are sold on the bus.", question=_choice("Which gate does Bus 12 leave from?", "Gate 4", ("Gate 9", "Gate 12"), "The sign states Gate 4, so Gate 4 is the correct detail.", correct_position=0)),
                _nested("reading_comprehension", title="A short reminder", text="Please bring your blue notebook to Room 3 on Monday. The class starts at ten.", question=_choice("What should the learner bring?", "The blue notebook", ("A red folder", "A bus ticket"), "The reminder explicitly says to bring the blue notebook.", correct_position=2)),
            ],
        ),
        "listening": _skill_lesson(
            "Listen for one key detail",
            "Recognize clear times, places, and directions in careful speech.",
            "Predict the type of detail you need, listen once, then check on a second play.",
            [
                {"type": "concept", "data": _concept("Before listening, decide whether the question needs a time, place, person, or action. Listen for that detail instead of trying to remember every word.", ["Use the question to choose a listening target.", "Replay once to confirm, not to guess again."], ["When does it open? Listen for a time.", "Where do I turn? Listen for a place."])},
                _nested("listening_comprehension", title="Opening time", text="The pharmacy opens at eight in the morning. A pharmacist is available all day.", question=_choice("When does the pharmacy open?", "At eight", ("At six", "At ten"), "The speaker says the pharmacy opens at eight, so At eight is correct.", correct_position=2)),
                _nested("listening_comprehension", title="A simple direction", text="Walk straight for one minute. Turn left after the bank, then continue along the same street.", question=_choice("After which place should you turn left?", "The bank", ("The café", "The bookshop"), "The direction is ‘Turn left after the bank,’ so The bank is correct.", correct_position=1)),
                _nested("listening_comprehension", title="Meeting reminder", text="Remember, our meeting is in Room Two at four this afternoon. Please arrive five minutes early.", question=_choice("Where is the meeting?", "Room Two", ("Room Four", "The library"), "The speaker states that the meeting is in Room Two.", correct_position=0)),
            ],
        ),
        "speaking": _skill_lesson(
            "Ask for something politely",
            "Use a short request and respond clearly in an everyday exchange.",
            "Learn one reusable request frame, then recognize, complete, and build it.",
            [
                {"type": "concept", "data": _concept("Use Could I have …, please? to ask for an item politely. A helpful reply can begin with Certainly or Sorry, followed by clear information.", ["Name the item after have.", "Add please to keep the request polite."], ["Could I have some water, please?", "Certainly. Here you are."])},
                {"type": "multiple_choice", "data": _choice("Which phrase is the polite way to ask for water?", "Could I have some water, please?", ("Water now.", "You have water."), "Could I have some water, please? is a complete polite request.", correct_position=1)},
                {"type": "fill_blank", "data": _fill("Could I ___ a coffee, please?", "have", "The request frame is Could I have a coffee, please?")},
                {"type": "sentence_order", "data": _order("Build the polite request.", ("Could I", "have", "a ticket,", "please?"), "The complete request is: Could I have a ticket, please?")},
            ],
        ),
        "pronunciation": _skill_lesson(
            "Clear /p/ and /b/",
            "Use air and voicing to keep the English /p/–/b/ contrast clear.",
            "Feel the contrast first, then practise it in words and a short perception check.",
            [
                {"type": "pronunciation_drill", "data": {"sound_label": "Voiceless P", "ipa": "/p/", "instructions": "Close both lips, then release them with a small puff of air. Keep your throat quiet.", "tips": ["Hold a hand in front of your mouth to feel the air.", "Do not add a vowel before the sound."], "practice_items": ["pen", "paper", "Please pass the pepper."], "native_hint": None}},
                {"type": "pronunciation_drill", "data": {"sound_label": "Voiced B", "ipa": "/b/", "instructions": "Close both lips and release them while your vocal folds vibrate. The air puff is weaker than /p/.", "tips": ["Touch your throat to feel vibration.", "Compare bat with pat slowly."], "practice_items": ["book", "baby", "Ben bought a blue bag."], "native_hint": None}},
                {"type": "pronunciation_drill", "data": {"sound_label": "P and B in phrases", "ipa": "/p/ and /b/", "instructions": "Keep /p/ voiceless and /b/ voiced without adding an extra vowel.", "tips": ["Pause between the contrasting words first.", "Keep both lips fully closed before each sound."], "practice_items": ["paper bag", "Please bring both pens.", "Put the blue book beside the paper."], "native_hint": None}},
                {"type": "multiple_choice", "data": _choice("Which word begins with the stronger puff of air?", "pen", ("ben", "book"), "Pen begins with voiceless /p/, which normally has a stronger puff of air.", correct_position=0)},
            ],
        ),
        "discourse": _skill_lesson(
            "Connect two short ideas",
            "Use and, but, and because to show addition, contrast, and reason.",
            "Match one connector to its meaning, then build two complete links.",
            [
                {"type": "concept", "data": _concept("Use and to add similar information, but to contrast two ideas, and because to introduce a reason.", ["Choose the relationship before the connector.", "Put because directly before the reason."], ["I work and I study.", "I stayed home because I was tired."])},
                {"type": "multiple_choice", "data": _choice("Which connector introduces a reason?", "because", ("and", "but"), "Because introduces a reason, so because is correct.", correct_position=2)},
                {"type": "sentence_order", "data": _order("Build a sentence with a reason.", ("I stayed home", "because", "I was tired."), "The complete sentence is: I stayed home because I was tired.")},
                {"type": "sentence_order", "data": _order("Build a sentence with contrast.", ("The room is small,", "but", "it is comfortable."), "The complete sentence is: The room is small, but it is comfortable.")},
            ],
        ),
    },
    "A2": {},
    "B1": {},
    "B2": {},
}
# The remaining levels use distinct reviewed language below. Defining them as
# updates keeps the factory-heavy source readable without hiding answer keys in
# runtime prompts.
_CURATED_LESSONS["A2"] = {
    "vocabulary": _vocab(
        title="Appointments and service words",
        description="Use two practical items when changing a booking or paying for something.",
        cards=(_card("reschedule", "verb", "/ˌriːˈskedʒuːl/", "arrange an event for a different time", "I need to reschedule my appointment.", ["reschedule a meeting", "reschedule for Monday"]), _card("receipt", "noun", "/rɪˈsiːt/", "a written or digital record that you paid", "Keep the receipt in case you return the shirt.", ["ask for a receipt", "digital receipt"])),
        check=_choice("Which word means ‘arrange it for a different time’?", "reschedule", ("receipt", "reserve"), "Reschedule means to arrange something for a different time.", correct_position=2),
        recall=_fill("Could I have a ___ for this purchase, please?", "receipt", "A receipt is the record of a purchase."),
    ),
    "grammar": _skill_lesson(
        "Finished events and future intentions",
        "Contrast the past simple with be going to.",
        "Use the time reference to choose the form, then produce both patterns.",
        [
            {"type": "concept", "data": _concept("Use the past simple for a finished event at a finished time. Use am, is, or are going to plus a base verb for an intention.", ["Yesterday and last year normally point to the past simple.", "Tomorrow can introduce an intention with going to."], ["I visited Aleppo last year.", "I am going to apply tomorrow."])},
            {"type": "multiple_choice", "data": _choice("Choose the sentence about a finished trip last year.", "We visited Jordan last year.", ("We visit Jordan last year.", "We are going to visited Jordan last year."), "We visited Jordan last year uses the past simple for a finished time.", correct_position=1)},
            {"type": "fill_blank", "data": _fill("I am going to ___ for the course tomorrow.", "apply", "After going to, use the base verb apply.")},
            {"type": "sentence_order", "data": _order("Build a negative past sentence.", ("We", "did not", "miss", "the bus."), "The complete sentence is: We did not miss the bus.")},
        ],
    ),
    "reading": _skill_lesson(
        "Read short emails and instructions",
        "Find purpose, required action, and sequence in connected everyday texts.",
        "Identify what the reader must know or do, then verify one detail in each text.",
        [
            {"type": "concept", "data": _concept("In an email or instruction, find the purpose first. Then underline the action, deadline, or numbered step that answers the question.", ["Purpose tells you why the text exists.", "Imperative verbs often show the required action."], ["Please confirm by Friday shows an action and deadline.", "First, switch off the machine shows step one."])},
            _nested("reading_comprehension", title="Appointment email", text="Hello Omar, your dentist appointment has moved to Thursday at 3:30 p.m. Please reply by Tuesday to confirm the new time.", question=_choice("What must Omar do by Tuesday?", "Confirm the new time", ("Visit the dentist", "Choose a new doctor"), "The email says to reply by Tuesday to confirm the new time.", correct_position=2)),
            _nested("reading_comprehension", title="Coffee machine", text="To clean the coffee machine, first switch it off. Next, remove and wash the water container. Finally, dry it before putting it back.", question=_choice("What should you do first?", "Switch the machine off", ("Dry the container", "Put the container back"), "The instruction says first switch it off, so Switch the machine off is correct.", correct_position=0)),
            _nested("reading_comprehension", title="Course registration", text="Registration closes on Wednesday. Complete the online form, then bring your identification to the office before five o’clock.", question=_choice("What should learners complete first?", "The online form", ("A final exam", "A travel ticket"), "The instruction says to complete the online form before visiting the office.", correct_position=1)),
        ],
    ),
    "listening": _skill_lesson(
        "Follow routine exchanges",
        "Listen for changes, prices, and requested actions in familiar conversations.",
        "Use contrast words and repeated details to catch the information that matters.",
        [
            {"type": "concept", "data": _concept("Speakers often correct or change a detail. Words such as actually, but, and instead warn you that the final information may differ from the first idea.", ["Wait for the final version of a corrected detail.", "Write only the key number, place, or action."], ["Not Tuesday—Thursday gives the final day.", "It is fifteen, not fifty, corrects a price."])},
            _nested("listening_comprehension", title="Platform change", text="Attention, please. The train to Homs now leaves from Platform Five at ten twenty.", question=_choice("Which platform should passengers use?", "Platform Five", ("Platform Two", "Platform Ten"), "The announcement says it now leaves from Platform Five.", correct_position=1)),
            _nested("listening_comprehension", title="At the shop", text="Customer: How much is this notebook today? Assistant: Today it costs nine dollars.", question=_choice("What is today’s price?", "Nine dollars", ("Twelve dollars", "Twenty-one dollars"), "The assistant says today it costs nine dollars.", correct_position=0)),
            _nested("listening_comprehension", title="Changed appointment", text="Your appointment was at two, but the doctor is delayed. Please come at three thirty instead.", question=_choice("What is the new appointment time?", "Three thirty", ("Two o’clock", "Four thirty"), "Instead signals the change to three thirty.", correct_position=2)),
        ],
    ),
    "speaking": _skill_lesson(
        "Clarify a misunderstanding",
        "Ask someone to repeat or confirm one detail in a routine conversation.",
        "Learn a repair phrase, then choose, complete, and build a clear follow-up.",
        [
            {"type": "concept", "data": _concept("When you miss information, say Sorry, could you say that again? For one uncertain detail, ask Do you mean …? and repeat what you heard.", ["Say what you need repeated.", "Use a rising voice on Do you mean …?"], ["Could you say that again, please?", "Do you mean Thursday at three?"])},
            {"type": "multiple_choice", "data": _choice("Which response politely asks someone to repeat a detail?", "Could you repeat that, please?", ("That detail is good.", "I repeated it yesterday."), "Could you repeat that, please? directly and politely asks for clarification.", correct_position=2)},
            {"type": "fill_blank", "data": _fill("Do you ___ Thursday at three?", "mean", "The clarification frame is Do you mean Thursday at three?")},
            {"type": "sentence_order", "data": _order("Build a clarification request.", ("Could you", "say that", "again,", "please?"), "The complete request is: Could you say that again, please?")},
        ],
    ),
    "pronunciation": _skill_lesson(
        "Clear TH sounds",
        "Keep /θ/ and /ð/ distinct from /t/, /d/, /s/, and /z/.",
        "Place the tongue correctly, compare voicing, then check the contrast.",
        [
            {"type": "pronunciation_drill", "data": {"sound_label": "Voiceless TH", "ipa": "/θ/", "instructions": "Place the tongue tip lightly between the teeth and let air pass continuously. Keep your throat quiet.", "tips": ["Do not stop the air as you do for /t/.", "Practise slowly before adding the next sound."], "practice_items": ["think", "three", "I think Thursday is free."], "native_hint": None}},
            {"type": "pronunciation_drill", "data": {"sound_label": "Voiced TH", "ipa": "/ð/", "instructions": "Keep the tongue lightly between the teeth and let air pass while your throat vibrates.", "tips": ["Touch your throat to check the vibration.", "Avoid replacing it with /d/ or /z/."], "practice_items": ["this", "those", "They left their bags there."], "native_hint": None}},
            {"type": "pronunciation_drill", "data": {"sound_label": "Voiceless TH in connected phrases", "ipa": "/θ/", "instructions": "Keep the tongue near the teeth and let the voiceless air continue as you move smoothly into the next word.", "tips": ["Slow the phrase down before joining the words.", "Keep your throat quiet on each /θ/."], "practice_items": ["three things", "I thought they were there.", "Their third class is on Thursday."], "native_hint": None}},
            {"type": "multiple_choice", "data": _choice("Which word begins with voiced /ð/?", "those", ("think", "three"), "Those begins with voiced /ð/; think and three begin with /θ/.", correct_position=1)},
        ],
    ),
    "discourse": _skill_lesson(
        "Sequence a short account",
        "Use first, then, after that, and finally to make event order easy to follow.",
        "Choose the closing marker, then arrange two short sequences.",
        [
            {"type": "concept", "data": _concept("Use first for the opening step, then or after that for middle steps, and finally for the last step.", ["Keep the events in time order.", "Do not use finally before another step remains."], ["First, we checked in. Then, we went through security.", "Finally, we boarded the plane."])},
            {"type": "multiple_choice", "data": _choice("Which marker introduces the last step?", "finally", ("first", "after that"), "Finally introduces the last step, so finally is correct.", correct_position=0)},
            {"type": "sentence_order", "data": _order("Order the start of a journey.", ("First,", "we bought the tickets.", "Then,", "we found the platform."), "The sequence is: First, we bought the tickets. Then, we found the platform.")},
            {"type": "sentence_order", "data": _order("Order the end of a recipe.", ("After that,", "add the rice.", "Finally,", "turn off the heat."), "The sequence is: After that, add the rice. Finally, turn off the heat.")},
        ],
    ),
}
_CURATED_LESSONS["B1"] = {
    "vocabulary": _vocab(
        title="Project problem-solving vocabulary",
        description="Use two practical work and technology items in natural collocations.",
        cards=(_card("deadline", "noun", "/ˈdedlaɪn/", "the latest time by which something must be completed", "We moved the deadline to Friday.", ["meet a deadline", "miss a deadline"]), _card("troubleshoot", "verb", "/ˈtrʌbəlʃuːt/", "identify the cause of a problem and try to solve it", "The technician helped us troubleshoot the connection.", ["troubleshoot an issue", "troubleshooting guide"])),
        check=_choice("Which verb means ‘investigate and solve a technical problem’?", "troubleshoot", ("postpone", "download"), "Troubleshoot means to investigate the cause of a problem and try to solve it.", correct_position=1),
        recall=_fill("We must finish the report by Friday’s ___.", "deadline", "A deadline is the latest time by which the report must be finished."),
    ),
    "grammar": _skill_lesson(
        "Present perfect and finished time",
        "Contrast a current result with a finished past event.",
        "Use the time expression and intended focus to select the tense, then build both forms.",
        [
            {"type": "concept", "data": _concept("Use the present perfect for experience or a result connected to now, without a finished past time. Use the past simple with a finished time such as yesterday or last week.", ["Present perfect: have or has plus past participle.", "Finished past time: use the past simple."], ["I have fixed the issue, so it works now.", "I fixed the issue yesterday."])},
            {"type": "multiple_choice", "data": _choice("Choose the sentence that fits the finished time ‘yesterday’.", "I sent the update yesterday.", ("I have sent the update yesterday.", "I send the update yesterday."), "I sent the update yesterday is correct because yesterday is a finished past time.", correct_position=2)},
            {"type": "fill_blank", "data": _fill("The team has ___ the connection, so it works now.", "fixed", "The present perfect form is has fixed, and the result matters now.")},
            {"type": "sentence_order", "data": _order("Build a present-perfect result.", ("We", "have completed", "the report", "already."), "The complete sentence is: We have completed the report already.")},
        ],
    ),
    "reading": _skill_lesson(
        "Separate claims from evidence",
        "Identify a main point and the detail that supports it.",
        "Learn to label claim and evidence, then answer one evidence-based question per text.",
        [
            {"type": "concept", "data": _concept("A main claim tells you what the writer wants you to believe. Evidence is the specific fact, example, or result used to support that claim.", ["Ask: what is the writer’s main point?", "Then ask: which exact detail supports it?"], ["Claim: remote meetings save time. Evidence: the team avoided a two-hour trip.", "Background information is not automatically evidence."])},
            _nested(
                "reading_comprehension",
                title="A quieter office",
                text="Our team tested a quiet work hour from nine to ten each morning. During the trial, staff completed urgent tasks with fewer interruptions. Because the result was positive, the manager plans to continue the quiet hour next month.",
                question=_choice("Which result supports continuing the quiet hour?", "Staff completed urgent tasks with fewer interruptions", ("The office opened at nine", "The manager bought new desks"), "The text reports that staff completed urgent tasks with fewer interruptions; this is the supporting result.", correct_position=0),
            ),
            _nested(
                "reading_comprehension",
                title="Repair before replacement",
                text="The school considered replacing twenty slow laptops. A technician cleaned the cooling fans and updated the software on five test machines. Those laptops then started much faster, so the school decided to repair the others first.",
                question=_choice("Why did the school decide to repair the other laptops?", "The five test laptops became faster", ("Twenty new laptops arrived", "Students stopped using software"), "The five test laptops became faster after repair, which supports repairing the others first.", correct_position=2),
            ),
            _nested(
                "reading_comprehension",
                title="A revised workshop",
                text="Feedback showed that participants understood the demonstrations but needed more time to practise. The organizer therefore shortened the opening talk and added a longer guided task.",
                question=_choice("Which evidence caused the workshop to change?", "Participants needed more practice time", ("The venue became unavailable", "The demonstrations were removed"), "The feedback specifically says participants needed more time to practise.", correct_position=1),
            ),
        ],
    ),
    "listening": _skill_lesson(
        "Track signposts and key details",
        "Follow the main point and one important detail in clear extended speech.",
        "Use signposts to predict what comes next, then answer questions tied to one explicit detail.",
        [
            {"type": "concept", "data": _concept("Signposts show the speaker’s direction. For example introduces support, however signals contrast, and in conclusion introduces the final main point.", ["Write the signpost, not every sentence.", "Listen closely to the idea immediately after it."], ["However often introduces a limitation.", "For example normally introduces evidence or illustration."])},
            _nested(
                "listening_comprehension",
                title="A project update",
                text="The design is ready and the client has approved it. However, the testing stage will start two days late because one device has not arrived. In conclusion, the final deadline is still realistic.",
                question=_choice("What problem does the speaker introduce after ‘however’?", "Testing will start two days late", ("The client rejected the design", "The final deadline was cancelled"), "After however, the speaker says testing will start two days late.", correct_position=1),
            ),
            _nested(
                "listening_comprehension",
                title="Choosing a training format",
                text="Online training is flexible. For example, staff can complete each section when their schedule is quiet. The company will therefore offer the course online next month.",
                question=_choice("What example of flexibility does the speaker give?", "Staff can study when their schedule is quiet", ("The course requires a fixed classroom", "The company cancelled the course"), "The speaker’s example is that staff can study when their schedule is quiet.", correct_position=0),
            ),
            _nested(
                "listening_comprehension",
                title="Revising a delivery plan",
                text="First, the supplier confirmed that the materials are ready. On the other hand, the larger vehicle is unavailable until Friday. As a result, the team will make two smaller deliveries.",
                question=_choice("What decision follows from the vehicle problem?", "Make two smaller deliveries", ("Cancel the materials", "Wait for a new supplier"), "As a result introduces the decision to make two smaller deliveries.", correct_position=2),
            ),
        ],
    ),
    "speaking": _skill_lesson(
        "Give a reason and invite a response",
        "Sustain a familiar conversation with a reason and a follow-up question.",
        "Learn a complete conversational move, then choose, complete, and build useful language for it.",
        [
            {"type": "concept", "data": _concept("A useful extended turn has a clear view, a reason, and an invitation for the other person. Use In my view … because …, then ask What do you think?", ["Make the reason specific enough to discuss.", "Use a follow-up question to keep the conversation moving."], ["In my view, online booking is easier because it saves time. What do you think?", "I prefer the first option because it is more reliable. How about you?"])},
            {"type": "multiple_choice", "data": _choice("Which response gives a view, a reason, and a follow-up question?", "I prefer this option because it is more reliable. How about you?", ("This is one option.", "Do you prefer it? Yes."), "I prefer this option because it is more reliable. How about you? contains all three conversation moves.", correct_position=2)},
            {"type": "fill_blank", "data": _fill("I prefer this option ___ it is more reliable.", "because", "Because introduces the speaker’s reason: because it is more reliable.")},
            {"type": "sentence_order", "data": _order("Build a response that invites the other speaker.", ("In my view,", "this option is more practical", "because it is easier to use.", "What do you think?"), "The response states a view, gives a reason, and ends with What do you think?")},
        ],
    ),
    "pronunciation": _skill_lesson(
        "Keep /p/ and /b/ distinct",
        "Improve intelligibility by keeping a useful English consonant contrast clear.",
        "Use air and voicing as physical checks, then apply the contrast in meaningful phrases.",
        [
            {"type": "pronunciation_drill", "data": {"sound_label": "Clear initial P", "ipa": "/p/", "instructions": "Close both lips, build pressure, and release a clear voiceless /p/ at the start of the word.", "tips": ["Test the release with a small piece of paper.", "Do not voice the sound before the lips open."], "practice_items": ["project plan", "payment problem", "Please print the proposal."], "native_hint": None}},
            {"type": "pronunciation_drill", "data": {"sound_label": "Voiced B", "ipa": "/b/", "instructions": "Close both lips and start vocal-fold vibration as you release /b/. Use less air than for /p/.", "tips": ["Touch the throat to confirm vibration.", "Alternate pack–back slowly, then increase speed."], "practice_items": ["budget brief", "better battery", "Ben brought the blue booklet."], "native_hint": None}},
            {"type": "pronunciation_drill", "data": {"sound_label": "P and B in longer phrases", "ipa": "/p/ and /b/", "instructions": "Keep /p/ voiceless and /b/ voiced throughout each longer phrase.", "tips": ["Practise the contrasting words slowly first.", "Keep the lips active even in the middle of the phrase."], "practice_items": ["Please bring the project brief.", "The backup plan is practical.", "We prepared a better proposal."], "native_hint": None}},
            {"type": "multiple_choice", "data": _choice("Which physical cue best distinguishes initial /p/ from /b/?", "A stronger air puff with no voicing", ("Continuous tongue vibration", "A longer nasal sound"), "Initial /p/ normally has a stronger air puff with no voicing.", correct_position=1)},
        ],
    ),
    "discourse": _skill_lesson(
        "Link contrast and reason",
        "Use although and because to make relationships between ideas explicit.",
        "Choose the intended relationship, then construct two coherent extended sentences.",
        [
            {"type": "concept", "data": _concept("Although introduces a contrast or unexpected result. Because introduces the reason for a claim or situation.", ["Although and because express different logical relationships.", "Use a complete clause after each connector."], ["Although it costs more, it is more reliable.", "We delayed the launch because testing was incomplete."])},
            {"type": "multiple_choice", "data": _choice("Which connector introduces the reason for a delay?", "because", ("although", "overall"), "Because introduces a reason, so because is the correct connector.", correct_position=0)},
            {"type": "sentence_order", "data": _order("Build a sentence with contrast.", ("Although", "the call was short,", "we solved", "the main problem."), "The complete sentence is: Although the call was short, we solved the main problem.")},
            {"type": "sentence_order", "data": _order("Build a sentence with a reason.", ("We changed the schedule", "because", "the client requested", "more testing time."), "The complete sentence is: We changed the schedule because the client requested more testing time.")},
        ],
    ),
}
_CURATED_LESSONS["B2"] = {
    "vocabulary": _vocab(
        title="Precise professional stance",
        description="Use two formal expressions to raise an issue and describe evidence cautiously.",
        cards=(
            _card("raise a concern", "verb phrase", "/reɪz ə kənˈsɜːrn/", "formally draw attention to a possible problem", "Several reviewers raised a concern about data privacy.", ["raise a serious concern", "raise concerns about"]),
            _card("the evidence suggests", "stance phrase", "/ði ˈevɪdəns səˈdʒests/", "introduce a conclusion cautiously rather than as absolute fact", "The evidence suggests that the new process reduces delays.", ["available evidence suggests", "evidence strongly suggests"]),
        ),
        check=_choice("Which phrase introduces a cautious evidence-based conclusion?", "the evidence suggests", ("everyone knows", "raise a concern"), "The evidence suggests presents a conclusion cautiously and links it to evidence.", correct_position=1),
        recall=_fill("The reviewers decided to ___ about the proposal’s privacy risks.", "raise a concern", "Raise a concern means to draw formal attention to a possible problem."),
    ),
    "grammar": _skill_lesson(
        "Unreal past conditionals",
        "Describe a past condition and an imagined past result precisely.",
        "Map condition to result, then recognize and construct the third conditional.",
        [
            {"type": "concept", "data": _concept("Use if plus past perfect for an unreal past condition, and would have plus past participle for its imagined result.", ["Condition: if + had + past participle.", "Result: would have + past participle."], ["If we had tested it earlier, we would have found the fault.", "If she had called, I would have answered."])},
            {"type": "multiple_choice", "data": _choice("Choose the correct unreal past sentence.", "If we had checked the data, we would have noticed the error.", ("If we checked the data, we would have noticed yesterday.", "If we had check the data, we would noticed the error."), "If we had checked the data, we would have noticed the error has both required third-conditional forms.", correct_position=0)},
            {"type": "fill_blank", "data": _fill("If they had tested the update, they would have ___ the fault.", "found", "Would have is followed by the past participle found.")},
            {"type": "sentence_order", "data": _order("Build an unreal past result.", ("If she had called,", "I", "would have answered", "immediately."), "The complete sentence is: If she had called, I would have answered immediately.")},
        ],
    ),
    "reading": _skill_lesson(
        "Evaluate claims and evidence",
        "Distinguish a writer’s conclusion from the limitation that qualifies it.",
        "Identify claim, support, and limitation before judging how strong an argument is.",
        [
            {"type": "concept", "data": _concept("A strong critical reading separates the claim, the supporting evidence, and any limitation. A limitation narrows how confidently the conclusion can be applied.", ["Locate cautious words such as may, suggests, and in this sample.", "Check whether the evidence directly supports the scope of the claim."], ["A small trial may support a local result without proving a universal claim.", "However can introduce evidence that limits the conclusion."])},
            _nested(
                "reading_comprehension",
                title="Four-day trial",
                text="A six-week trial found that employees on a four-day schedule reported higher concentration and completed the same number of tasks. However, the trial involved only one department during a quiet season. The results support a longer test, not an immediate company-wide change.",
                question=_choice("Which limitation reduces the scope of the trial’s conclusion?", "It covered one department during a quiet season", ("Employees completed the same number of tasks", "The company has already changed every schedule"), "The stated limitation is that the trial covered one department during a quiet season.", correct_position=1),
            ),
            _nested(
                "reading_comprehension",
                title="AI support tool",
                text="A support team used an AI tool to draft routine replies. Average response time fell by 18 percent. Human review was still part of the process: supervisors checked every message before it was sent. The author therefore does not claim that the tool can work safely on its own.",
                question=_choice("What qualification does the author make?", "Human review was still part of the process", ("Response time increased by 18 percent", "The tool independently sent every reply"), "Human review was still part of the process because supervisors checked every message before it was sent.", correct_position=2),
            ),
            _nested(
                "reading_comprehension",
                title="Transport survey",
                text="A neighborhood survey found strong support for a later evening bus. Yet most responses came from commuters who already use the route. The findings justify a broader consultation, but they do not represent every resident.",
                question=_choice("Why should the survey conclusion remain limited?", "Most responses came from existing commuters", ("The route has already closed", "Every resident answered the survey"), "Most responses came from existing commuters, so the sample cannot represent every resident.", correct_position=0),
            ),
        ],
    ),
    "listening": _skill_lesson(
        "Follow qualified viewpoints",
        "Notice hedging and changes of direction in detailed discussion.",
        "Listen for the speaker’s level of certainty and the contrast that follows a concession.",
        [
            {"type": "concept", "data": _concept("Hedges such as probably, appears to, and to some extent reduce certainty. Phrases such as having said that signal that the speaker is about to qualify the previous point.", ["Record whether a claim is certain, probable, or tentative.", "Expect a qualification after having said that."], ["It appears to be effective is cautious.", "Having said that often introduces a limitation."])},
            _nested(
                "listening_comprehension",
                title="Remote onboarding",
                text="Remote onboarding appears to reduce travel costs and gives new staff more flexibility. Having said that, the first week probably works better when each employee has a named colleague to contact.",
                question=_choice("What does the speaker recommend for the first week?", "Give each employee a named contact", ("Require every employee to travel", "Remove all onboarding support"), "After the qualification, the speaker recommends giving each employee a named contact.", correct_position=0),
            ),
            _nested(
                "listening_comprehension",
                title="A cautious forecast",
                text="Sales are likely to improve next quarter, mainly because two delayed products will finally launch. Nevertheless, the estimate depends on shipping costs remaining stable.",
                question=_choice("What condition could affect the forecast?", "Whether shipping costs remain stable", ("Whether both products stay delayed forever", "Whether the company stops tracking sales"), "The speaker says the estimate depends on shipping costs remaining stable.", correct_position=2),
            ),
            _nested(
                "listening_comprehension",
                title="Qualified recommendation",
                text="The pilot seems to have reduced routine errors. Even so, the sample was relatively small, and the team should probably repeat the test before adopting the process everywhere.",
                question=_choice("What does the speaker recommend before wider adoption?", "Repeat the test", ("Ignore the pilot", "Adopt it everywhere immediately"), "The speaker recommends repeating the test because the sample was small.", correct_position=1),
            ),
        ],
    ),
    "speaking": _skill_lesson(
        "Acknowledge and counter",
        "Respond to another viewpoint before presenting a reasoned alternative.",
        "Learn a respectful counterargument frame, then recognize, complete, and build it.",
        [
            {
                "type": "concept",
                "data": _concept("A constructive counterargument first acknowledges the other point, then signals a different view and supports it. Use I take your point; however, … followed by a specific reason.", ["Acknowledge accurately before disagreeing.", "Support the alternative with evidence or a practical consequence."], ["I take your point; however, the cheaper option may cost more to maintain.", "That is a fair concern. Nevertheless, a short trial would limit the risk."]),
            },
            {"type": "multiple_choice", "data": _choice("Which response acknowledges the concern before offering a counterargument?", "I take your point; however, a pilot would let us test the risk safely.", ("You are completely wrong.", "A pilot is a small test."), "I take your point; however, a pilot would let us test the risk safely acknowledges and then counters with a reason.", correct_position=1)},
            {"type": "fill_blank", "data": _fill("I take your point; ___, the evidence is still limited.", "however", "However signals the counterargument after the acknowledgement.")},
            {"type": "sentence_order", "data": _order("Build a respectful counterargument.", ("That is a fair concern.", "Nevertheless,", "a short trial", "would limit the risk."), "The response acknowledges the concern before presenting the alternative.")},
        ],
    ),
    "pronunciation": _skill_lesson(
        "Clear /ʒ/ and /dʒ/",
        "Keep the fricative /ʒ/ distinct from the affricate /dʒ/ in professional vocabulary.",
        "Sustain the voiced friction first, then add the brief stop release required for /dʒ/.",
        [
            {"type": "pronunciation_drill", "data": {"sound_label": "Voiced ZH", "ipa": "/ʒ/", "instructions": "Let voiced air continue through a narrow groove behind the teeth without stopping it first.", "tips": ["Touch your throat to confirm voicing.", "Keep the friction continuous rather than adding a stop."], "practice_items": ["measure", "revision", "The decision needs revision."], "native_hint": None}},
            {"type": "pronunciation_drill", "data": {"sound_label": "Voiced J", "ipa": "/dʒ/", "instructions": "Briefly stop the air behind the teeth, then release it into voiced friction.", "tips": ["Build a short closure before the release.", "Keep your throat vibrating through the sound."], "practice_items": ["project", "manager", "The project manager joined us."], "native_hint": None}},
            {
                "type": "pronunciation_drill",
                "data": {"sound_label": "ZH and J in longer phrases", "ipa": "/ʒ/ and /dʒ/", "instructions": "Keep /ʒ/ continuous, but begin /dʒ/ with a brief stop before the voiced release.", "tips": ["Stretch /ʒ/ to feel its continuous friction.", "Use a crisp but voiced release for /dʒ/."], "practice_items": ["The project manager revised the decision.", "The journalist measured the damaged equipment.", "A major revision changed the procedure."], "native_hint": None},
            },
            {"type": "multiple_choice", "data": _choice("Which sound begins with a brief stop before its voiced release?", "/dʒ/", ("/ʒ/", "/z/"), "/dʒ/ begins with a stop closure, while /ʒ/ is continuous friction.", correct_position=2)},
        ],
    ),
    "discourse": _skill_lesson(
        "Frame and qualify an argument",
        "Use an opening frame and a qualification to structure a balanced position.",
        "Choose the function of a qualifier, then arrange a clear opening and conclusion.",
        [
            {"type": "concept", "data": _concept("Frame an argument by announcing its structure. Use a qualifier such as that said to introduce an important limitation without abandoning the main position.", ["Tell the listener how many considerations will follow.", "Use the qualifier where the direction of the argument changes."], ["There are two main considerations.", "That said, the evidence is still limited."])},
            {"type": "multiple_choice", "data": _choice("Which phrase introduces a qualification to the previous point?", "That said", ("There are two main considerations", "Taken together"), "That said introduces a qualification or limitation to the previous point.", correct_position=1)},
            {"type": "sentence_order", "data": _order("Build an argument opening.", ("There are", "two main considerations:", "cost", "and reliability."), "The opening is: There are two main considerations: cost and reliability.")},
            {"type": "sentence_order", "data": _order("Build a qualified conclusion.", ("Taken together,", "these results support a trial.", "That said,", "longer testing is still needed."), "The conclusion supports a trial and then qualifies it with the need for longer testing.")},
        ],
    ),
}


def validate_catalog_shape() -> None:
    expected_domains = {"vocabulary", "grammar", "reading", "listening", "speaking", "pronunciation", "discourse"}
    for level, domains in _CURATED_LESSONS.items():
        if set(domains) != expected_domains:
            raise ValueError(f"curated {level} domains are incomplete")


validate_catalog_shape()
