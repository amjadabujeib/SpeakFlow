import 'package:flutter_test/flutter_test.dart';
import 'package:speakflow/features/chat/roleplay_feedback_data.dart';
import 'package:speakflow/features/chat/roleplay_models.dart';

void main() {
  test('roleplay scenario parses the server contract', () {
    final scenario = RoleplayScenario.fromJson({
      'id': 'hotel_check_in',
      'version': 2,
      'category': 'Travel',
      'icon': '🏨',
      'title': 'Hotel Check-in',
      'description': 'Check into a hotel.',
      'ai_role': 'receptionist',
      'learner_role': 'guest',
      'opening': 'Welcome. How may I help?',
      'objectives': [
        {
          'id': 'reservation',
          'label': 'Explain your reservation',
          'weight': 2,
          'required': true,
        },
      ],
      'target_language': ['I have a reservation'],
      'evaluation_rubric': [
        {
          'id': 'booking_clarity',
          'label': 'Booking clarity',
          'description':
              'Communicates booking details clearly and consistently.',
          'weight': 2,
        },
      ],
      'designed_cefr_level': 'A2',
      'custom': false,
    });

    expect(scenario.id, 'hotel_check_in');
    expect(scenario.version, 2);
    expect(scenario.objectives.single.weight, 2);
    expect(scenario.targetLanguage.single, 'I have a reservation');
    expect(scenario.evaluationRubric.single.id, 'booking_clarity');
    expect(scenario.designedCefrLevel, 'A2');
  });

  test('final roleplay result uses authoritative evaluation fields', () {
    final feedback = RoleplayFeedbackData.fromFinalizeJson({
      'session': {
        'scenario': 'Hotel Check-in',
        'message_count': 5,
        'duration_seconds': 92,
        'evaluation': {
          'scenario': {'title': 'Hotel Check-in', 'icon': '🏨'},
          'eligible': true,
          'scenario_completed': true,
          'eligibility_note': 'Enough spoken evidence.',
          'scores': {'task_achievement': 100, 'delivery_fluency': 76},
          'evidence': {
            'spoken_turns': 5,
            'scenario_evidence': [
              {
                'rubric_id': 'booking_clarity',
                'label': 'Booking clarity',
                'score': 87,
                'evidence': [],
              },
            ],
          },
          'recognition_checks': [
            {
              'word': 'reservation',
              'confidence': 64,
              'reason': 'recognizer_uncertain',
            },
          ],
        },
      },
      'corrections': [
        {
          'turn_id': 'turn-12345678',
          'original': 'I have reserve.',
          'corrected': 'I have a reservation.',
          'feedback': 'Use a noun after have.',
        },
      ],
    });

    expect(feedback.scores.containsKey('overall'), isFalse);
    expect(feedback.objectiveCompleted, isTrue);
    expect(feedback.icon, '🏨');
    expect(feedback.recognitionChecks.single.word, 'reservation');
    expect(feedback.scenarioEvidence.single['score'], 87);
    expect(feedback.corrections.single.corrected, 'I have a reservation.');
    expect(feedback.practiceWordsAdded, 0);
    expect(feedback.withPracticeWordsAdded(2).practiceWordsAdded, 2);
  });

  test('short session keeps independent provisional category scores', () {
    final feedback = RoleplayFeedbackData.fromFinalizeJson({
      'session': {
        'scenario': 'Café Small Talk',
        'message_count': 1,
        'duration_seconds': 8,
        'evaluation': {
          'eligible': false,
          'scenario_completed': false,
          'eligibility_note': 'Use at least four turns.',
          'scores': {'task_achievement': 25, 'interaction': 61},
          'recognition_checks': [],
        },
      },
      'corrections': [],
    });

    expect(feedback.eligible, isFalse);
    expect(feedback.scores['task_achievement'], 25);
    expect(feedback.scores.containsKey('overall'), isFalse);
    expect(feedback.evidenceNote, contains('four turns'));
  });

  test('saved roleplay transcript preserves ordered message pairs', () {
    final transcript = RoleplayTranscript.fromJson({
      'read_only': true,
      'session': {
        'client_session_id': 'roleplay-history-1234',
        'scenario': 'Airport Check-in',
        'duration_seconds': 44,
      },
      'scenario': {
        'id': 'airport_check_in',
        'version': 1,
        'category': 'Travel',
        'icon': '✈️',
        'title': 'Airport Check-in',
        'description': 'Check in for a flight.',
        'ai_role': 'check-in agent',
        'learner_role': 'passenger',
        'opening': 'Where are you flying today?',
        'objectives': const [],
      },
      'turns': [
        {
          'turn_id': 'turn-history-0001',
          'sequence': 1,
          'input_mode': 'text',
          'user_text': 'I am flying to Paris.',
          'assistant_text': 'May I see your passport?',
          'created_at': '2026-07-26T07:00:00Z',
        },
        {
          'turn_id': 'turn-history-0002',
          'sequence': 2,
          'input_mode': 'audio',
          'user_text': 'Here it is.',
          'assistant_text': 'Thank you.',
          'grammar_corrected_text': 'Here it is.',
          'grammar_feedback': 'Correct',
          'word_confidence': [
            {'word': 'Here', 'score': .91},
            {'word': 'it', 'score': .82},
            {'word': 'is', 'score': .74},
          ],
          'created_at': '2026-07-26T07:00:05Z',
        },
      ],
    });

    expect(transcript.readOnly, isTrue);
    expect(transcript.scenario.opening, 'Where are you flying today?');
    expect(transcript.turns.map((item) => item.sequence), [1, 2]);
    expect(transcript.turns.last.inputMode, 'audio');
    expect(transcript.turns.last.correctedText, 'Here it is.');
    expect(transcript.turns.last.grammarFeedback, 'Correct');
    expect(transcript.turns.last.wordConfidence.length, 3);
    expect(transcript.turns.last.wordConfidence.last['score'], .74);
  });
}
