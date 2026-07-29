import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:speakflow/features/chat/roleplay_message_bubbles.dart';

void main() {
  testWidgets('spoken transcript colors words from WhisperX confidence', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: RoleplayUserMessageBubble(
            text: 'I said ship, today.',
            correctedText: null,
            grammarFeedback: null,
            wordConfidence: [
              {'word': 'I', 'score': .95},
              {'word': 'said', 'score': .72},
              {'word': 'ship', 'score': .32},
              {'word': 'today', 'score': null},
            ],
            transcriptKey: ValueKey('roleplay-confidence-transcript'),
          ),
        ),
      ),
    );

    final transcript = tester.widget<Text>(
      find.byKey(const ValueKey('roleplay-confidence-transcript')),
    );
    expect(transcript.textSpan!.toPlainText(), 'I said ship, today.');

    final wordSpans = (transcript.textSpan! as TextSpan).children!
        .whereType<TextSpan>()
        .where(
          (span) => const {'I', 'said', 'ship', 'today'}.contains(span.text),
        )
        .toList(growable: false);
    final colors = {for (final span in wordSpans) span.text: span.style?.color};

    expect(colors['I'], const Color(0xFF86EFAC));
    expect(colors['said'], const Color(0xFFFDE68A));
    expect(colors['ship'], const Color(0xFFFCA5A5));
    expect(colors['today'], isNull);
  });

  testWidgets(
    'spoken user message has icon-only replay and grammar explanation',
    (tester) async {
      var replayCount = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: RoleplayUserMessageBubble(
              text: 'I has a reservation.',
              correctedText: 'I have a reservation.',
              grammarFeedback:
                  'Use “have” with the subject “I.” '
                  'Corrected: I have a reservation.',
              wordConfidence: const [],
              hasReplay: true,
              onReplay: () => replayCount++,
            ),
          ),
        ),
      );

      expect(find.byTooltip('Replay recording'), findsOneWidget);
      expect(find.byIcon(Icons.replay_rounded), findsOneWidget);
      expect(find.text('Replay'), findsNothing);
      expect(find.text('Grammar'), findsOneWidget);

      await tester.tap(find.byTooltip('Replay recording'));
      expect(replayCount, 1);

      await tester.tap(find.text('Grammar'));
      await tester.pumpAndSettle();

      expect(find.text('Your sentence'), findsOneWidget);
      expect(find.text('I has a reservation.'), findsWidgets);
      expect(find.text('Suggested correction'), findsOneWidget);
      expect(find.text('I have a reservation.'), findsOneWidget);
      expect(find.text('Explanation'), findsOneWidget);
      expect(find.text('Use “have” with the subject “I.”'), findsOneWidget);
      expect(
        find.textContaining('Corrected: I have a reservation.'),
        findsNothing,
      );
    },
  );

  testWidgets('grammar action reports when no mistake was detected', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: RoleplayUserMessageBubble(
            text: 'I have a reservation.',
            correctedText: null,
            grammarFeedback: 'Correct',
            wordConfidence: [],
          ),
        ),
      ),
    );

    await tester.tap(find.text('Grammar'));
    await tester.pumpAndSettle();

    expect(
      find.text('No grammar mistakes were detected in this sentence.'),
      findsOneWidget,
    );
    expect(find.text('Suggested correction'), findsNothing);
  });
}
