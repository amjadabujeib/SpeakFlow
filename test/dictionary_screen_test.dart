import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:just_talk/core/theme/app_theme.dart';
import 'package:just_talk/features/home/dictionary_screen.dart';

void main() {
  testWidgets('dictionary shows learner translation, meaning, and examples', (
    tester,
  ) async {
    String? requestedWord;
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.dark,
        home: DictionaryScreen(
          lookup: (word) async {
            requestedWord = word;
            return {
              'word': 'wrong model word',
              'phonetic': '/ˈdʒɜːni/',
              'part_of_speech': 'noun',
              'translation': 'رحلة',
              'translation_language': 'Arabic',
              'definition': 'An act of travelling from one place to another.',
              'examples': [
                'The journey took three hours.',
                'We began our journey early.',
              ],
            };
          },
        ),
      ),
    );

    await tester.enterText(
      find.byKey(const ValueKey('dictionary-input')),
      'journey',
    );
    await tester.tap(find.byKey(const ValueKey('dictionary-search')));
    await tester.pump();
    await tester.pumpAndSettle();

    expect(requestedWord, 'journey');
    expect(
      find.descendant(
        of: find.byKey(const ValueKey('dictionary-entry-journey')),
        matching: find.text('journey'),
      ),
      findsOneWidget,
    );
    expect(find.text('wrong model word'), findsNothing);
    expect(find.text('ARABIC'), findsOneWidget);
    expect(find.text('رحلة'), findsOneWidget);
    expect(
      find.text('An act of travelling from one place to another.'),
      findsOneWidget,
    );
    expect(find.text('The journey took three hours.'), findsOneWidget);
    expect(find.text('We began our journey early.'), findsOneWidget);
  });

  testWidgets('dictionary requires one English word', (tester) async {
    var calls = 0;
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.dark,
        home: DictionaryScreen(
          lookup: (_) async {
            calls += 1;
            return {};
          },
        ),
      ),
    );

    await tester.enterText(
      find.byKey(const ValueKey('dictionary-input')),
      'two words',
    );
    await tester.tap(find.byKey(const ValueKey('dictionary-search')));
    await tester.pump();

    expect(calls, 0);
    expect(find.text('Enter one English word.'), findsOneWidget);
  });
}
