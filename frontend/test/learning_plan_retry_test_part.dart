part of 'learning_plan_screen_test.dart';

void registerLearningPlanRetryTests() {
  testWidgets('failed generation retry cannot be submitted twice', (
    tester,
  ) async {
    final fixture = await tester.runAsync(
      () => const AssetPlpRepository().loadPlan(),
    );
    final failedDocument = PlpDocument(
      formatRevision: fixture!.formatRevision,
      plan: fixture.plan,
      learnerSnapshot: fixture.learnerSnapshot,
      progress: fixture.progress,
      knowledgeSources: fixture.knowledgeSources,
      generation: const PlpGeneration(
        jobId: 'generation-job',
        status: 'failed',
        readyWeeks: 0,
        totalWeeks: 4,
        completedLessons: 1,
        totalLessons: 8,
        failedLessonIds: ['w01_l02_assessment'],
        error: 'Groq is temporarily rate-limited.',
      ),
    );
    final repository = _PendingRetryRepository(failedDocument);
    await tester.pumpWidget(
      MaterialApp(home: LearningPlanScreen(repository: repository)),
    );
    await tester.pumpAndSettle();

    await tester.scrollUntilVisible(
      find.text('Continue generating'),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.text('Continue generating'));
    await tester.pump();
    await tester.tap(find.text('Retrying…'));
    await tester.pump();

    expect(repository.retryCalls, 1);
    expect(find.text('Retrying…'), findsOneWidget);
    expect(find.text('Plan generation paused'), findsOneWidget);
    expect(find.textContaining('assembled locally'), findsNothing);
  });

  testWidgets('rate-limited generation disables retry until cooldown ends', (
    tester,
  ) async {
    final fixture = await tester.runAsync(
      () => const AssetPlpRepository().loadPlan(),
    );
    final failedDocument = PlpDocument(
      formatRevision: fixture!.formatRevision,
      plan: fixture.plan,
      learnerSnapshot: fixture.learnerSnapshot,
      progress: fixture.progress,
      knowledgeSources: fixture.knowledgeSources,
      generation: PlpGeneration(
        jobId: 'generation-job',
        status: 'failed',
        readyWeeks: 0,
        totalWeeks: 4,
        completedLessons: 0,
        totalLessons: 20,
        failedLessonIds: const ['w01_l01_input_noticing'],
        error: 'Groq is temporarily rate-limited.',
        failureKind: 'rate_limited',
        retryAvailableAt: DateTime.now().toUtc().add(
          const Duration(seconds: 45),
        ),
        retryAfterSeconds: 45,
      ),
    );
    final repository = _PendingRetryRepository(failedDocument);
    await tester.pumpWidget(
      MaterialApp(home: LearningPlanScreen(repository: repository)),
    );
    await tester.pumpAndSettle();

    await tester.scrollUntilVisible(
      find.textContaining('Retry in '),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    final button = tester.widget<FilledButton>(
      find.ancestor(
        of: find.textContaining('Retry in '),
        matching: find.byWidgetPredicate((widget) => widget is FilledButton),
      ),
    );
    expect(button.onPressed, isNull);
    expect(find.textContaining('Retry in '), findsOneWidget);
    expect(repository.retryCalls, 0);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('rate-limited generation waits and resumes automatically', (
    tester,
  ) async {
    final fixture = await tester.runAsync(
      () => const AssetPlpRepository().loadPlan(),
    );
    final waitingDocument = PlpDocument(
      formatRevision: fixture!.formatRevision,
      plan: fixture.plan,
      learnerSnapshot: fixture.learnerSnapshot,
      progress: fixture.progress,
      knowledgeSources: fixture.knowledgeSources,
      generation: PlpGeneration(
        jobId: 'generation-job',
        status: 'waiting_for_model',
        readyWeeks: 0,
        totalWeeks: 4,
        completedLessons: 0,
        totalLessons: 20,
        failedLessonIds: const [],
        error: 'Groq’s token window is briefly full.',
        failureKind: 'rate_limited',
        retryAvailableAt: DateTime.now().toUtc().add(
          const Duration(seconds: 45),
        ),
        retryAfterSeconds: 45,
      ),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: LearningPlanScreen(
          repository: _PendingRetryRepository(waitingDocument),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('Waiting for Groq’s token window'), findsOneWidget);
    expect(find.textContaining('resume automatically'), findsOneWidget);
    expect(find.textContaining('Continue generating'), findsNothing);
    await tester.pumpWidget(const SizedBox.shrink());
  });
}
