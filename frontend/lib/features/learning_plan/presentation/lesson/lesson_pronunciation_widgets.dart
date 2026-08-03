part of 'lesson_screens.dart';

extension _LessonPronunciationWidgets on _InteractiveLessonScreenState {
  Widget _buildPronunciation(PlpActivity activity) {
    final data = activity.data;
    final tips = (data['tips'] as List).cast<String>();
    final practiceItems = data['practice_items'] as List;
    return _activityPage(
      activity: activity,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                (data['title'] ?? data['sound_label']) as String,
                style: const TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.w900,
                  color: AppColors.textPrimary,
                ),
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 8),
              decoration: BoxDecoration(
                color: _themeColor.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(14),
              ),
              child: Text(
                (data['target_ipa'] ?? data['ipa']) as String,
                style: TextStyle(
                  color: _themeColor,
                  fontSize: 21,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 18),
        Text(
          data['instructions'] as String,
          style: const TextStyle(fontSize: 18, height: 1.5),
        ),
        ..._nativeHintWidgets(data),
        const SizedBox(height: 22),
        _InfoPanel(
          color: _themeColor,
          icon: Icons.lightbulb_outline,
          title: 'Technique',
          children: tips,
        ),
        const SizedBox(height: 24),
        const _SectionTitle('Practice targets'),
        const SizedBox(height: 10),
        if (_submittedActivityIds.contains(activity.id)) ...[
          _LessonPracticeMessage(
            color: Colors.green,
            icon: Icons.verified,
            text:
                'All ${practiceItems.length} assigned targets passed. You can '
                'continue the lesson.',
          ),
          const SizedBox(height: 10),
        ] else if ((_passedPronunciationTargets[activity.id]?.length ?? 0) >
            0) ...[
          _LessonPracticeMessage(
            color: Colors.blue,
            icon: Icons.timelapse_rounded,
            text:
                '${_passedPronunciationTargets[activity.id]!.length} of '
                '${practiceItems.length} targets passed. Complete the rest to '
                'continue.',
          ),
          const SizedBox(height: 10),
        ],
        for (final item in practiceItems)
          _buildPronunciationTargetCard(activity, item, practiceItems),
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: AppColors.surfaceElevated,
            borderRadius: BorderRadius.circular(13),
            border: Border.all(color: AppColors.borderLight),
          ),
          child: const Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.info_outline, color: AppColors.primaryLight),
              SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Listen if helpful, then practise each assigned target. Every '
                  'target must pass before you can continue.',
                  style: TextStyle(
                    height: 1.35,
                    color: AppColors.textSecondary,
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  String _pronunciationTarget(dynamic item) =>
      item is String ? item : item['text'] as String;

  Widget _buildPronunciationTargetCard(
    PlpActivity activity,
    dynamic item,
    List practiceItems,
  ) {
    final target = _pronunciationTarget(item);
    final normalizedTarget = _normalisePronunciationTarget(target);
    final passed =
        _submittedActivityIds.contains(activity.id) ||
        (_passedPronunciationTargets[activity.id]?.contains(normalizedTarget) ??
            false);
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 9),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: const BorderSide(color: AppColors.borderLight),
      ),
      child: ListTile(
        leading: IconButton.filledTonal(
          tooltip: 'Hear with Kokoro',
          onPressed: () async {
            final audio = await AppDependencies.instance.languageTools
                .synthesizeSpeech(target);
            await _audioPlayer.play(BytesSource(audio));
          },
          icon: const Icon(Icons.volume_up),
        ),
        title: Text(
          target,
          style: const TextStyle(fontWeight: FontWeight.w800),
        ),
        subtitle: item is Map && item['ipa'] is String
            ? Text(item['ipa'] as String)
            : null,
        trailing: passed
            ? const Icon(Icons.verified_rounded, color: AppColors.success)
            : FilledButton.tonal(
                onPressed: () => _openPronunciationPractice(
                  activity,
                  target,
                  practiceItems.map(_pronunciationTarget).toList(),
                ),
                child: const Text('Practice'),
              ),
      ),
    );
  }

  Future<void> _openPronunciationPractice(
    PlpActivity activity,
    String target,
    List<String> assignedTargets,
  ) async {
    final result = await Navigator.of(context).push<PlpAttemptResult>(
      MaterialPageRoute(
        builder: (_) => _LessonPronunciationPracticePage(
          initialTarget: target,
          assignedTargets: assignedTargets,
          activityId: widget.submitAttempt == null ? null : activity.id,
          attemptSessionId: _attemptSessionId,
        ),
      ),
    );
    if (!mounted || result == null) return;
    _update(() {
      _recordServerLessonResult(result);
      if (result.correct == true) {
        _passedPronunciationTargets
            .putIfAbsent(activity.id, () => {})
            .add(_normalisePronunciationTarget(target));
      }
      if (result.completedActivityIds.contains(activity.id)) {
        _submittedActivityIds.add(activity.id);
      }
      _serverExplanations[activity.id] = result.explanation;
    });
  }

  String _normalisePronunciationTarget(String value) =>
      value.trim().toLowerCase().replaceAll(RegExp(r'\s+'), ' ');
}
