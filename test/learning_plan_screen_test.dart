import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:just_talk/core/theme/app_colors.dart';
import 'package:just_talk/core/theme/app_theme.dart';
import 'package:just_talk/features/home/home_tab.dart';
import 'package:just_talk/lesson_screens.dart';
import 'package:just_talk/plp/first_run_gate.dart';
import 'package:just_talk/plp/learning_plan_screen.dart';
import 'package:just_talk/plp/onboarding_screen.dart';
import 'package:just_talk/plp/plp_models.dart';
import 'package:just_talk/plp/plp_repository.dart';

class _FixedRepository extends PlpRepository {
  final PlpDocument document;

  const _FixedRepository(this.document);

  @override
  Future<PlpDocument> loadPlan() async => document;
}

class _ResettableRepository extends _FixedRepository {
  bool resetCalled = false;

  _ResettableRepository(super.document);

  @override
  bool get isRemote => true;

  @override
  Future<void> resetLearner() async {
    resetCalled = true;
  }
}

class _ActiveGenerationRepository extends _FixedRepository {
  _ActiveGenerationRepository(super.document);

  @override
  bool get isRemote => true;

  @override
  Future<JsonMap> generationStatus(String jobId) async => {
    'job_id': jobId,
    'status': 'generating_week_one',
    'ready_weeks': 0,
    'total_weeks': 4,
    'completed_lessons': 0,
    'total_lessons': 20,
    'failed_lesson_ids': <String>[],
    'retry_after_seconds': 0,
  };
}

class _OnboardingRepository extends PlpRepository {
  JsonMap? savedProfile;

  @override
  Future<PlpDocument> loadPlan() => throw const PlpApiException(404, 'No plan');

  @override
  Future<JsonMap> saveProfile(JsonMap profile) async {
    savedProfile = profile;
    return profile;
  }

  @override
  Future<String> generatePlan() async => 'job-from-onboarding';

  @override
  Future<JsonMap> latestGeneration() =>
      throw const PlpApiException(404, 'No generation');
}

class _PendingRetryRepository extends _FixedRepository {
  int retryCalls = 0;
  final Completer<JsonMap> retryCompleter = Completer<JsonMap>();

  _PendingRetryRepository(super.document);

  @override
  bool get isRemote => true;

  @override
  Future<JsonMap> retryGeneration(String jobId) {
    retryCalls += 1;
    return retryCompleter.future;
  }
}

class _GenerationPollingRepository extends _FixedRepository {
  final bool finishImmediately;
  int loadCalls = 0;

  _GenerationPollingRepository(
    super.document, {
    required this.finishImmediately,
  });

  @override
  bool get isRemote => true;

  JsonMap get _queued => {
    'job_id': 'generation-job',
    'status': 'generating_week_one',
    'ready_weeks': 0,
    'total_weeks': 4,
    'completed_lessons': 0,
    'total_lessons': 20,
    'failed_lesson_ids': <String>[],
    'retry_after_seconds': 0,
  };

  @override
  Future<PlpDocument> loadPlan() async {
    loadCalls += 1;
    if (!finishImmediately || loadCalls == 1) {
      throw const PlpApiException(404, 'No active plan yet.');
    }
    return document;
  }

  @override
  Future<JsonMap> latestGeneration() async => _queued;

  @override
  Future<JsonMap> generationStatus(String jobId) async => finishImmediately
      ? {..._queued, 'status': 'idle', 'ready_weeks': 1, 'completed_lessons': 5}
      : _queued;
}

void main() {
  testWidgets('onboarding starts generation without revealing the app shell', (
    tester,
  ) async {
    final repository = _OnboardingRepository();
    String? generatedJob;
    await tester.pumpWidget(
      MaterialApp(
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

    await tester.pumpWidget(MaterialApp.router(routerConfig: router));
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
      MaterialApp(
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
      MaterialApp(
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
      MaterialApp(
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
      MaterialApp(
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
      schemaVersion: fixture!.schemaVersion,
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
      plan['architecture'] = 'mission_v3';
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

  testWidgets('failed generation retry cannot be submitted twice', (
    tester,
  ) async {
    final fixture = await tester.runAsync(
      () => const AssetPlpRepository().loadPlan(),
    );
    final failedDocument = PlpDocument(
      schemaVersion: fixture!.schemaVersion,
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
      schemaVersion: fixture!.schemaVersion,
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
      schemaVersion: fixture!.schemaVersion,
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
