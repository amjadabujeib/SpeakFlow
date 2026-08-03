import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:speakflow/features/chat/roleplay_history_screen.dart';
import 'package:speakflow/features/chat/roleplay_models.dart';

void main() {
  testWidgets('saved conversation is displayed without live chat controls', (
    tester,
  ) async {
    Future<Map<String, dynamic>> loader(String _) async => {
      'read_only': true,
      'session': {
        'client_session_id': 'roleplay-history-1234',
        'scenario': 'Airport Check-in',
        'duration_seconds': 44,
      },
      'scenario': {
        'id': 'airport_check_in',
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
          'input_mode': 'audio',
          'user_text': 'I flying to Paris.',
          'assistant_text': 'May I see your passport?',
          'grammar_corrected_text': 'I am flying to Paris.',
          'grammar_feedback':
              'Add “am” after “I” to form the present continuous. '
              'Corrected: I am flying to Paris.',
          'word_confidence': [
            {'word': 'I', 'score': .95},
            {'word': 'flying', 'score': .42},
            {'word': 'to', 'score': .72},
            {'word': 'Paris', 'score': null},
          ],
          'created_at': '2026-07-26T07:00:00Z',
        },
      ],
    };

    await tester.pumpWidget(
      MaterialApp(
        home: RoleplayHistoryScreen(
          args: const RoleplayHistoryArgs(
            clientSessionId: 'roleplay-history-1234',
            title: 'Airport Check-in',
          ),
          loader: loader,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Conversation replay'), findsOneWidget);
    expect(find.text('Read only'), findsOneWidget);
    expect(find.text('WORD CONFIDENCE'), findsOneWidget);
    expect(find.text('Clear'), findsOneWidget);
    expect(find.text('Review'), findsOneWidget);
    expect(find.text('Low'), findsOneWidget);
    expect(find.text('Where are you flying today?'), findsOneWidget);
    expect(find.text('May I see your passport?'), findsOneWidget);
    expect(find.byType(TextField), findsNothing);
    expect(find.byIcon(Icons.send_rounded), findsNothing);

    final transcript = tester.widget<Text>(
      find.byKey(
        const ValueKey('history-confidence-transcript-turn-history-0001'),
      ),
    );
    expect(transcript.textSpan!.toPlainText(), 'I flying to Paris.');
    final wordSpans = (transcript.textSpan! as TextSpan).children!
        .whereType<TextSpan>()
        .where(
          (span) => const {'I', 'flying', 'to', 'Paris'}.contains(span.text),
        )
        .toList(growable: false);
    final colors = {for (final span in wordSpans) span.text: span.style?.color};
    expect(colors['I'], const Color(0xFF86EFAC));
    expect(colors['flying'], const Color(0xFFFCA5A5));
    expect(colors['to'], const Color(0xFFFDE68A));
    expect(colors['Paris'], isNull);

    await tester.ensureVisible(find.text('Grammar'));
    await tester.tap(find.text('Grammar'));
    await tester.pumpAndSettle();
    expect(find.text('I am flying to Paris.'), findsOneWidget);
    expect(
      find.text('Add “am” after “I” to form the present continuous.'),
      findsOneWidget,
    );
  });

  testWidgets('history layout remains usable on a narrow display', (
    tester,
  ) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(320, 700);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);

    Future<Map<String, dynamic>> loader(String _) async => {
      'read_only': true,
      'session': {'duration_seconds': 125},
      'scenario': {
        'id': 'airport_check_in',
        'category': 'Travel',
        'icon': '✈️',
        'title': 'Airport Check-in',
        'description': 'Check in for a flight.',
        'ai_role': 'check-in agent',
        'learner_role': 'passenger',
        'opening': 'Where are you flying today?',
        'objectives': const [],
      },
      'turns': const [],
    };

    await tester.pumpWidget(
      MaterialApp(
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(
            context,
          ).copyWith(textScaler: const TextScaler.linear(1.4)),
          child: child!,
        ),
        home: RoleplayHistoryScreen(
          args: const RoleplayHistoryArgs(
            clientSessionId: 'roleplay-history-1234',
            title: 'Airport Check-in',
          ),
          loader: loader,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Conversation replay'), findsOneWidget);
    expect(find.text('0 turns  •  2:05'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
