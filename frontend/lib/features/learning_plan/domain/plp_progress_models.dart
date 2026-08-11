part of 'plp_models.dart';

enum StoredLessonStatus { inProgress, completed }

class PronunciationActivityProgress {
  final Set<String> verifiedTargetKeys;
  final Set<String> unverifiedTargetKeys;

  const PronunciationActivityProgress({
    this.verifiedTargetKeys = const {},
    this.unverifiedTargetKeys = const {},
  });

  factory PronunciationActivityProgress.fromJson(JsonMap json, String path) =>
      PronunciationActivityProgress(
        verifiedTargetKeys: _optionalStringList(
          json,
          'verified_target_keys',
          path,
        ).toSet(),
        unverifiedTargetKeys: _optionalStringList(
          json,
          'unverified_target_keys',
          path,
        ).toSet(),
      );
}

class LessonProgress {
  final StoredLessonStatus status;
  final double progressFraction;
  final int? bestScore;
  final int attempts;
  final List<String> completedActivityIds;
  final Map<String, PronunciationActivityProgress>
  pronunciationActivityProgress;
  final DateTime? completedAt;

  const LessonProgress({
    required this.status,
    required this.progressFraction,
    required this.bestScore,
    required this.attempts,
    this.completedActivityIds = const [],
    this.pronunciationActivityProgress = const {},
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
    final rawPronunciationProgress = json['pronunciation_activity_progress'];
    if (rawPronunciationProgress != null && rawPronunciationProgress is! Map) {
      throw PlpFormatException(
        '$path.pronunciation_activity_progress must be an object',
      );
    }
    final pronunciationActivityProgress =
        <String, PronunciationActivityProgress>{};
    for (final entry
        in (rawPronunciationProgress as Map? ?? const {}).entries) {
      if (entry.value is! Map) {
        throw PlpFormatException(
          '$path.pronunciation_activity_progress.${entry.key} must be an object',
        );
      }
      pronunciationActivityProgress[entry.key
          .toString()] = PronunciationActivityProgress.fromJson(
        Map<String, dynamic>.from(entry.value as Map),
        '$path.pronunciation_activity_progress.${entry.key}',
      );
    }
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
      pronunciationActivityProgress: pronunciationActivityProgress,
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
