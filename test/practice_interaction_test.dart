import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:just_talk/core/theme/app_theme.dart';
import 'package:just_talk/features/practice/pronunciation_screen.dart';
import 'package:just_talk/shared/widgets/dictionary_popup.dart';

void main() {
  test('practice pass requires both accuracy and completeness thresholds', () {
    expect(
      isPracticePronunciationPass({'accuracy': 85, 'completeness': 90}),
      isTrue,
    );
    expect(
      isPracticePronunciationPass({'accuracy': 84, 'completeness': 100}),
      isFalse,
    );
    expect(
      isPracticePronunciationPass({'accuracy': 100, 'completeness': 89}),
      isFalse,
    );
  });

  testWidgets('pronunciation shortcut opens without a fabricated target', (
    tester,
  ) async {
    await tester.pumpWidget(const MaterialApp(home: PronunciationScreen()));
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
      MaterialApp(
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
      MaterialApp(
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
