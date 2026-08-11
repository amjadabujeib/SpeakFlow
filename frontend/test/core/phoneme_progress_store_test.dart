import 'package:flutter_test/flutter_test.dart';
import '../support/test_app.dart';
import 'package:flutter/material.dart';
import 'package:speakflow/core/data/phoneme_progress_store.dart';
import 'package:speakflow/features/practice/practice_tab.dart';
import 'package:speakflow/features/shell/main_shell.dart';
import 'package:speakflow/core/providers/app_state.dart';

void main() {
  test('measured phoneme progress survives JSON persistence', () {
    final original = PhonemeProgress(
      symbol: 'θ',
      score: 64,
      observations: 3,
      lastPracticedAt: DateTime.utc(2026, 7, 24),
    );

    final restored = PhonemeProgress.fromJson(original.toJson());

    expect(restored.symbol, 'θ');
    expect(restored.score, 64);
    expect(restored.observations, 3);
    expect(restored.lastPracticedAt, original.lastPracticedAt);
  });

  test('persisted phoneme values are constrained to valid ranges', () {
    final restored = PhonemeProgress.fromJson({
      'symbol': ' ɹ ',
      'score': 140,
      'observations': 0,
      'last_practiced_at': 'invalid',
    });

    expect(restored.symbol, 'ɹ');
    expect(restored.score, 100);
    expect(restored.observations, 1);
  });

  test('phoneme map accepts only transcript-verified acoustic results', () {
    final verified = {
      'assessment': {'transcript_verified': true},
      'analysis': [
        {'char': 'p', 'score': 82},
      ],
    };
    final unverified = {
      'assessment': {'transcript_verified': false},
      'analysis': [
        {'char': 'p', 'score': 82},
      ],
    };

    expect(isPhonemeProgressEligibleResult(verified), isTrue);
    expect(isPhonemeProgressEligibleResult(unverified), isFalse);
  });

  testWidgets('fresh practice map does not display invented scores', (
    tester,
  ) async {
    await tester.pumpWidget(testApp(home: PracticeTab()));
    await tester.tap(find.text('Phoneme Map'));
    await tester.pumpAndSettle();

    expect(find.text('No measured phonemes yet'), findsOneWidget);
    expect(find.textContaining('88%'), findsNothing);
    expect(find.textContaining('28%'), findsNothing);
  });

  testWidgets('settings is in the top bar, not the bottom navigation', (
    tester,
  ) async {
    await tester.pumpWidget(
      testApp(
        home: MainShell(
          location: '/home',
          child: Center(child: Text('Shell child')),
        ),
      ),
    );
    await tester.pump();

    expect(find.byTooltip('Settings'), findsOneWidget);
    expect(find.text('Home'), findsOneWidget);
    expect(find.text('Practice'), findsOneWidget);
    expect(find.text('Chat'), findsOneWidget);
    expect(find.text('News'), findsOneWidget);
    expect(
      tester.getCenter(find.byTooltip('Settings')).dy,
      lessThan(tester.getCenter(find.text('Shell child')).dy),
    );
  });

  testWidgets('bottom navigation keeps stable edge spacing on wide phones', (
    tester,
  ) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(465, 930);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);

    await tester.pumpWidget(
      testApp(
        home: MainShell(location: '/home', child: SizedBox()),
      ),
    );

    final homeCenter = tester.getCenter(find.text('Home'));
    final newsCenter = tester.getCenter(find.text('News'));
    expect(homeCenter.dx, lessThanOrEqualTo(52));
    expect(465 - newsCenter.dx, lessThanOrEqualTo(52));
    expect(tester.takeException(), isNull);
  });

  testWidgets('removing the shell does not dispose the shared app state', (
    tester,
  ) async {
    await tester.pumpWidget(
      testApp(
        home: MainShell(location: '/home', child: SizedBox()),
      ),
    );
    await tester.pumpWidget(testApp(home: SizedBox()));
    expect(() => AppState().setMotherTongue('Arabic'), returnsNormally);
  });
}
