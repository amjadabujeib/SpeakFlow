import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import '../../support/test_app.dart';
import 'package:speakflow/core/theme/app_theme.dart';
import 'package:speakflow/features/practice/grammar_check_screen.dart';
import 'package:speakflow/features/practice/pronunciation_screen.dart';
import 'package:speakflow/features/news/widgets/dictionary_popup.dart';
import 'package:speakflow/main.dart' as app_entry;

void main() {
  test(
    'app font preference preserves bounded system accessibility scaling',
    () {
      expect(app_entry.effectiveTextScale(1.5, 1.2), closeTo(1.8, 0.0001));
      expect(app_entry.effectiveTextScale(3, 1.3), 2);
      expect(app_entry.effectiveTextScale(0.5, 0.85), 0.85);
    },
  );

  testWidgets(
    'grammar footer stays within a narrow phone and shows its limit',
    (tester) async {
      tester.view.physicalSize = const Size(393, 852);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(testApp(home: GrammarCheckScreen()));
      await tester.pump(const Duration(milliseconds: 500));

      expect(find.text('0/500'), findsOneWidget);
      expect(tester.takeException(), isNull);

      await tester.enterText(find.byType(TextField), 'I has a device problem.');
      await tester.pump();

      expect(find.text('23/500'), findsOneWidget);
      expect(find.text('Clear'), findsOneWidget);
      expect(find.text('💡 Try Example'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  test('practice pass uses the backend conservative assessment', () {
    expect(
      isPracticePronunciationPass({
        'assessment': {'passed': true},
        'scores': {'accuracy': 82, 'completeness': 100},
      }),
      isTrue,
    );
    expect(
      isPracticePronunciationPass({
        'assessment': {'passed': false},
        'scores': {'accuracy': 99, 'completeness': 100},
      }),
      isFalse,
    );
    expect(
      isPracticePronunciationPass({
        'assessment': {'passed': null},
      }),
      isFalse,
    );
    expect(isPracticePronunciationPass({'accuracy': 100}), isFalse);
  });

  testWidgets('pronunciation shortcut opens without a fabricated target', (
    tester,
  ) async {
    await tester.pumpWidget(testApp(home: PronunciationScreen()));
    await tester.pump(const Duration(milliseconds: 100));

    final input = tester.widget<TextField>(find.byType(TextField));
    expect(input.controller!.text, isEmpty);
    expect(find.text('hello'), findsNothing);
    expect(
      find.byKey(const ValueKey('pronunciation-guide-empty')),
      findsOneWidget,
    );
    final recordButton = tester.widget<GestureDetector>(
      find.byKey(const ValueKey('pronunciation-record-button')),
    );
    expect(recordButton.onTap, isNull);

    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('dictionary never substitutes a different returned word', (
    tester,
  ) async {
    String? lookedUpWord;
    await tester.pumpWidget(
      testApp(
        theme: AppTheme.dark,
        home: Scaffold(
          body: DictionaryPopup(
            word: 'technology',
            tapPosition: const Offset(200, 100),
            lookup: (word) async {
              lookedUpWord = word;
              return {
                'word': 'thoroughly',
                'definition': 'The selected definition.',
              };
            },
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));

    expect(lookedUpWord, 'technology');
    expect(find.text('technology'), findsOneWidget);
    expect(find.text('thoroughly'), findsNothing);
    expect(find.text('The selected definition.'), findsOneWidget);
  });

  testWidgets('dictionary failure shows an error instead of mock content', (
    tester,
  ) async {
    await tester.pumpWidget(
      testApp(
        theme: AppTheme.dark,
        home: Scaffold(
          body: DictionaryPopup(
            word: 'technology',
            tapPosition: const Offset(200, 100),
            lookup: (_) async => {'error': 'Lookup unavailable.'},
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));

    expect(find.text('Could not look up “technology”.'), findsOneWidget);
    expect(find.text('Lookup unavailable.'), findsOneWidget);
    expect(find.text('thoroughly'), findsNothing);
  });
}
