import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:speakflow/features/chat/roleplay_feedback_data.dart';
import 'package:speakflow/features/chat/roleplay_session_summary_screen.dart';

void main() {
  testWidgets('session summary shows only useful calculated performance', (
    tester,
  ) async {
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
          'scores': {
            'task_achievement': 100,
            'interaction': 82,
            'grammar_control': 77,
            'vocabulary_function': 80,
            'delivery_fluency': 76,
            'pitch_variation': 65,
            'intelligibility_proxy': 91,
          },
          'evidence': {
            'scenario_evidence': [
              {'label': 'Booking clarity', 'score': 87, 'evidence': []},
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
        },
      ],
    }).withPracticeWordsAdded(1);

    await tester.pumpWidget(
      MaterialApp(home: SessionFeedbackScreen(feedback: feedback)),
    );
    await tester.pump();

    expect(find.text('Performance'), findsOneWidget);
    expect(find.text('Goals'), findsOneWidget);
    expect(find.text('Interaction'), findsOneWidget);
    expect(find.text('Grammar'), findsOneWidget);
    expect(find.text('Vocabulary'), findsOneWidget);
    expect(find.text('Speaking fluency'), findsOneWidget);
    expect(find.text('Pitch variation'), findsNothing);
    expect(find.text('Clarity proxy'), findsNothing);
    expect(find.text('Evidence quality'), findsOneWidget);
    expect(find.text('Enough spoken evidence.'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('Scenario-specific feedback'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('Scenario-specific feedback'), findsOneWidget);
    expect(find.text('Booking clarity'), findsOneWidget);
    expect(find.text('Words worth checking'), findsNothing);
    await tester.scrollUntilVisible(
      find.text('Language refinements'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('Language refinements'), findsOneWidget);
    expect(find.text('I have a reservation.'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.byKey(const ValueKey('roleplay-practice-words-added')),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    expect(
      find.text(
        '1 word needing pronunciation checks was moved to your Practice list.',
      ),
      findsOneWidget,
    );
  });
}
