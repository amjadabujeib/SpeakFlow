part of 'plp_models.dart';

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
