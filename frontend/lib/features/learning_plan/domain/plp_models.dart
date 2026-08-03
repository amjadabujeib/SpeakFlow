import 'dart:collection';

part 'plp_plan_models.dart';
part 'plp_lesson_models.dart';
part 'plp_progress_models.dart';
part 'plp_model_validation.dart';

typedef JsonMap = Map<String, dynamic>;

enum PlpLessonType {
  vocabulary,
  grammar,
  pronunciation,
  reading,
  listening,
  speaking,
  discourse,
  assessment,
}

enum PlpLessonStatus { locked, available, inProgress, completed }

enum PlpContentStatus { pending, ready, failed }

enum PlpCompletionMode { requiredActivities, minimumScore }

enum PlpActivityType {
  vocabularyCard,
  concept,
  pronunciationDrill,
  multipleChoice,
  fillBlank,
  readingComprehension,
  listeningComprehension,
  sentenceOrder,
  guidedSpeaking,
}

enum PlpActivityPhase {
  unspecified,
  learn,
  guidedPractice,
  independentCheck,
  review,
}

class PlpFormatException implements Exception {
  final String message;

  const PlpFormatException(this.message);

  @override
  String toString() => 'Invalid learning plan data: $message';
}

class PlpDocument {
  static const supportedFormatRevision = 1;

  final int formatRevision;
  final PlpPlan plan;
  final LearnerSnapshot learnerSnapshot;
  final PlpProgress progress;
  final List<PlpKnowledgeSource> knowledgeSources;
  final PlpGeneration? generation;

  PlpDocument({
    required this.formatRevision,
    required this.plan,
    required this.learnerSnapshot,
    required this.progress,
    required this.knowledgeSources,
    this.generation,
  }) {
    _validate();
  }

  factory PlpDocument.fromJson(JsonMap json) {
    final formatRevision = _requiredInt(json, 'format_revision', r'$');
    if (formatRevision != supportedFormatRevision) {
      throw PlpFormatException(
        'unsupported format_revision $formatRevision; expected '
        '$supportedFormatRevision',
      );
    }
    return PlpDocument(
      formatRevision: formatRevision,
      plan: PlpPlan.fromJson(_requiredMap(json, 'plan', r'$')),
      learnerSnapshot: LearnerSnapshot.fromJson(
        _requiredMap(json, 'learner_snapshot', r'$'),
      ),
      progress: PlpProgress.fromJson(_requiredMap(json, 'progress', r'$')),
      knowledgeSources: _requiredMapList(
        json,
        'knowledge_sources',
        r'$',
      ).map(PlpKnowledgeSource.fromJson).toList(growable: false),
      generation: json['generation'] == null
          ? null
          : PlpGeneration.fromJson(_requiredMap(json, 'generation', r'$')),
    );
  }

  List<PlpLesson> get lessons => [
    for (final week in plan.weeks)
      for (final unit in week.units) ...unit.lessons,
  ];

  Map<String, PlpLesson> get lessonById => {
    for (final lesson in lessons) lesson.id: lesson,
  };

  int get completedLessonCount => lessons
      .where((lesson) => statusOf(lesson) == PlpLessonStatus.completed)
      .length;

  double get completionRatio =>
      lessons.isEmpty ? 0 : completedLessonCount / lessons.length;

  int get earnedXp => lessons
      .where((lesson) => statusOf(lesson) == PlpLessonStatus.completed)
      .fold(0, (total, lesson) => total + lesson.xp);

  int get totalXp => lessons.fold(0, (total, lesson) => total + lesson.xp);

  PlpLessonStatus statusOf(PlpLesson lesson) {
    if (!lesson.isReady) return PlpLessonStatus.locked;
    final state = progress.lessonStates[lesson.id];
    if (state?.status == StoredLessonStatus.completed) {
      return PlpLessonStatus.completed;
    }
    if (state?.status == StoredLessonStatus.inProgress ||
        progress.currentLessonId == lesson.id) {
      return PlpLessonStatus.inProgress;
    }
    final allPrerequisitesComplete = lesson.requiredLessonIds.every(
      (id) => progress.lessonStates[id]?.status == StoredLessonStatus.completed,
    );
    return allPrerequisitesComplete
        ? PlpLessonStatus.available
        : PlpLessonStatus.locked;
  }

  PlpDocument withLessonResult(String lessonId, {required int score}) {
    final lesson = lessonById[lessonId];
    if (lesson == null) {
      throw ArgumentError.value(lessonId, 'lessonId', 'unknown lesson');
    }
    if (score < 0 || score > 100) {
      throw RangeError.range(score, 0, 100, 'score');
    }
    if (statusOf(lesson) == PlpLessonStatus.locked) {
      throw StateError('cannot complete locked lesson $lessonId');
    }
    final oldState = progress.lessonStates[lessonId];
    final states = Map<String, LessonProgress>.from(progress.lessonStates);
    final passed =
        oldState?.status == StoredLessonStatus.completed ||
        lesson.completionPolicy.isSatisfiedBy(score);
    if (!passed) {
      states[lessonId] = LessonProgress(
        status: StoredLessonStatus.inProgress,
        progressFraction: 0,
        bestScore: oldState?.bestScore == null
            ? score
            : (score > oldState!.bestScore! ? score : oldState.bestScore),
        attempts: (oldState?.attempts ?? 0) + 1,
        completedAt: null,
      );
      return PlpDocument(
        formatRevision: formatRevision,
        plan: plan,
        learnerSnapshot: learnerSnapshot,
        progress: progress.copyWith(
          currentLessonId: lessonId,
          lessonStates: states,
        ),
        knowledgeSources: knowledgeSources,
        generation: generation,
      );
    }
    states[lessonId] = LessonProgress(
      status: StoredLessonStatus.completed,
      progressFraction: 1,
      bestScore: oldState?.bestScore == null
          ? score
          : (score > oldState!.bestScore! ? score : oldState.bestScore),
      attempts: (oldState?.attempts ?? 0) + 1,
      completedAt: oldState?.completedAt ?? DateTime.now().toUtc(),
    );

    final ordered = lessons;
    final completedIndex = ordered.indexWhere((item) => item.id == lessonId);
    String? nextLessonId;
    for (var index = completedIndex + 1; index < ordered.length; index++) {
      final candidate = ordered[index];
      if (states[candidate.id]?.status == StoredLessonStatus.completed) {
        continue;
      }
      if (candidate.requiredLessonIds.every(
        (id) => states[id]?.status == StoredLessonStatus.completed,
      )) {
        nextLessonId = candidate.id;
        break;
      }
    }
    if (nextLessonId != null && states[nextLessonId] == null) {
      states[nextLessonId] = const LessonProgress(
        status: StoredLessonStatus.inProgress,
        progressFraction: 0,
        bestScore: null,
        attempts: 0,
        completedAt: null,
      );
    }

    return PlpDocument(
      formatRevision: formatRevision,
      plan: plan,
      learnerSnapshot: learnerSnapshot,
      progress: progress.copyWith(
        currentLessonId: nextLessonId,
        lessonStates: states,
      ),
      knowledgeSources: knowledgeSources,
      generation: generation,
    );
  }

  PlpDocument withCompletedLesson(String lessonId, {required int score}) =>
      withLessonResult(lessonId, score: score);

  void _validate() {
    if (plan.revision <= 0 || plan.weeks.isEmpty) {
      throw const PlpFormatException(
        'plan revision must be positive and weeks must not be empty',
      );
    }
    if (plan.weeks.length != plan.schedule.durationWeeks) {
      throw PlpFormatException(
        'plan.schedule.duration_weeks must equal the number of weeks',
      );
    }
    final allIds = <String>{plan.id};
    final sourceIds = <String>{};
    for (final source in knowledgeSources) {
      if (!sourceIds.add(source.id)) {
        throw PlpFormatException('duplicate knowledge source id ${source.id}');
      }
    }
    final orderedLessonIds = <String>[];
    for (var weekIndex = 0; weekIndex < plan.weeks.length; weekIndex++) {
      final week = plan.weeks[weekIndex];
      if (week.sequence != weekIndex + 1 || week.units.isEmpty) {
        throw PlpFormatException(
          'week ${week.id} has an invalid sequence or no units',
        );
      }
      _addUniqueId(allIds, week.id, 'week');
      for (var unitIndex = 0; unitIndex < week.units.length; unitIndex++) {
        final unit = week.units[unitIndex];
        if (unit.sequence != unitIndex + 1 || unit.lessons.isEmpty) {
          throw PlpFormatException(
            'unit ${unit.id} has an invalid sequence or no lessons',
          );
        }
        _addUniqueId(allIds, unit.id, 'unit');
        for (
          var lessonIndex = 0;
          lessonIndex < unit.lessons.length;
          lessonIndex++
        ) {
          final lesson = unit.lessons[lessonIndex];
          if (lesson.sequence != lessonIndex + 1) {
            throw PlpFormatException(
              'lesson ${lesson.id} has an invalid sequence',
            );
          }
          _addUniqueId(allIds, lesson.id, 'lesson');
          orderedLessonIds.add(lesson.id);
          for (final activity
              in lesson.content?.activities ?? const <PlpActivity>[]) {
            _addUniqueId(allIds, activity.id, 'activity');
            for (final skillId in activity.skillIds) {
              if (!lesson.skillIds.contains(skillId)) {
                throw PlpFormatException(
                  'activity ${activity.id} refers to skill $skillId outside '
                  'lesson ${lesson.id}',
                );
              }
            }
            for (final sourceRef in activity.sourceRefs) {
              if (!sourceIds.contains(sourceRef)) {
                throw PlpFormatException(
                  'activity ${activity.id} refers to unknown knowledge source '
                  '$sourceRef',
                );
              }
            }
          }
          for (final sourceRef in lesson.grounding.sourceRefs) {
            if (!sourceIds.contains(sourceRef)) {
              throw PlpFormatException(
                'lesson ${lesson.id} refers to unknown knowledge source '
                '$sourceRef',
              );
            }
          }
        }
      }
    }

    final lessonIds = orderedLessonIds.toSet();
    for (var index = 0; index < lessons.length; index++) {
      final lesson = lessons[index];
      for (final prerequisiteId in lesson.requiredLessonIds) {
        if (!lessonIds.contains(prerequisiteId)) {
          throw PlpFormatException(
            'lesson ${lesson.id} refers to unknown prerequisite '
            '$prerequisiteId',
          );
        }
        final prerequisiteIndex = orderedLessonIds.indexOf(prerequisiteId);
        if (prerequisiteIndex >= index) {
          throw PlpFormatException(
            'lesson ${lesson.id} prerequisite $prerequisiteId must appear '
            'earlier in the plan',
          );
        }
      }
    }

    for (final lessonId in progress.lessonStates.keys) {
      if (!lessonIds.contains(lessonId)) {
        throw PlpFormatException('progress refers to unknown lesson $lessonId');
      }
    }
    final inProgressIds = progress.lessonStates.entries
        .where((entry) => entry.value.status == StoredLessonStatus.inProgress)
        .map((entry) => entry.key)
        .toList(growable: false);
    if (inProgressIds.length > 1 ||
        (inProgressIds.isEmpty && progress.currentLessonId != null) ||
        (inProgressIds.isNotEmpty &&
            inProgressIds.single != progress.currentLessonId)) {
      throw const PlpFormatException(
        'progress must have exactly one matching current/in-progress lesson, '
        'or neither when the plan is complete',
      );
    }
    final currentLessonId = progress.currentLessonId;
    if (currentLessonId != null && !lessonIds.contains(currentLessonId)) {
      throw PlpFormatException(
        'progress.current_lesson_id refers to unknown lesson '
        '$currentLessonId',
      );
    }
    if (currentLessonId != null) {
      final currentLesson = lessonById[currentLessonId]!;
      final prerequisitesComplete = currentLesson.requiredLessonIds.every(
        (id) =>
            progress.lessonStates[id]?.status == StoredLessonStatus.completed,
      );
      if (!prerequisitesComplete) {
        throw PlpFormatException(
          'current lesson $currentLessonId has incomplete prerequisites',
        );
      }
    }
  }
}
