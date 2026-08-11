part of 'learning_plan_screen_test.dart';

void registerLearningPlanOnboardingTests() {
  testWidgets('onboarding starts generation without revealing the app shell', (
    tester,
  ) async {
    final repository = _OnboardingRepository();
    String? generatedJob;
    await tester.pumpWidget(
      testApp(
        home: PlpOnboardingScreen(
          repository: repository,
          allowBack: false,
          onGenerationStarted: (jobId) => generatedJob = jobId,
        ),
      ),
    );

    await tester.scrollUntilVisible(
      find.text('GENERATE MY PLAN'),
      300,
      scrollable: find.byType(Scrollable),
    );
    await tester.tap(find.text('GENERATE MY PLAN'));
    await tester.pumpAndSettle();

    expect(generatedJob, 'job-from-onboarding');
    expect(repository.savedProfile?['cefr_level'], 'B1');
    expect(repository.savedProfile?['native_language'], 'Arabic');
    expect(find.byTooltip('Back'), findsNothing);
  });

  testWidgets('onboarding enters Home as soon as generation starts', (
    tester,
  ) async {
    final repository = _OnboardingRepository();
    final router = GoRouter(
      initialLocation: '/start',
      routes: [
        GoRoute(
          path: '/start',
          builder: (_, __) => FirstRunGate(repository: repository),
        ),
        GoRoute(
          path: '/home',
          builder: (_, __) => const Scaffold(body: Text('HOME SHELL')),
        ),
      ],
    );
    addTearDown(router.dispose);

    await tester.pumpWidget(
      ProviderScope(child: MaterialApp.router(routerConfig: router)),
    );
    await tester.pumpAndSettle();
    expect(find.text('Build your learning path'), findsOneWidget);

    await tester.scrollUntilVisible(
      find.text('GENERATE MY PLAN'),
      300,
      scrollable: find.byType(Scrollable),
    );
    await tester.tap(find.text('GENERATE MY PLAN'));
    await tester.pumpAndSettle();

    expect(find.text('HOME SHELL'), findsOneWidget);
    expect(repository.savedProfile, isNotNull);
  });

  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('learning plan renders validated mock data', (tester) async {
    final document = await tester.runAsync(
      () => const AssetPlpRepository().loadPlan(),
    );
    expect(document, isNotNull);
    await tester.pumpWidget(
      testApp(
        home: LearningPlanScreen(repository: _FixedRepository(document!)),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));

    expect(find.text('Confident English for Real Life'), findsOneWidget);
    expect(find.text('Travel with confidence'), findsOneWidget);
    expect(find.text('Airport essentials'), findsOneWidget);
    expect(find.text('Plan progress'), findsOneWidget);
    expect(find.text('1/16 lessons'), findsOneWidget);
    expect(find.text('B1 → B2'), findsOneWidget);
    expect(find.text('4 weeks'), findsOneWidget);
    expect(find.text('20 min/day'), findsOneWidget);
    expect(find.text(document.plan.description), findsNothing);

    final scaffold = tester.widget<Scaffold>(find.byType(Scaffold).first);
    expect(scaffold.backgroundColor, AppColors.background);
    final appBar = tester.widget<AppBar>(find.byType(AppBar).first);
    expect(appBar.backgroundColor, AppColors.surface);
  });

  testWidgets('embedded plan is the Home content without an open-plan button', (
    tester,
  ) async {
    final document = await tester.runAsync(
      () => const AssetPlpRepository().loadPlan(),
    );
    await tester.pumpWidget(
      testApp(
        home: LearningPlanScreen(
          repository: _FixedRepository(document!),
          embedded: true,
          embeddedTop: const Text('HOME ACTIONS'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('HOME ACTIONS'), findsOneWidget);
    expect(find.text('Confident English for Real Life'), findsOneWidget);
    expect(find.text('Open learning plan'), findsNothing);
    expect(find.text('Your focus'), findsNothing);
    expect(find.byType(AppBar), findsNothing);
  });

  testWidgets('generated lessons use the app dark theme', (tester) async {
    final document = await tester.runAsync(
      () => const AssetPlpRepository().loadPlan(),
    );
    final lesson = document!.lessons.firstWhere(
      (candidate) => candidate.content != null,
    );
    await tester.pumpWidget(
      testApp(
        theme: AppTheme.dark,
        home: InteractiveLessonScreen(lesson: lesson),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text(lesson.title), findsOneWidget);
    final scaffold = tester.widget<Scaffold>(find.byType(Scaffold));
    expect(scaffold.backgroundColor, AppColors.background);
    final title = tester.widget<Text>(find.text(lesson.title));
    expect(title.style?.color, AppColors.textPrimary);
    expect(find.text('LESSON GOAL'), findsOneWidget);
    expect(find.text('How this lesson works'), findsNothing);
    expect(find.text('Why this is in your plan'), findsNothing);
    expect(find.text(lesson.personalizationReason), findsNothing);
    expect(find.text('${lesson.xp} XP'), findsNothing);
  });

  testWidgets('Home tools stay clear on a narrow phone', (tester) async {
    final document = await tester.runAsync(
      () => const AssetPlpRepository().loadPlan(),
    );
    await tester.binding.setSurfaceSize(const Size(320, 700));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      testApp(
        theme: AppTheme.dark,
        home: HomeTab(repository: _FixedRepository(document!)),
      ),
    );
    await tester.pumpAndSettle();

    for (final title in ['Fix grammar', 'Practice speech', 'Look up words']) {
      expect(find.text(title), findsOneWidget);
      final icon = tester.widget<Container>(
        find.byKey(ValueKey('home-action-icon-$title')),
      );
      expect((icon.decoration! as BoxDecoration).shape, BoxShape.circle);
      expect(icon.constraints?.maxWidth, 72);
    }
    expect(
      tester.getCenter(find.text('Fix grammar')).dx,
      lessThan(tester.getCenter(find.text('Practice speech')).dx),
    );
    expect(
      tester.getCenter(find.text('Practice speech')).dx,
      lessThan(tester.getCenter(find.text('Look up words')).dx),
    );
    expect(tester.takeException(), isNull);
  });
}
