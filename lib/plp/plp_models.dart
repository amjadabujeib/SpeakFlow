import 'dart:collection';

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
  static const supportedSchemaVersion = 2;

  final int schemaVersion;
  final PlpPlan plan;
  final LearnerSnapshot learnerSnapshot;
  final PlpProgress progress;
  final List<PlpKnowledgeSource> knowledgeSources;
  final PlpGeneration? generation;

  PlpDocument({
    required this.schemaVersion,
    required this.plan,
    required this.learnerSnapshot,
    required this.progress,
    required this.knowledgeSources,
    this.generation,
  }) {
    _validate();
  }

  factory PlpDocument.fromJson(JsonMap json) {
    final schemaVersion = _requiredInt(json, 'schema_version', r'$');
    if (schemaVersion != 1 && schemaVersion != supportedSchemaVersion) {
      throw PlpFormatException(
        'unsupported schema_version $schemaVersion; expected '
        '1 or $supportedSchemaVersion',
      );
    }
    return PlpDocument(
      schemaVersion: schemaVersion,
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
      generation: schemaVersion == 2
          ? PlpGeneration.fromJson(_requiredMap(json, 'generation', r'$'))
          : null,
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
        schemaVersion: schemaVersion,
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
      schemaVersion: schemaVersion,
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

class PlpKnowledgeSource {
  final String id;
  final String title;
  final String locator;
  final String license;
  final String version;

  const PlpKnowledgeSource({
    required this.id,
    required this.title,
    required this.locator,
    required this.license,
    required this.version,
  });

  factory PlpKnowledgeSource.fromJson(JsonMap json) => PlpKnowledgeSource(
    id: _requiredString(json, 'id', 'knowledge_source'),
    title: _requiredString(json, 'title', 'knowledge_source'),
    locator: _requiredString(json, 'locator', 'knowledge_source'),
    license: _requiredString(json, 'license', 'knowledge_source'),
    version: _requiredString(json, 'version', 'knowledge_source'),
  );
}

class PlpGeneration {
  final String jobId;
  final String status;
  final int readyWeeks;
  final int totalWeeks;
  final int completedLessons;
  final int totalLessons;
  final List<String> failedLessonIds;
  final String? error;
  final String? failureKind;
  final DateTime? retryAvailableAt;
  final int retryAfterSeconds;

  const PlpGeneration({
    required this.jobId,
    required this.status,
    required this.readyWeeks,
    required this.totalWeeks,
    required this.completedLessons,
    required this.totalLessons,
    required this.failedLessonIds,
    required this.error,
    this.failureKind,
    this.retryAvailableAt,
    this.retryAfterSeconds = 0,
  });

  factory PlpGeneration.fromJson(JsonMap json) {
    final retryText = _optionalString(json, 'retry_available_at', 'generation');
    final retryAt = retryText == null ? null : DateTime.tryParse(retryText);
    final retryAfter =
        _optionalInt(json, 'retry_after_seconds', 'generation') ?? 0;
    if ((retryText != null && retryAt == null) ||
        retryAfter < 0 ||
        retryAfter > 300) {
      throw const PlpFormatException(
        'generation contains invalid retry timing',
      );
    }
    return PlpGeneration(
      jobId: _requiredString(json, 'job_id', 'generation'),
      status: _requiredString(json, 'status', 'generation'),
      readyWeeks: _requiredInt(json, 'ready_weeks', 'generation'),
      totalWeeks: _requiredInt(json, 'total_weeks', 'generation'),
      completedLessons: _requiredInt(json, 'completed_lessons', 'generation'),
      totalLessons: _requiredInt(json, 'total_lessons', 'generation'),
      failedLessonIds: _requiredStringList(
        json,
        'failed_lesson_ids',
        'generation',
        allowEmpty: true,
      ),
      error: _optionalString(json, 'error', 'generation'),
      failureKind: _optionalString(json, 'failure_kind', 'generation'),
      retryAvailableAt: retryAt,
      retryAfterSeconds: retryAfter,
    );
  }
}

class PlpPlan {
  final String id;
  final int revision;
  final String? architecture;
  final String title;
  final String description;
  final String currentLevel;
  final String targetLevel;
  final String levelLabel;
  final PlpSchedule schedule;
  final List<String> focusAreas;
  final List<PlpWeek> weeks;

  const PlpPlan({
    required this.id,
    required this.revision,
    this.architecture,
    required this.title,
    required this.description,
    required this.currentLevel,
    required this.targetLevel,
    required this.levelLabel,
    required this.schedule,
    required this.focusAreas,
    required this.weeks,
  });

  factory PlpPlan.fromJson(JsonMap json) {
    final level = _requiredMap(json, 'level', 'plan');
    return PlpPlan(
      id: _requiredString(json, 'id', 'plan'),
      revision: _requiredInt(json, 'revision', 'plan'),
      architecture: _optionalString(json, 'architecture', 'plan'),
      title: _requiredString(json, 'title', 'plan'),
      description: _requiredString(json, 'description', 'plan'),
      currentLevel: _requiredString(level, 'current', 'plan.level'),
      targetLevel: _requiredString(level, 'target', 'plan.level'),
      levelLabel: _requiredString(level, 'label', 'plan.level'),
      schedule: PlpSchedule.fromJson(_requiredMap(json, 'schedule', 'plan')),
      focusAreas: _requiredStringList(json, 'focus_areas', 'plan'),
      weeks: _requiredMapList(
        json,
        'weeks',
        'plan',
      ).map(PlpWeek.fromJson).toList(growable: false),
    );
  }
}

class PlpSchedule {
  final int durationWeeks;
  final int daysPerWeek;
  final int minutesPerDay;

  const PlpSchedule({
    required this.durationWeeks,
    required this.daysPerWeek,
    required this.minutesPerDay,
  });

  factory PlpSchedule.fromJson(JsonMap json) {
    final result = PlpSchedule(
      durationWeeks: _requiredInt(json, 'duration_weeks', 'plan.schedule'),
      daysPerWeek: _requiredInt(json, 'days_per_week', 'plan.schedule'),
      minutesPerDay: _requiredInt(json, 'minutes_per_day', 'plan.schedule'),
    );
    if (result.durationWeeks <= 0 ||
        result.daysPerWeek < 1 ||
        result.daysPerWeek > 7 ||
        result.minutesPerDay <= 0) {
      throw const PlpFormatException('invalid plan.schedule values');
    }
    return result;
  }
}

class LearnerSnapshot {
  final String nativeLanguage;
  final List<String> learningGoals;
  final List<String> interests;
  final List<String> preferredContexts;
  final List<String> pronunciationPriorities;

  const LearnerSnapshot({
    required this.nativeLanguage,
    required this.learningGoals,
    required this.interests,
    required this.preferredContexts,
    required this.pronunciationPriorities,
  });

  factory LearnerSnapshot.fromJson(JsonMap json) => LearnerSnapshot(
    nativeLanguage: _requiredString(
      json,
      'native_language',
      'learner_snapshot',
    ),
    learningGoals: _requiredStringList(
      json,
      'learning_goals',
      'learner_snapshot',
    ),
    interests: _requiredStringList(json, 'interests', 'learner_snapshot'),
    // These fields remain in stored v1/v2 snapshots, but the shortened
    // onboarding no longer collects either one. New plans legitimately send
    // empty arrays and future payloads may omit them.
    preferredContexts: _optionalStringList(
      json,
      'preferred_contexts',
      'learner_snapshot',
    ),
    pronunciationPriorities: _optionalStringList(
      json,
      'pronunciation_priorities',
      'learner_snapshot',
    ),
  );
}

class PlpWeek {
  final String id;
  final int sequence;
  final String title;
  final String description;
  final List<String> objectives;
  final PlpWeekMission? mission;
  final List<PlpUnit> units;

  const PlpWeek({
    required this.id,
    required this.sequence,
    required this.title,
    required this.description,
    required this.objectives,
    this.mission,
    required this.units,
  });

  factory PlpWeek.fromJson(JsonMap json) {
    return PlpWeek(
      id: _requiredString(json, 'id', 'week'),
      sequence: _requiredInt(json, 'sequence', 'week'),
      title: _requiredString(json, 'title', 'week'),
      description: _requiredString(json, 'description', 'week'),
      objectives: _requiredStringList(json, 'objectives', 'week'),
      mission: json['mission'] == null
          ? null
          : PlpWeekMission.fromJson(_requiredMap(json, 'mission', 'week')),
      units: _requiredMapList(
        json,
        'units',
        'week',
      ).map(PlpUnit.fromJson).toList(growable: false),
    );
  }
}

class PlpWeekMission {
  final String title;
  final String premise;
  final String product;
  final String permittedSupport;
  final String canDo;
  final String goalId;
  final String goalLabel;
  final String interestId;
  final String interestLabel;
  final String scenarioId;
  final String scenarioTitle;

  const PlpWeekMission({
    required this.title,
    required this.premise,
    required this.product,
    required this.permittedSupport,
    required this.canDo,
    required this.goalId,
    required this.goalLabel,
    required this.interestId,
    required this.interestLabel,
    required this.scenarioId,
    required this.scenarioTitle,
  });

  factory PlpWeekMission.fromJson(JsonMap json) {
    const path = 'week.mission';
    final mission = _requiredMap(json, 'mission', path);
    final goal = _requiredMap(json, 'goal', path);
    final interest = _requiredMap(json, 'interest', path);
    final scenario = _requiredMap(json, 'scenario', path);
    return PlpWeekMission(
      title: _requiredString(mission, 'title', '$path.mission'),
      premise: _requiredString(mission, 'premise', '$path.mission'),
      product: _requiredString(mission, 'product', '$path.mission'),
      permittedSupport: _requiredString(
        mission,
        'permitted_support',
        '$path.mission',
      ),
      canDo: _requiredString(json, 'can_do', path),
      goalId: _requiredString(goal, 'id', '$path.goal'),
      goalLabel: _requiredString(goal, 'label', '$path.goal'),
      interestId: _requiredString(interest, 'id', '$path.interest'),
      interestLabel: _requiredString(interest, 'label', '$path.interest'),
      scenarioId: _requiredString(scenario, 'id', '$path.scenario'),
      scenarioTitle: _requiredString(scenario, 'title', '$path.scenario'),
    );
  }
}

class PlpUnit {
  final String id;
  final int sequence;
  final String title;
  final String description;
  final List<String> objectives;
  final List<PlpLesson> lessons;

  const PlpUnit({
    required this.id,
    required this.sequence,
    required this.title,
    required this.description,
    required this.objectives,
    required this.lessons,
  });

  factory PlpUnit.fromJson(JsonMap json) => PlpUnit(
    id: _requiredString(json, 'id', 'unit'),
    sequence: _requiredInt(json, 'sequence', 'unit'),
    title: _requiredString(json, 'title', 'unit'),
    description: _requiredString(json, 'description', 'unit'),
    objectives: _requiredStringList(json, 'objectives', 'unit'),
    lessons: _requiredMapList(
      json,
      'lessons',
      'unit',
    ).map(PlpLesson.fromJson).toList(growable: false),
  );
}

class PlpLesson {
  final String id;
  final int sequence;
  final PlpLessonType type;
  final String title;
  final String description;
  final int estimatedMinutes;
  final int xp;
  final PlpCompletionPolicy completionPolicy;
  final List<String> objectives;
  final List<String> skillIds;
  final List<String> requiredLessonIds;
  final String personalizationReason;
  final String? lessonRole;
  final String? canDoStatement;
  final String? contentInstanceId;
  final LessonGrounding grounding;
  final PlpContentStatus contentStatus;
  final PlpLessonContent? content;

  bool get isReady => contentStatus == PlpContentStatus.ready;

  const PlpLesson({
    required this.id,
    required this.sequence,
    required this.type,
    required this.title,
    required this.description,
    required this.estimatedMinutes,
    required this.xp,
    required this.completionPolicy,
    required this.objectives,
    required this.skillIds,
    required this.requiredLessonIds,
    required this.personalizationReason,
    this.lessonRole,
    this.canDoStatement,
    this.contentInstanceId,
    required this.grounding,
    required this.contentStatus,
    required this.content,
  });

  factory PlpLesson.fromJson(JsonMap json) {
    final path = 'lesson ${json['id'] ?? '<unknown>'}';
    final type = _parseLessonType(_requiredString(json, 'type', path), path);
    final lesson = PlpLesson(
      id: _requiredString(json, 'id', path),
      sequence: _requiredInt(json, 'sequence', path),
      type: type,
      title: _requiredString(json, 'title', path),
      description: _requiredString(json, 'description', path),
      estimatedMinutes: _requiredInt(json, 'estimated_minutes', path),
      xp: _requiredInt(json, 'xp', path),
      completionPolicy: PlpCompletionPolicy.fromJson(
        _requiredMap(json, 'completion_policy', path),
        path,
      ),
      objectives: _requiredStringList(json, 'objectives', path),
      skillIds: _requiredStringList(json, 'skill_ids', path),
      requiredLessonIds: _requiredStringList(
        json,
        'required_lesson_ids',
        path,
        allowEmpty: true,
      ),
      personalizationReason: _requiredString(
        json,
        'personalization_reason',
        path,
      ),
      lessonRole: _optionalString(json, 'lesson_role', path),
      canDoStatement: _optionalString(json, 'can_do_statement', path),
      contentInstanceId: _optionalString(json, 'content_instance_id', path),
      grounding: LessonGrounding.fromJson(
        _requiredMap(json, 'grounding', path),
        path,
      ),
      contentStatus: switch (_optionalString(json, 'content_status', path)) {
        null || 'ready' => PlpContentStatus.ready,
        'pending' => PlpContentStatus.pending,
        'failed' => PlpContentStatus.failed,
        final value => throw PlpFormatException(
          '$path has unknown content_status $value',
        ),
      },
      content: json['content'] == null
          ? null
          : PlpLessonContent.fromJson(
              _requiredMap(json, 'content', path),
              path,
            ),
    );
    if (lesson.sequence <= 0 || lesson.estimatedMinutes <= 0 || lesson.xp < 0) {
      throw PlpFormatException('$path has invalid numeric metadata');
    }
    if (lesson.isReady != (lesson.content != null)) {
      throw PlpFormatException(
        '$path ready content status must exactly match content presence',
      );
    }
    if ((lesson.type == PlpLessonType.assessment) !=
        (lesson.completionPolicy.mode == PlpCompletionMode.minimumScore)) {
      throw PlpFormatException(
        '$path assessments must use minimum_score completion and teaching '
        'lessons must use required_activities completion',
      );
    }
    return lesson;
  }
}

class PlpCompletionPolicy {
  final PlpCompletionMode mode;
  final int? minimumScore;

  const PlpCompletionPolicy({required this.mode, required this.minimumScore});

  factory PlpCompletionPolicy.fromJson(JsonMap json, String parentPath) {
    final path = '$parentPath.completion_policy';
    final modeText = _requiredString(json, 'mode', path);
    final mode = switch (modeText) {
      'finish' || 'required_activities' => PlpCompletionMode.requiredActivities,
      'minimum_score' => PlpCompletionMode.minimumScore,
      _ => throw PlpFormatException('$path has unknown mode $modeText'),
    };
    final minimumScore = _optionalInt(json, 'minimum_score', path);
    if (mode == PlpCompletionMode.minimumScore &&
        (minimumScore == null || minimumScore < 1 || minimumScore > 100)) {
      throw PlpFormatException(
        '$path minimum_score mode requires a score from 1 to 100',
      );
    }
    if (mode == PlpCompletionMode.requiredActivities && minimumScore != null) {
      throw PlpFormatException(
        '$path required_activities mode must not define minimum_score',
      );
    }
    return PlpCompletionPolicy(mode: mode, minimumScore: minimumScore);
  }

  bool isSatisfiedBy(int score) => switch (mode) {
    PlpCompletionMode.requiredActivities => true,
    PlpCompletionMode.minimumScore => score >= minimumScore!,
  };
}

class LessonGrounding {
  final String origin;
  final String reviewStatus;
  final List<String> retrievalTags;
  final List<String> sourceRefs;

  const LessonGrounding({
    required this.origin,
    required this.reviewStatus,
    required this.retrievalTags,
    required this.sourceRefs,
  });

  factory LessonGrounding.fromJson(JsonMap json, String parentPath) {
    final path = '$parentPath.grounding';
    return LessonGrounding(
      origin: _requiredString(json, 'origin', path),
      reviewStatus: _requiredString(json, 'review_status', path),
      retrievalTags: _requiredStringList(json, 'retrieval_tags', path),
      sourceRefs: _requiredStringList(
        json,
        'source_refs',
        path,
        allowEmpty: true,
      ),
    );
  }
}

class PlpLessonContent {
  final String intro;
  final List<PlpActivity> activities;

  const PlpLessonContent({required this.intro, required this.activities});

  factory PlpLessonContent.fromJson(JsonMap json, String parentPath) {
    final path = '$parentPath.content';
    final result = PlpLessonContent(
      intro: _requiredString(json, 'intro', path),
      activities: _requiredMapList(
        json,
        'activities',
        path,
      ).map((item) => PlpActivity.fromJson(item, path)).toList(growable: false),
    );
    if (result.activities.isEmpty) {
      throw PlpFormatException('$path.activities must not be empty');
    }
    return result;
  }
}

class PlpActivity {
  final String id;
  final PlpActivityType type;
  final PlpActivityPhase phase;
  final bool required;
  final List<String> sourceRefs;
  final List<String> skillIds;
  final JsonMap data;

  PlpActivity({
    required this.id,
    required this.type,
    this.phase = PlpActivityPhase.unspecified,
    required this.required,
    required this.sourceRefs,
    List<String> skillIds = const [],
    required JsonMap data,
  }) : skillIds = List.unmodifiable(skillIds),
       data = UnmodifiableMapView(data);

  bool get isQuestion =>
      type == PlpActivityType.multipleChoice ||
      type == PlpActivityType.fillBlank ||
      type == PlpActivityType.readingComprehension ||
      type == PlpActivityType.listeningComprehension ||
      type == PlpActivityType.sentenceOrder;

  factory PlpActivity.fromJson(JsonMap json, String parentPath) {
    final id = _requiredString(json, 'id', '$parentPath.activity');
    final path = '$parentPath.activity $id';
    final type = _parseActivityType(_requiredString(json, 'type', path), path);
    final phase = _parseActivityPhase(
      _optionalString(json, 'phase', path),
      path,
    );
    final sourceRefs = _optionalStringList(json, 'source_refs', path);
    final skillIds = _optionalStringList(json, 'skill_ids', path);
    final required = json['required'] == null
        ? true
        : _requiredBool(json, 'required', path);
    final data = json['data'] is Map<String, dynamic>
        ? Map<String, dynamic>.from(json['data'] as Map<String, dynamic>)
        : (Map<String, dynamic>.from(json)
            ..remove('id')
            ..remove('type')
            ..remove('phase')
            ..remove('required')
            ..remove('source_refs')
            ..remove('skill_ids'));
    _validateActivity(type, data, path);
    return PlpActivity(
      id: id,
      type: type,
      phase: phase,
      required: required,
      sourceRefs: sourceRefs,
      skillIds: skillIds,
      data: data,
    );
  }
}

enum StoredLessonStatus { inProgress, completed }

class LessonProgress {
  final StoredLessonStatus status;
  final double progressFraction;
  final int? bestScore;
  final int attempts;
  final List<String> completedActivityIds;
  final DateTime? completedAt;

  const LessonProgress({
    required this.status,
    required this.progressFraction,
    required this.bestScore,
    required this.attempts,
    this.completedActivityIds = const [],
    required this.completedAt,
  });

  factory LessonProgress.fromJson(JsonMap json, String lessonId) {
    final path = 'progress.lesson_states.$lessonId';
    final statusText = _requiredString(json, 'status', path);
    final status = switch (statusText) {
      'in_progress' => StoredLessonStatus.inProgress,
      'completed' => StoredLessonStatus.completed,
      _ => throw PlpFormatException('$path has unknown status $statusText'),
    };
    final fraction = _requiredNumber(
      json,
      'progress_fraction',
      path,
    ).toDouble();
    final bestScore = _optionalInt(json, 'best_score', path);
    final attempts = _requiredInt(json, 'attempts', path);
    final completedActivityIds = _optionalStringList(
      json,
      'completed_activity_ids',
      path,
    );
    final completedAtText = _optionalString(json, 'completed_at', path);
    final completedAt = completedAtText == null
        ? null
        : DateTime.tryParse(completedAtText);
    if (fraction < 0 ||
        fraction > 1 ||
        attempts < 0 ||
        (bestScore != null && (bestScore < 0 || bestScore > 100)) ||
        (completedAtText != null && completedAt == null)) {
      throw PlpFormatException('$path contains invalid progress values');
    }
    if (status == StoredLessonStatus.completed && fraction != 1) {
      throw PlpFormatException('$path completed progress must equal 1');
    }
    if (status == StoredLessonStatus.completed &&
        (bestScore == null || attempts < 1 || completedAt == null)) {
      throw PlpFormatException(
        '$path completed progress requires a score, attempt, and timestamp',
      );
    }
    if (status == StoredLessonStatus.inProgress &&
        (fraction >= 1 || completedAt != null)) {
      throw PlpFormatException('$path in-progress state cannot be complete');
    }
    return LessonProgress(
      status: status,
      progressFraction: fraction,
      bestScore: bestScore,
      attempts: attempts,
      completedActivityIds: completedActivityIds,
      completedAt: completedAt,
    );
  }
}

class PlpProgress {
  final String? currentLessonId;
  final int currentStreakDays;
  final int longestStreakDays;
  final int weeklyGoalDays;
  final List<DateTime> studiedDatesThisWeek;
  final Map<String, LessonProgress> lessonStates;

  PlpProgress({
    required this.currentLessonId,
    required this.currentStreakDays,
    required this.longestStreakDays,
    required this.weeklyGoalDays,
    required this.studiedDatesThisWeek,
    required Map<String, LessonProgress> lessonStates,
  }) : lessonStates = UnmodifiableMapView(lessonStates);

  factory PlpProgress.fromJson(JsonMap json) {
    final rawStates = _requiredMap(json, 'lesson_states', 'progress');
    final states = <String, LessonProgress>{};
    for (final entry in rawStates.entries) {
      if (entry.value is! Map<String, dynamic>) {
        throw PlpFormatException(
          'progress.lesson_states.${entry.key} must be an object',
        );
      }
      states[entry.key] = LessonProgress.fromJson(
        entry.value as JsonMap,
        entry.key,
      );
    }
    final studiedDates =
        _requiredStringList(
              json,
              'studied_dates_this_week',
              'progress',
              allowEmpty: true,
            )
            .map((value) {
              final parsed = DateTime.tryParse(value);
              if (parsed == null) {
                throw PlpFormatException('invalid studied date $value');
              }
              return parsed;
            })
            .toList(growable: false);
    final result = PlpProgress(
      currentLessonId: _optionalString(json, 'current_lesson_id', 'progress'),
      currentStreakDays: _requiredInt(json, 'current_streak_days', 'progress'),
      longestStreakDays: _requiredInt(json, 'longest_streak_days', 'progress'),
      weeklyGoalDays: _requiredInt(json, 'weekly_goal_days', 'progress'),
      studiedDatesThisWeek: studiedDates,
      lessonStates: states,
    );
    if (result.currentStreakDays < 0 ||
        result.longestStreakDays < result.currentStreakDays ||
        result.weeklyGoalDays < 1 ||
        result.weeklyGoalDays > 7 ||
        result.studiedDatesThisWeek.length > 7) {
      throw const PlpFormatException(
        'progress contains invalid summary values',
      );
    }
    return result;
  }

  PlpProgress copyWith({
    String? currentLessonId,
    Map<String, LessonProgress>? lessonStates,
  }) => PlpProgress(
    currentLessonId: currentLessonId,
    currentStreakDays: currentStreakDays,
    longestStreakDays: longestStreakDays,
    weeklyGoalDays: weeklyGoalDays,
    studiedDatesThisWeek: studiedDatesThisWeek,
    lessonStates: lessonStates ?? this.lessonStates,
  );
}

PlpLessonType _parseLessonType(String value, String path) => switch (value) {
  'vocabulary' => PlpLessonType.vocabulary,
  'grammar' => PlpLessonType.grammar,
  'pronunciation' => PlpLessonType.pronunciation,
  'reading' => PlpLessonType.reading,
  'listening' => PlpLessonType.listening,
  'speaking' => PlpLessonType.speaking,
  'discourse' => PlpLessonType.discourse,
  'assessment' => PlpLessonType.assessment,
  _ => throw PlpFormatException('$path has unsupported lesson type $value'),
};

PlpActivityType _parseActivityType(String value, String path) =>
    switch (value) {
      'vocabulary_card' => PlpActivityType.vocabularyCard,
      'concept' => PlpActivityType.concept,
      'pronunciation_drill' => PlpActivityType.pronunciationDrill,
      'multiple_choice' => PlpActivityType.multipleChoice,
      'fill_blank' => PlpActivityType.fillBlank,
      'reading_comprehension' => PlpActivityType.readingComprehension,
      'listening_comprehension' => PlpActivityType.listeningComprehension,
      'sentence_order' => PlpActivityType.sentenceOrder,
      'guided_speaking' => PlpActivityType.guidedSpeaking,
      _ => throw PlpFormatException(
        '$path has unsupported activity type $value',
      ),
    };

PlpActivityPhase _parseActivityPhase(String? value, String path) =>
    switch (value) {
      null => PlpActivityPhase.unspecified,
      'learn' => PlpActivityPhase.learn,
      'guided_practice' => PlpActivityPhase.guidedPractice,
      'independent_check' => PlpActivityPhase.independentCheck,
      'review' => PlpActivityPhase.review,
      _ => throw PlpFormatException(
        '$path has unsupported activity phase $value',
      ),
    };

void _validateActivity(PlpActivityType type, JsonMap data, String path) {
  switch (type) {
    case PlpActivityType.vocabularyCard:
      _requiredString(data, 'word', path);
      _requiredString(data, 'part_of_speech', path);
      _requiredString(data, 'ipa', path);
      _requiredString(data, 'definition', path);
      _requiredStringList(data, 'examples', path);
      _requiredStringList(data, 'collocations', path, allowEmpty: true);
    case PlpActivityType.concept:
      _optionalString(data, 'title', path);
      _requiredString(data, 'explanation', path);
      _requiredStringList(data, 'key_points', path);
      _requiredStringList(data, 'examples', path);
    case PlpActivityType.pronunciationDrill:
      if (data['title'] == null && data['sound_label'] == null) {
        throw PlpFormatException('$path needs title or sound_label');
      }
      if (data['target_ipa'] == null && data['ipa'] == null) {
        throw PlpFormatException('$path needs target_ipa or ipa');
      }
      _requiredString(data, 'instructions', path);
      _requiredStringList(data, 'tips', path);
      final rawItems = data['practice_items'];
      if (rawItems is! List || rawItems.length < 2) {
        throw PlpFormatException(
          '$path.practice_items must have 2 or more items',
        );
      }
    case PlpActivityType.multipleChoice:
      _requiredString(data, 'prompt', path);
      final options = _requiredMapList(data, 'options', path);
      if (options.length < 2) {
        throw PlpFormatException('$path.options must contain at least 2 items');
      }
      final optionIds = <String>{};
      for (final option in options) {
        final optionId = _requiredString(option, 'id', '$path.options');
        _requiredString(option, 'text', '$path.options');
        if (!optionIds.add(optionId)) {
          throw PlpFormatException(
            '$path contains duplicate option id $optionId',
          );
        }
      }
      final correctId = _optionalString(data, 'correct_option_id', path);
      if (correctId != null && !optionIds.contains(correctId)) {
        throw PlpFormatException('$path.correct_option_id is not an option');
      }
      _requiredString(data, 'explanation', path);
    case PlpActivityType.fillBlank:
      _requiredString(data, 'prompt', path);
      if (data.containsKey('accepted_answers')) {
        _requiredStringList(data, 'accepted_answers', path);
      }
      _requiredString(data, 'explanation', path);
    case PlpActivityType.readingComprehension:
      _requiredString(data, 'title', path);
      _requiredString(data, 'passage', path);
      _validateNestedQuestion(data, path);
    case PlpActivityType.listeningComprehension:
      _requiredString(data, 'title', path);
      _validateNestedQuestion(data, path);
    case PlpActivityType.sentenceOrder:
      _requiredString(data, 'prompt', path);
      final tokens = _requiredMapList(data, 'tokens', path);
      if (tokens.length < 2) {
        throw PlpFormatException('$path.tokens must contain at least 2 items');
      }
      for (final token in tokens) {
        _requiredString(token, 'id', '$path.tokens');
        _requiredString(token, 'text', '$path.tokens');
      }
      _requiredString(data, 'explanation', path);
    case PlpActivityType.guidedSpeaking:
      _requiredString(data, 'prompt', path);
      _requiredStringList(data, 'target_expressions', path);
      _requiredString(data, 'preparation_tip', path);
      _requiredInt(data, 'minimum_seconds', path);
  }
}

void _validateNestedQuestion(JsonMap data, String path) {
  final question = _requiredMap(data, 'question', path);
  _requiredString(question, 'prompt', '$path.question');
  final options = _requiredMapList(question, 'options', '$path.question');
  if (options.length < 2) {
    throw PlpFormatException('$path.question.options needs at least 2 items');
  }
  for (final option in options) {
    _requiredString(option, 'id', '$path.question.options');
    _requiredString(option, 'text', '$path.question.options');
  }
  _requiredString(question, 'explanation', '$path.question');
}

void _addUniqueId(Set<String> ids, String id, String kind) {
  if (!ids.add(id)) {
    throw PlpFormatException('duplicate $kind id $id');
  }
}

String _requiredString(JsonMap json, String key, String path) {
  final value = json[key];
  if (value is! String || value.trim().isEmpty) {
    throw PlpFormatException('$path.$key must be a non-empty string');
  }
  return value.trim();
}

String? _optionalString(JsonMap json, String key, String path) {
  final value = json[key];
  if (value == null) return null;
  if (value is! String || value.trim().isEmpty) {
    throw PlpFormatException('$path.$key must be null or a non-empty string');
  }
  return value.trim();
}

int _requiredInt(JsonMap json, String key, String path) {
  final value = json[key];
  if (value is! int) {
    throw PlpFormatException('$path.$key must be an integer');
  }
  return value;
}

int? _optionalInt(JsonMap json, String key, String path) {
  final value = json[key];
  if (value == null) return null;
  if (value is! int) {
    throw PlpFormatException('$path.$key must be null or an integer');
  }
  return value;
}

bool _requiredBool(JsonMap json, String key, String path) {
  final value = json[key];
  if (value is! bool) {
    throw PlpFormatException('$path.$key must be a boolean');
  }
  return value;
}

num _requiredNumber(JsonMap json, String key, String path) {
  final value = json[key];
  if (value is! num) {
    throw PlpFormatException('$path.$key must be numeric');
  }
  return value;
}

JsonMap _requiredMap(JsonMap json, String key, String path) {
  final value = json[key];
  if (value is! Map<String, dynamic>) {
    throw PlpFormatException('$path.$key must be an object');
  }
  return value;
}

List<JsonMap> _requiredMapList(JsonMap json, String key, String path) {
  final value = json[key];
  if (value is! List) {
    throw PlpFormatException('$path.$key must be an array');
  }
  final result = <JsonMap>[];
  for (final item in value) {
    if (item is! Map<String, dynamic>) {
      throw PlpFormatException('$path.$key must contain only objects');
    }
    result.add(item);
  }
  return result;
}

List<String> _requiredStringList(
  JsonMap json,
  String key,
  String path, {
  bool allowEmpty = false,
}) {
  final value = json[key];
  if (value is! List || value.any((item) => item is! String)) {
    throw PlpFormatException('$path.$key must be an array of strings');
  }
  final result = value
      .cast<String>()
      .map((item) => item.trim())
      .toList(growable: false);
  if (result.any((item) => item.isEmpty) || (!allowEmpty && result.isEmpty)) {
    throw PlpFormatException('$path.$key contains no usable values');
  }
  return result;
}

List<String> _optionalStringList(JsonMap json, String key, String path) {
  if (!json.containsKey(key)) return const [];
  return _requiredStringList(json, key, path, allowEmpty: true);
}
