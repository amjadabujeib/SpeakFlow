part of 'learning_plan_screen_test.dart';

void registerLearningPlanActiveTests() {
  testWidgets('finished first-week generation opens the active plan', (
    tester,
  ) async {
    final document = await tester.runAsync(
      () => const AssetPlpRepository().loadPlan(),
    );
    final repository = _GenerationPollingRepository(
      document!,
      finishImmediately: true,
    );

    await tester.pumpWidget(
      MaterialApp(home: LearningPlanScreen(repository: repository)),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));

    expect(repository.loadCalls, 2);
    expect(find.text('Confident English for Real Life'), findsOneWidget);
    expect(find.text('Preparing your first lessons'), findsNothing);
  });

  testWidgets('atomic week generation does not show fake zero progress', (
    tester,
  ) async {
    final document = await tester.runAsync(
      () => const AssetPlpRepository().loadPlan(),
    );
    final repository = _GenerationPollingRepository(
      document!,
      finishImmediately: false,
    );

    await tester.pumpWidget(
      MaterialApp(home: LearningPlanScreen(repository: repository)),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));

    expect(find.text('Preparing your first week…'), findsOneWidget);
    expect(find.text('0 of 20 lessons ready'), findsNothing);
    final progress = tester.widget<LinearProgressIndicator>(
      find.byType(LinearProgressIndicator),
    );
    expect(progress.value, isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('active plan makes regeneration progress unmistakable', (
    tester,
  ) async {
    final fixture = await tester.runAsync(
      () => const AssetPlpRepository().loadPlan(),
    );
    final generatingDocument = PlpDocument(
      formatRevision: fixture!.formatRevision,
      plan: fixture.plan,
      learnerSnapshot: fixture.learnerSnapshot,
      progress: fixture.progress,
      knowledgeSources: fixture.knowledgeSources,
      generation: const PlpGeneration(
        jobId: 'generation-job',
        status: 'generating_week_one',
        readyWeeks: 0,
        totalWeeks: 4,
        completedLessons: 0,
        totalLessons: 20,
        failedLessonIds: [],
        error: null,
      ),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: LearningPlanScreen(
          repository: _ActiveGenerationRepository(generatingDocument),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));

    expect(find.text('Building your new plan'), findsOneWidget);
    expect(find.text('Preferences applied'), findsOneWidget);
    expect(find.text('Four-week roadmap created'), findsOneWidget);
    expect(find.text('Writing and checking Week 1'), findsOneWidget);
    expect(find.textContaining('updates automatically'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('confirmed reset clears learner and opens onboarding', (
    tester,
  ) async {
    final document = await tester.runAsync(
      () => const AssetPlpRepository().loadPlan(),
    );
    final repository = _ResettableRepository(document!);
    await tester.pumpWidget(
      MaterialApp(home: LearningPlanScreen(repository: repository)),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Reset'));
    await tester.pumpAndSettle();
    expect(find.text('Reset learning plan?'), findsOneWidget);

    await tester.tap(find.text('Reset and start over'));
    await tester.pumpAndSettle();

    expect(repository.resetCalled, isTrue);
    expect(find.text('Build your learning path'), findsOneWidget);
    expect(find.text('Native language'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('Simple fixed rhythm'),
      250,
      scrollable: find.byType(Scrollable).last,
    );
    expect(find.text('Simple fixed rhythm'), findsOneWidget);
    expect(find.textContaining('5 days per week'), findsOneWidget);
    expect(find.text('Accent preference'), findsNothing);
    expect(find.text('Preferred learning contexts'), findsNothing);
    expect(find.text('Optional pronunciation priorities'), findsNothing);
    expect(find.byType(Slider), findsNothing);
  });

  testWidgets('weekly mission summary stays compact and personalized', (
    tester,
  ) async {
    final document = await tester.runAsync(() async {
      final raw =
          jsonDecode(
                await rootBundle.loadString(
                  AssetPlpRepository.defaultAssetPath,
                ),
              )
              as Map<String, dynamic>;
      final plan = raw['plan'] as Map<String, dynamic>;
      plan['architecture'] = 'weekly_mission';
      final firstWeek = (plan['weeks'] as List).first as Map<String, dynamic>;
      firstWeek['title'] = 'Week 1 · Solve a familiar device problem';
      firstWeek['mission'] = {
        'mission': {
          'title': 'Solve a familiar device problem',
          'premise': 'A device update caused a familiar problem.',
          'product': 'Recommend a clear next step.',
          'permitted_support': 'A short phrase bank.',
        },
        'can_do': 'Can understand a clear update and recommend a next step.',
        'goal': {'id': 'workplace', 'label': 'Workplace communication'},
        'interest': {'id': 'technology', 'label': 'Technology'},
        'scenario': {'id': 'technology.support', 'title': 'Technology support'},
      };
      return PlpDocument.fromJson(raw);
    });

    await tester.pumpWidget(
      MaterialApp(
        home: LearningPlanScreen(repository: _FixedRepository(document!)),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('YOUR WEEKLY OUTCOME'), findsOneWidget);
    expect(
      find.textContaining('Solve a familiar device problem'),
      findsOneWidget,
    );
    expect(
      find.text('Can understand a clear update and recommend a next step.'),
      findsOneWidget,
    );
    expect(
      find.text('Finish with Recommend a clear next step.'),
      findsOneWidget,
    );
    expect(find.text('Goal · Workplace communication'), findsOneWidget);
    expect(find.text('Interest · Technology'), findsOneWidget);
  });

  testWidgets('corrected mistakes leave review instead of looping', (
    tester,
  ) async {
    final activity = PlpActivity(
      id: 'question_one',
      type: PlpActivityType.multipleChoice,
      required: true,
      sourceRefs: const ['reviewed-source'],
      data: {
        'prompt': 'Which answer is correct?',
        'options': [
          {'id': 'wrong', 'text': 'Wrong answer'},
          {'id': 'right', 'text': 'Right answer'},
          {'id': 'other', 'text': 'Other answer'},
        ],
        'correct_option_id': 'right',
        'explanation': 'The right answer is supported.',
      },
    );
    final lesson = PlpLesson(
      id: 'correction_lesson',
      sequence: 1,
      type: PlpLessonType.grammar,
      title: 'Correction practice',
      description: 'Check and correct one answer.',
      estimatedMinutes: 5,
      xp: 20,
      completionPolicy: const PlpCompletionPolicy(
        mode: PlpCompletionMode.requiredActivities,
        minimumScore: null,
      ),
      objectives: const ['Correct the answer'],
      skillIds: const ['grammar.b1.core'],
      requiredLessonIds: const [],
      personalizationReason: 'Tests correction behavior.',
      grounding: const LessonGrounding(
        origin: 'curated',
        reviewStatus: 'reviewed',
        retrievalTags: ['cefr:B1'],
        sourceRefs: ['reviewed-source'],
      ),
      contentStatus: PlpContentStatus.ready,
      content: PlpLessonContent(
        intro: 'Answer the question, then correct it if needed.',
        activities: [activity],
      ),
    );
    final cached = <String, PlpAttemptResult>{};
    final submissionIds = <String>[];

    Future<PlpAttemptResult> submit(String _, JsonMap payload) async {
      final submissionId = payload['submission_id'] as String;
      submissionIds.add(submissionId);
      return cached.putIfAbsent(submissionId, () {
        final correct = payload['selected_option_id'] == 'right';
        final firstSubmission = cached.isEmpty;
        return PlpAttemptResult(
          correct: correct,
          score: correct ? 100 : 0,
          explanation: correct ? 'Correct.' : 'Try the supported answer.',
          correctResponse: const {'selected_option_id': 'right'},
          firstAttempt: firstSubmission,
          masteryEvidenceRecorded: firstSubmission,
          lessonCompleted: true,
          lessonScore: correct ? 100 : 0,
          newlyCompleted: firstSubmission,
          xpAwarded: firstSubmission ? 20 : 0,
          completedActivityIds: const {'question_one'},
        );
      });
    }

    Future<void> tap(String label) async {
      final target = find.text(label);
      await tester.ensureVisible(target);
      await tester.tap(target);
      await tester.pumpAndSettle();
    }

    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.dark,
        home: InteractiveLessonScreen(lesson: lesson, submitAttempt: submit),
      ),
    );
    await tester.pumpAndSettle();

    await tap('CONTINUE');
    await tap('Wrong answer');
    await tap('CHECK ANSWER');
    await tap('FINISH LESSON');
    expect(find.text('CORRECT 1 MISSED ITEM'), findsOneWidget);

    await tap('CORRECT 1 MISSED ITEM');
    await tap('Wrong answer');
    await tap('CHECK ANSWER');
    await tap('FINISH REVIEW');
    expect(find.text('CORRECT 1 MISSED ITEM'), findsOneWidget);

    await tap('CORRECT 1 MISSED ITEM');
    await tap('Right answer');
    await tap('CHECK ANSWER');
    await tap('FINISH REVIEW');

    expect(find.text('CORRECT 1 MISSED ITEM'), findsNothing);
    expect(find.text('PRACTISE MISTAKES AGAIN'), findsNothing);
    expect(
      find.textContaining('You corrected every missed item'),
      findsOneWidget,
    );
    expect(submissionIds, hasLength(3));
    expect(submissionIds[1], isNot(submissionIds[2]));
  });
}
