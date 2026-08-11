import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import '../../support/test_app.dart';
import 'package:speakflow/core/providers/app_state.dart';
import 'package:speakflow/features/learning_plan/data/plp_repository.dart';
import 'package:speakflow/features/learning_plan/domain/plp_models.dart';
import 'package:speakflow/features/shell/settings/settings_drawer.dart';

class _SettingsRepository extends PlpRepository {
  Map<String, dynamic>? savedProfile;
  int generationCalls = 0;
  bool? regenerateRequested;

  @override
  Future<PlpDocument> loadPlan() =>
      throw UnsupportedError('Not needed by this test.');

  @override
  Future<Map<String, dynamic>> loadProfile() async => {
    'cefr_level': 'B1',
    'native_language': 'Arabic',
    'learning_goals': ['Speak confidently'],
    'interests': ['Technology'],
  };

  @override
  Future<Map<String, dynamic>> saveProfile(Map<String, dynamic> profile) async {
    savedProfile = profile;
    return profile;
  }

  @override
  Future<String> generatePlan({bool regenerate = false}) async {
    generationCalls++;
    regenerateRequested = regenerate;
    return 'new-plan-job';
  }
}

void main() {
  testWidgets('settings saves changed interests and starts a new plan', (
    tester,
  ) async {
    final scaffoldKey = GlobalKey<ScaffoldState>();
    final repository = _SettingsRepository();
    final appState = AppState();
    final refreshToken = appState.planRefreshToken;

    await tester.pumpWidget(
      testApp(
        home: Scaffold(
          key: scaffoldKey,
          endDrawer: SettingsDrawer(appState: appState, repository: repository),
          body: const SizedBox.shrink(),
        ),
      ),
    );
    scaffoldKey.currentState!.openEndDrawer();
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text('Technology'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Technology'));
    await tester.ensureVisible(find.text('Music'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Music'));
    await tester.ensureVisible(find.text('History'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('History'));
    await tester.ensureVisible(find.text('Apply changes & build plan'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Apply changes & build plan'));
    await tester.pumpAndSettle();

    expect(repository.generationCalls, 1);
    expect(repository.regenerateRequested, isTrue);
    expect((repository.savedProfile!['interests'] as List).toSet(), {
      'Music',
      'History',
    });
    expect(repository.savedProfile!['learning_goals'], ['Speak confidently']);
    expect(appState.planRefreshToken, refreshToken + 1);
    expect(
      find.text('Your new plan is now being built on Home.'),
      findsOneWidget,
    );
  });
}
