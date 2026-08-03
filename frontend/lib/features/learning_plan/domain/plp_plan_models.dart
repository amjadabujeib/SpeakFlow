part of 'plp_models.dart';

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
    // The shortened onboarding no longer collects these optional preferences.
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
