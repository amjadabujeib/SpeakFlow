import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:speakflow/plp/plp_models.dart';
import 'package:speakflow/plp/plp_repository.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('format errors use production-neutral learning-plan wording', () {
    expect(
      const PlpFormatException('missing field').toString(),
      'Invalid learning plan data: missing field',
    );
  });

  test('attempt feedback reveals the answer only after grading', () {
    final result = PlpAttemptResult.fromJson({
      'correct': false,
      'score': 0,
      'explanation': 'Battery life is the supported detail.',
      'correct_response': {'selected_option_id': 'battery'},
      'lesson_completed': false,
    });

    expect(result.correct, isFalse);
    expect(result.correctResponse, {'selected_option_id': 'battery'});
    expect(result.lessonScore, isNull);
    expect(result.newlyCompleted, isFalse);
    expect(result.xpAwarded, 0);
  });

  test('attempt feedback parses server-authoritative lesson outcome', () {
    final result = PlpAttemptResult.fromJson({
      'correct': true,
      'score': 100,
      'explanation': 'The answer is supported.',
      'correct_response': {'selected_option_id': 'supported'},
      'first_attempt': true,
      'mastery_evidence_recorded': true,
      'lesson_completed': true,
      'lesson_score': 82,
      'newly_completed': true,
      'xp_awarded': 35,
    });

    expect(result.lessonCompleted, isTrue);
    expect(result.lessonScore, 82);
    expect(result.newlyCompleted, isTrue);
    expect(result.xpAwarded, 35);
  });

  group('PLP v1 contract', () {
    test('loads the complete mock plan with derived progress', () async {
      final document = await const AssetPlpRepository().loadPlan();

      expect(document.schemaVersion, 1);
      expect(document.plan.weeks, hasLength(4));
      expect(document.lessons, hasLength(16));
      expect(
        document.lessons.expand((lesson) => lesson.content!.activities),
        hasLength(52),
      );
      expect(document.completedLessonCount, 1);
      expect(document.earnedXp, 20);
      expect(document.totalXp, 465);
      expect(document.plan.architecture, isNull);
      expect(document.plan.weeks.first.mission, isNull);
      expect(document.lessons.first.lessonRole, isNull);
      expect(document.lessons.first.canDoStatement, isNull);
      expect(document.lessons.first.contentInstanceId, isNull);
      expect(
        document.lessons.first.content!.activities.first.phase,
        PlpActivityPhase.unspecified,
      );
      expect(
        document.statusOf(document.lessonById['lesson_01_airport_words']!),
        PlpLessonStatus.completed,
      );
      expect(
        document.statusOf(document.lessonById['lesson_02_future_plans']!),
        PlpLessonStatus.inProgress,
      );
      expect(
        document.statusOf(document.lessonById['lesson_03_th_sounds']!),
        PlpLessonStatus.locked,
      );
    });

    test('completing a lesson unlocks the next prerequisite', () async {
      final document = await const AssetPlpRepository().loadPlan();
      final updated = document.withCompletedLesson(
        'lesson_02_future_plans',
        score: 75,
      );

      expect(
        updated.statusOf(updated.lessonById['lesson_02_future_plans']!),
        PlpLessonStatus.completed,
      );
      expect(
        updated.statusOf(updated.lessonById['lesson_03_th_sounds']!),
        PlpLessonStatus.inProgress,
      );
      expect(updated.progress.currentLessonId, 'lesson_03_th_sounds');
      expect(
        updated.progress.lessonStates['lesson_02_future_plans']!.bestScore,
        75,
      );
    });

    test('accepts empty retired learner snapshot preferences', () async {
      final raw =
          jsonDecode(
                await rootBundle.loadString(
                  AssetPlpRepository.defaultAssetPath,
                ),
              )
              as Map<String, dynamic>;
      final snapshot = raw['learner_snapshot'] as Map<String, dynamic>;
      snapshot['preferred_contexts'] = <String>[];
      snapshot['pronunciation_priorities'] = <String>[];

      final parsed = PlpDocument.fromJson(raw).learnerSnapshot;

      expect(parsed.preferredContexts, isEmpty);
      expect(parsed.pronunciationPriorities, isEmpty);
    });

    test('accepts omitted retired learner snapshot preferences', () async {
      final raw =
          jsonDecode(
                await rootBundle.loadString(
                  AssetPlpRepository.defaultAssetPath,
                ),
              )
              as Map<String, dynamic>;
      final snapshot = raw['learner_snapshot'] as Map<String, dynamic>;
      snapshot.remove('preferred_contexts');
      snapshot.remove('pronunciation_priorities');

      final parsed = PlpDocument.fromJson(raw).learnerSnapshot;

      expect(parsed.preferredContexts, isEmpty);
      expect(parsed.pronunciationPriorities, isEmpty);
    });

    test('a failed checkpoint records the attempt without unlocking', () async {
      var document = await const AssetPlpRepository().loadPlan();
      document = document.withLessonResult('lesson_02_future_plans', score: 50);
      document = document.withLessonResult('lesson_03_th_sounds', score: 50);
      document = document.withLessonResult(
        'lesson_04_airport_checkpoint',
        score: 50,
      );

      expect(
        document.statusOf(document.lessonById['lesson_04_airport_checkpoint']!),
        PlpLessonStatus.inProgress,
      );
      expect(
        document.statusOf(document.lessonById['lesson_05_appointment_words']!),
        PlpLessonStatus.locked,
      );
      expect(
        document
            .progress
            .lessonStates['lesson_04_airport_checkpoint']!
            .bestScore,
        50,
      );
      expect(
        document
            .progress
            .lessonStates['lesson_04_airport_checkpoint']!
            .attempts,
        1,
      );
    });

    test(
      'rejects an unknown prerequisite instead of silently locking',
      () async {
        final raw =
            jsonDecode(
                  await rootBundle.loadString(
                    AssetPlpRepository.defaultAssetPath,
                  ),
                )
                as Map<String, dynamic>;
        final plan = raw['plan'] as Map<String, dynamic>;
        final firstWeek = (plan['weeks'] as List).first as Map<String, dynamic>;
        final firstUnit =
            (firstWeek['units'] as List).first as Map<String, dynamic>;
        final secondLesson =
            (firstUnit['lessons'] as List)[1] as Map<String, dynamic>;
        secondLesson['required_lesson_ids'] = ['lesson_does_not_exist'];

        expect(
          () => PlpDocument.fromJson(raw),
          throwsA(isA<PlpFormatException>()),
        );
      },
    );

    test('rejects malformed question answer keys', () async {
      final raw =
          jsonDecode(
                await rootBundle.loadString(
                  AssetPlpRepository.defaultAssetPath,
                ),
              )
              as Map<String, dynamic>;
      final plan = raw['plan'] as Map<String, dynamic>;
      final firstWeek = (plan['weeks'] as List).first as Map<String, dynamic>;
      final firstUnit =
          (firstWeek['units'] as List).first as Map<String, dynamic>;
      final firstLesson =
          (firstUnit['lessons'] as List).first as Map<String, dynamic>;
      final activities =
          (firstLesson['content'] as Map<String, dynamic>)['activities']
              as List;
      final question =
          activities.firstWhere(
                (item) =>
                    (item as Map<String, dynamic>)['type'] == 'multiple_choice',
              )
              as Map<String, dynamic>;
      question['correct_option_id'] = 'missing';

      expect(
        () => PlpDocument.fromJson(raw),
        throwsA(isA<PlpFormatException>()),
      );
    });

    test('keeps completed legacy two-option activities readable', () async {
      final raw =
          jsonDecode(
                await rootBundle.loadString(
                  AssetPlpRepository.defaultAssetPath,
                ),
              )
              as Map<String, dynamic>;
      final plan = raw['plan'] as Map<String, dynamic>;
      final firstWeek = (plan['weeks'] as List).first as Map<String, dynamic>;
      final firstUnit =
          (firstWeek['units'] as List).first as Map<String, dynamic>;
      final firstLesson =
          (firstUnit['lessons'] as List).first as Map<String, dynamic>;
      final activities =
          (firstLesson['content'] as Map<String, dynamic>)['activities']
              as List;
      final question =
          activities.firstWhere(
                (item) =>
                    (item as Map<String, dynamic>)['type'] == 'multiple_choice',
              )
              as Map<String, dynamic>;
      question['options'] = (question['options'] as List).take(2).toList();

      expect(PlpDocument.fromJson(raw).lessons, isNotEmpty);
    });

    test(
      'stores activity skill bindings without breaking legacy activities',
      () async {
        final raw =
            jsonDecode(
                  await rootBundle.loadString(
                    AssetPlpRepository.defaultAssetPath,
                  ),
                )
                as Map<String, dynamic>;
        final plan = raw['plan'] as Map<String, dynamic>;
        final firstWeek = (plan['weeks'] as List).first as Map<String, dynamic>;
        final firstUnit =
            (firstWeek['units'] as List).first as Map<String, dynamic>;
        final firstLesson =
            (firstUnit['lessons'] as List).first as Map<String, dynamic>;
        final activities =
            (firstLesson['content'] as Map<String, dynamic>)['activities']
                as List;
        final boundActivity = activities.first as Map<String, dynamic>;
        boundActivity['skill_ids'] = ['vocabulary.travel.airport'];

        final document = PlpDocument.fromJson(raw);
        final parsedActivities = document.lessons.first.content!.activities;

        expect(parsedActivities.first.skillIds, ['vocabulary.travel.airport']);
        expect(parsedActivities.first.data, isNot(contains('skill_ids')));
        expect(parsedActivities[1].skillIds, isEmpty);
      },
    );

    test('rejects an activity binding outside its lesson skills', () async {
      final raw =
          jsonDecode(
                await rootBundle.loadString(
                  AssetPlpRepository.defaultAssetPath,
                ),
              )
              as Map<String, dynamic>;
      final plan = raw['plan'] as Map<String, dynamic>;
      final firstWeek = (plan['weeks'] as List).first as Map<String, dynamic>;
      final firstUnit =
          (firstWeek['units'] as List).first as Map<String, dynamic>;
      final firstLesson =
          (firstUnit['lessons'] as List).first as Map<String, dynamic>;
      final activities =
          (firstLesson['content'] as Map<String, dynamic>)['activities']
              as List;
      (activities.first as Map<String, dynamic>)['skill_ids'] = [
        'grammar.not_in_this_lesson',
      ];

      expect(
        () => PlpDocument.fromJson(raw),
        throwsA(isA<PlpFormatException>()),
      );
    });

    test(
      'parses additive mission, lesson, instance, and phase metadata',
      () async {
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
        firstWeek['mission'] = {
          'mission': {
            'title': 'Resolve a familiar technology problem',
            'premise': 'A device update has caused a familiar problem.',
            'product': 'Recommend a clear next step.',
            'permitted_support': 'A short phrase bank.',
          },
          'can_do': 'Can understand a clear update and recommend a next step.',
          'goal': {'id': 'workplace', 'label': 'Workplace communication'},
          'interest': {'id': 'technology', 'label': 'Technology'},
          'scenario': {
            'id': 'technology.support',
            'title': 'Technology support',
          },
        };
        final firstUnit =
            (firstWeek['units'] as List).first as Map<String, dynamic>;
        final firstLesson =
            (firstUnit['lessons'] as List).first as Map<String, dynamic>;
        firstLesson['lesson_role'] = 'input_noticing';
        firstLesson['can_do_statement'] =
            'Can identify the main problem in a short update.';
        firstLesson['content_instance_id'] = 'instance_20260717_01';
        final activities =
            (firstLesson['content'] as Map<String, dynamic>)['activities']
                as List;
        (activities.first as Map<String, dynamic>)['phase'] = 'guided_practice';

        final document = PlpDocument.fromJson(raw);
        final mission = document.plan.weeks.first.mission!;
        final lesson = document.lessons.first;
        final activity = lesson.content!.activities.first;

        expect(document.plan.architecture, 'mission_v3');
        expect(mission.title, 'Resolve a familiar technology problem');
        expect(
          mission.canDo,
          'Can understand a clear update and recommend a next step.',
        );
        expect(mission.goalLabel, 'Workplace communication');
        expect(mission.interestLabel, 'Technology');
        expect(lesson.lessonRole, 'input_noticing');
        expect(
          lesson.canDoStatement,
          'Can identify the main problem in a short update.',
        );
        expect(lesson.contentInstanceId, 'instance_20260717_01');
        expect(activity.phase, PlpActivityPhase.guidedPractice);
        expect(activity.data, isNot(contains('phase')));
      },
    );
  });
}
