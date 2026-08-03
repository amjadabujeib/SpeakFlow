part of 'lesson_screens.dart';

extension _LessonCompletionWidgets on _InteractiveLessonScreenState {
  Widget _buildGuidedSpeaking(PlpActivity activity) {
    final data = activity.data;
    final expressions = (data['target_expressions'] as List).cast<String>();
    final result = _guidedSpeakingResults[activity.id];
    return _activityPage(
      activity: activity,
      children: [
        const Text(
          'Guided speaking',
          style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
        ),
        const SizedBox(height: 10),
        Text(
          data['prompt'] as String,
          style: const TextStyle(fontSize: 25, fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 16),
        _InfoPanel(
          color: _themeColor,
          icon: Icons.lightbulb_outline,
          title: 'Prepare',
          children: [data['preparation_tip'] as String],
        ),
        const SizedBox(height: 16),
        const _SectionTitle('Try to use'),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          children: expressions.map((item) => Chip(label: Text(item))).toList(),
        ),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: _submitting ? null : () => _recordGuidedSpeaking(activity),
          icon: Icon(result == null ? Icons.mic_rounded : Icons.replay_rounded),
          label: Text(result == null ? 'RECORD YOUR RESPONSE' : 'RECORD AGAIN'),
        ),
        if (result != null) ...[
          const SizedBox(height: 14),
          _InfoPanel(
            color: AppColors.success,
            icon: Icons.check_circle_outline,
            title: 'Recorded response',
            children: [
              '${result['duration_seconds']} seconds',
              result['transcript']?.toString() ?? '',
            ],
          ),
        ],
        const SizedBox(height: 12),
        const Text(
          'This checks participation and use of the target language. It is not '
          'an acoustic pronunciation grade.',
          style: TextStyle(color: AppColors.textSecondary, height: 1.4),
        ),
      ],
    );
  }

  Future<void> _recordGuidedSpeaking(PlpActivity activity) async {
    final result = await Navigator.push<JsonMap>(
      context,
      MaterialPageRoute(
        builder: (_) => _GuidedSpeakingPracticePage(
          prompt: activity.data['prompt'] as String,
          minimumSeconds: activity.data['minimum_seconds'] as int,
        ),
      ),
    );
    if (!mounted || result == null) return;
    _update(() => _guidedSpeakingResults[activity.id] = result);
  }

  Widget _buildBottomBar() {
    final activity = _currentActivity;
    final isQuestion = activity?.isQuestion ?? false;
    final isChecked =
        activity != null && _checkedQuestionIds.contains(activity.id);
    final hasAnswer = activity != null && _hasCompleteAnswer(activity);
    final needsCheck = isQuestion && !isChecked;
    final needsPronunciationPass =
        activity?.type == PlpActivityType.pronunciationDrill &&
        widget.submitAttempt != null &&
        !_submittedActivityIds.contains(activity!.id);
    final needsGuidedSpeaking =
        activity?.type == PlpActivityType.guidedSpeaking &&
        widget.submitAttempt != null &&
        !_submittedActivityIds.contains(activity!.id) &&
        !_guidedSpeakingResults.containsKey(activity.id);
    final enabled =
        !_submitting &&
        !needsPronunciationPass &&
        !needsGuidedSpeaking &&
        (!needsCheck || hasAnswer);
    final buttonLabel = needsPronunciationPass
        ? 'PASS ALL SOUND CHECKS TO CONTINUE'
        : needsGuidedSpeaking
        ? 'RECORD YOUR RESPONSE TO CONTINUE'
        : needsCheck
        ? 'CHECK ANSWER'
        : _reviewingMistakes &&
              _reviewPageCursor == _reviewPageIndexes.length - 1
        ? 'FINISH REVIEW'
        : _currentPage == _pageCount - 1
        ? 'FINISH LESSON'
        : 'CONTINUE';

    return Container(
      padding: const EdgeInsets.fromLTRB(18, 12, 18, 16),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(top: BorderSide(color: AppColors.border)),
      ),
      child: SafeArea(
        top: false,
        child: Row(
          children: [
            if (_currentPage > 0 && !isChecked && !_reviewingMistakes)
              TextButton(
                onPressed: () => _pageController.previousPage(
                  duration: const Duration(milliseconds: 250),
                  curve: Curves.easeOut,
                ),
                child: const Text('BACK'),
              )
            else
              const SizedBox(width: 70),
            const SizedBox(width: 10),
            Expanded(
              child: SizedBox(
                height: 54,
                child: FilledButton(
                  onPressed: enabled
                      ? (needsCheck ? _checkCurrentAnswer : _continue)
                      : null,
                  style: FilledButton.styleFrom(
                    backgroundColor: _themeColor,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(15),
                    ),
                  ),
                  child: _submitting
                      ? const SizedBox.square(
                          dimension: 22,
                          child: CircularProgressIndicator(
                            strokeWidth: 2.5,
                            color: Colors.white,
                          ),
                        )
                      : Text(
                          buttonLabel,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w900,
                            letterSpacing: 0.5,
                          ),
                        ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCompletion() {
    final usesServerResult = widget.submitAttempt != null;
    final localFirstTryScore = _questionCount > 0
        ? ((_initialCorrectQuestionCount / _questionCount) * 100).round()
        : null;
    final score = usesServerResult ? _serverLessonScore : localFirstTryScore;
    final passed = usesServerResult
        ? _serverLessonCompleted
        : widget.lesson.completionPolicy.isSatisfiedBy(localFirstTryScore ?? 0);
    final newlyCompleted = usesServerResult ? _serverNewlyCompleted : passed;
    final xpAwarded = usesServerResult
        ? (newlyCompleted ? _serverXpAwarded : 0)
        : (passed ? widget.lesson.xp : 0);
    final hasScore = score != null;
    final initialMistakes = _questionCount - _initialCorrectQuestionCount;
    final correctedMistakes = _correctedQuestionIds
        .where(
          (id) =>
              _scoredQuestionIds.contains(id) &&
              !_initialCorrectQuestionIds.contains(id),
        )
        .length;
    final remainingMistakes = initialMistakes > correctedMistakes
        ? initialMistakes - correctedMistakes
        : 0;
    final canReviewMistakes =
        _questionCount > 0 &&
        widget.lesson.type != PlpLessonType.assessment &&
        remainingMistakes > 0;
    final completionTitle = !passed
        ? widget.lesson.type == PlpLessonType.assessment
              ? 'Checkpoint not passed yet'
              : 'Lesson not complete yet'
        : !hasScore
        ? newlyCompleted
              ? 'Activities complete'
              : 'Activities reviewed'
        : newlyCompleted
        ? 'Lesson complete'
        : 'Lesson reviewed';
    final completionMessage = !passed
        ? widget.lesson.type == PlpLessonType.assessment
              ? score == null
                    ? 'The checkpoint remains open because no aggregate score '
                          'was returned. Review the activities and try again.'
                    : 'Your lesson score is $score%. You need '
                          '${widget.lesson.completionPolicy.minimumScore}% to '
                          'unlock the next lesson.'
              : 'The lesson is not yet marked complete. Return to the plan and '
                    'retry any unfinished required activity.'
        : !hasScore
        ? 'You completed every required activity. This lesson did not include '
              'a scored check.'
        : _questionCount == 0
        ? 'Your lesson result was recorded.'
        : initialMistakes == 0
        ? 'You retrieved every answer correctly on the first try.'
        : correctedMistakes == initialMistakes
        ? 'You corrected every missed item. The checkpoint will test this '
              'material again later.'
        : canReviewMistakes
        ? 'First try: $_initialCorrectQuestionCount of $_questionCount correct. '
              'Correct the missed items now; the checkpoint will test them '
              'again later.'
        : 'You answered $_initialCorrectQuestionCount of $_questionCount '
              'correctly. Review the feedback, then retry the full checkpoint.';
    final minimumScore = widget.lesson.completionPolicy.minimumScore;
    final resultLabel = score == null
        ? passed
              ? xpAwarded > 0
                    ? 'Completion recorded  •  +$xpAwarded XP'
                    : 'Completion recorded'
              : 'Completion not confirmed'
        : passed
        ? xpAwarded > 0
              ? 'Score $score%  •  +$xpAwarded XP'
              : 'Score $score%'
        : minimumScore == null
        ? 'Score $score%'
        : 'Score $score%  •  Need $minimumScore%';
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Spacer(),
              Icon(
                !passed
                    ? Icons.refresh_rounded
                    : !hasScore
                    ? Icons.task_alt
                    : newlyCompleted
                    ? Icons.emoji_events
                    : Icons.check_circle_outline,
                color: _themeColor,
                size: 104,
              ),
              const SizedBox(height: 24),
              Text(
                completionTitle,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 34,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                completionMessage,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: AppColors.textSecondary,
                  fontSize: 18,
                ),
              ),
              const SizedBox(height: 24),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 24,
                  vertical: 14,
                ),
                decoration: BoxDecoration(
                  color: AppColors.surfaceCard,
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(
                    color: _themeColor.withValues(alpha: 0.42),
                  ),
                ),
                child: Text(
                  resultLabel,
                  style: TextStyle(
                    color: _themeColor,
                    fontSize: 20,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              if (correctedMistakes > 0) ...[
                const SizedBox(height: 12),
                Text(
                  'Corrected after feedback: $correctedMistakes of $initialMistakes',
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
              const Spacer(),
              if (canReviewMistakes) ...[
                SizedBox(
                  width: double.infinity,
                  height: 54,
                  child: OutlinedButton.icon(
                    onPressed: _startMistakeReview,
                    icon: const Icon(Icons.replay),
                    label: Text(
                      'CORRECT $remainingMistakes MISSED '
                      '${remainingMistakes == 1 ? 'ITEM' : 'ITEMS'}',
                    ),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppColors.primaryLight,
                      side: const BorderSide(color: AppColors.primary),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
              ],
              SizedBox(
                width: double.infinity,
                height: 56,
                child: FilledButton(
                  onPressed: () => Navigator.pop(
                    context,
                    LessonResult(
                      score: score,
                      correctAnswers: _initialCorrectQuestionCount,
                      totalQuestions: _questionCount,
                      passed: passed,
                      newlyCompleted: newlyCompleted,
                      xpAwarded: xpAwarded,
                    ),
                  ),
                  style: FilledButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                  ),
                  child: const Text(
                    'RETURN TO PLAN',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
