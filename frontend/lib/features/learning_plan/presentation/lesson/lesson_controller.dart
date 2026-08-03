part of 'lesson_screens.dart';

extension _LessonController on _InteractiveLessonScreenState {
  Future<void> _checkCurrentAnswer() async {
    final activity = _currentActivity;
    if (activity == null || !activity.isQuestion) return;
    if (!_hasCompleteAnswer(activity)) return;
    final answer = _answers[activity.id]?.trim();
    final ordered = _orderedAnswers[activity.id];

    bool isCorrect;
    String explanation;
    if (widget.submitAttempt case final submit?) {
      final payload = <String, dynamic>{};
      if (activity.type == PlpActivityType.multipleChoice ||
          activity.type == PlpActivityType.readingComprehension ||
          activity.type == PlpActivityType.listeningComprehension) {
        payload['selected_option_id'] = answer;
      } else if (activity.type == PlpActivityType.fillBlank) {
        payload['text_answer'] = answer;
      } else if (activity.type == PlpActivityType.sentenceOrder) {
        payload['ordered_token_ids'] = ordered;
      }
      payload['attempt_kind'] = _reviewingMistakes ? 'correction' : 'initial';
      payload['attempt_session_id'] = _attemptSessionId;
      payload['timezone_offset_minutes'] =
          DateTime.now().timeZoneOffset.inMinutes;
      payload['submission_id'] = _submissionIdFor(activity.id, payload);
      final result = await _submitRemote(submit, activity.id, payload);
      if (result == null) return;
      _recordServerLessonResult(result);
      isCorrect = result.correct ?? result.score >= 70;
      explanation = result.explanation;
      if (result.correctResponse case final response?) {
        _serverCorrectResponses[activity.id] = response;
      }
      _submittedActivityIds.add(activity.id);
    } else {
      isCorrect = switch (activity.type) {
        PlpActivityType.multipleChoice =>
          answer == activity.data['correct_option_id'],
        PlpActivityType.fillBlank =>
          (activity.data['accepted_answers'] as List)
              .cast<String>()
              .map(_normalizeAnswer)
              .contains(_normalizeAnswer(answer!)),
        _ => false,
      };
      explanation = activity.data['explanation']?.toString() ?? '';
    }
    _update(() {
      if (!_reviewingMistakes && !_initialQuestionIds.contains(activity.id)) {
        _initialQuestionIds.add(activity.id);
        if (isCorrect) _initialCorrectQuestionIds.add(activity.id);
      }
      _checkedQuestionIds.add(activity.id);
      if (isCorrect) {
        _correctQuestionIds.add(activity.id);
        if (_reviewingMistakes) _correctedQuestionIds.add(activity.id);
      } else {
        _correctQuestionIds.remove(activity.id);
        if (_reviewingMistakes) _correctedQuestionIds.remove(activity.id);
      }
      _serverExplanations[activity.id] = explanation;
    });
  }

  bool _hasCompleteAnswer(PlpActivity activity) {
    if (activity.type != PlpActivityType.sentenceOrder) {
      return _answers[activity.id]?.trim().isNotEmpty ?? false;
    }
    final tokens = (activity.data['tokens'] as List)
        .cast<JsonMap>()
        .map((token) => token['id'] as String)
        .toSet();
    final selected = _orderedAnswers[activity.id] ?? const <String>[];
    return selected.length == tokens.length &&
        selected.toSet().length == tokens.length &&
        selected.every(tokens.contains);
  }

  String _normalizeAnswer(String value) => value
      .trim()
      .toLowerCase()
      .replaceAll(RegExp(r'\s+'), ' ')
      .replaceAll('’', "'");

  Future<void> _continue() async {
    final activity = _currentActivity;
    final submit = widget.submitAttempt;
    if (activity != null &&
        !_submittedActivityIds.contains(activity.id) &&
        submit != null) {
      final payload = <String, dynamic>{
        'attempt_kind': _reviewingMistakes ? 'correction' : 'initial',
        'attempt_session_id': _attemptSessionId,
        'timezone_offset_minutes': DateTime.now().timeZoneOffset.inMinutes,
      };
      if (activity.type == PlpActivityType.guidedSpeaking) {
        final speaking = _guidedSpeakingResults[activity.id];
        if (speaking == null) return;
        payload['transcript'] = speaking['transcript'];
        payload['duration_seconds'] = speaking['duration_seconds'];
      }
      payload['submission_id'] = _submissionIdFor(activity.id, payload);
      final result = await _submitRemote(submit, activity.id, payload);
      if (result == null) return;
      _recordServerLessonResult(result);
      _submittedActivityIds.add(activity.id);
      _serverExplanations[activity.id] = result.explanation;
      if (result.correctResponse case final response?) {
        _serverCorrectResponses[activity.id] = response;
      }
    }
    if (_reviewingMistakes) {
      if (_reviewPageCursor < _reviewPageIndexes.length - 1) {
        _reviewPageCursor += 1;
        _pageController.animateToPage(
          _reviewPageIndexes[_reviewPageCursor],
          duration: const Duration(milliseconds: 280),
          curve: Curves.easeOut,
        );
      } else {
        _update(() {
          _reviewingMistakes = false;
          _showCompletion = true;
        });
      }
      return;
    }
    if (_currentPage < _pageCount - 1) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 280),
        curve: Curves.easeOut,
      );
      return;
    }
    _update(() => _showCompletion = true);
  }

  void _recordServerLessonResult(PlpAttemptResult result) {
    if (result.lessonScore case final score?) {
      _serverLessonScore = score;
    }
    _serverLessonCompleted = result.lessonCompleted;
    _serverNewlyCompleted = _serverNewlyCompleted || result.newlyCompleted;
    if (result.xpAwarded > _serverXpAwarded) {
      _serverXpAwarded = result.xpAwarded;
    }
  }

  String _submissionIdFor(String activityId, JsonMap payload) {
    final response = <String, dynamic>{
      for (final key in const [
        'selected_option_id',
        'text_answer',
        'ordered_token_ids',
        'transcript',
        'duration_seconds',
      ])
        if (payload.containsKey(key)) key: payload[key],
    };
    var fingerprint = 0x811c9dc5;
    for (final byte in utf8.encode(jsonEncode(response))) {
      fingerprint ^= byte;
      fingerprint = (fingerprint * 0x01000193) & 0xffffffff;
    }
    final kind = payload['attempt_kind'] as String;
    final suffix = fingerprint.toRadixString(16).padLeft(8, '0');
    return '${_attemptSessionId}_${activityId}_${kind}_$suffix';
  }

  void _startMistakeReview() {
    final pages = <int>[];
    for (var index = 0; index < _activities.length; index++) {
      final activity = _activities[index];
      if (activity.required &&
          activity.isQuestion &&
          !_initialCorrectQuestionIds.contains(activity.id) &&
          !_correctedQuestionIds.contains(activity.id)) {
        pages.add(index + 1);
        _checkedQuestionIds.remove(activity.id);
        _correctQuestionIds.remove(activity.id);
        _answers.remove(activity.id);
        _orderedAnswers[activity.id]?.clear();
        _serverCorrectResponses.remove(activity.id);
        _serverExplanations.remove(activity.id);
        _textControllers[activity.id]?.clear();
      }
    }
    if (pages.isEmpty) return;
    _update(() {
      _reviewPageIndexes = pages;
      _reviewPageCursor = 0;
      _reviewingMistakes = true;
      _showCompletion = false;
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _pageController.hasClients) {
        _pageController.jumpToPage(pages.first);
      }
    });
  }

  Future<PlpAttemptResult?> _submitRemote(
    Future<PlpAttemptResult> Function(String, JsonMap) submit,
    String activityId,
    JsonMap payload,
  ) async {
    if (_submitting) return null;
    _update(() => _submitting = true);
    try {
      return await submit(activityId, payload);
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not save this activity: $error')),
        );
      }
      return null;
    } finally {
      if (mounted) _update(() => _submitting = false);
    }
  }
}
