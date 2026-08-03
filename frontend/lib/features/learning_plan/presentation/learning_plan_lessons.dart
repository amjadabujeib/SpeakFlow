part of 'learning_plan_screen.dart';

class _UnitSection extends StatelessWidget {
  final PlpDocument document;
  final PlpUnit unit;
  final ValueChanged<PlpLesson> onOpenLesson;

  const _UnitSection({
    required this.document,
    required this.unit,
    required this.onOpenLesson,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final lesson in unit.lessons)
            _LessonCard(
              document: document,
              lesson: lesson,
              onTap: () => onOpenLesson(lesson),
            ),
        ],
      ),
    );
  }
}

class _LessonCard extends StatelessWidget {
  final PlpDocument document;
  final PlpLesson lesson;
  final VoidCallback onTap;

  const _LessonCard({
    required this.document,
    required this.lesson,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final status = document.statusOf(lesson);
    final state = document.progress.lessonStates[lesson.id];
    final style = _statusStyle(status);
    final prerequisiteTitles = lesson.requiredLessonIds
        .where(
          (id) =>
              document.progress.lessonStates[id]?.status !=
              StoredLessonStatus.completed,
        )
        .map((id) => document.lessonById[id]?.title)
        .whereType<String>()
        .toList(growable: false);

    return Card(
      elevation: status == PlpLessonStatus.inProgress ? 2 : 0,
      color: style.background,
      margin: const EdgeInsets.only(bottom: 10),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(13),
        side: BorderSide(color: style.border),
      ),
      child: InkWell(
        onTap: status == PlpLessonStatus.locked ? null : onTap,
        borderRadius: BorderRadius.circular(13),
        child: Padding(
          padding: const EdgeInsets.all(13),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: style.iconBackground,
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  lesson.contentStatus == PlpContentStatus.pending
                      ? Icons.hourglass_top
                      : lesson.contentStatus == PlpContentStatus.failed
                      ? Icons.error_outline
                      : status == PlpLessonStatus.completed
                      ? Icons.check
                      : status == PlpLessonStatus.locked
                      ? Icons.lock_outline
                      : _lessonIcon(lesson.type),
                  color: style.foreground,
                  size: 22,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      lesson.title,
                      style: TextStyle(
                        color: status == PlpLessonStatus.locked
                            ? AppColors.textMuted
                            : AppColors.textPrimary,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      lesson.description,
                      style: TextStyle(
                        color: status == PlpLessonStatus.locked
                            ? AppColors.textMuted
                            : AppColors.textSecondary,
                        fontSize: 13,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 10,
                      runSpacing: 4,
                      children: [
                        _TinyMeta(
                          icon: Icons.today_outlined,
                          text: 'Day ${lesson.sequence}',
                        ),
                        _TinyMeta(
                          icon: Icons.schedule,
                          text: '${lesson.estimatedMinutes} min',
                        ),
                        _TinyMeta(icon: Icons.bolt, text: '${lesson.xp} XP'),
                        _TinyMeta(
                          icon: lesson.lessonRole == null
                              ? _lessonIcon(lesson.type)
                              : Icons.route_outlined,
                          text: lesson.lessonRole == null
                              ? _lessonTypeLabel(lesson.type)
                              : _metadataLabel(lesson.lessonRole!),
                        ),
                        if (state?.bestScore != null)
                          _TinyMeta(
                            icon: Icons.workspace_premium,
                            text: 'Lesson ${state!.bestScore}%',
                          ),
                      ],
                    ),
                    if (status == PlpLessonStatus.locked &&
                        !lesson.isReady) ...[
                      const SizedBox(height: 7),
                      Text(
                        lesson.contentStatus == PlpContentStatus.failed
                            ? 'Content generation failed. Refresh after retrying.'
                            : 'Scheduled for just-in-time generation…',
                        style: const TextStyle(
                          color: AppColors.textMuted,
                          fontSize: 11,
                        ),
                      ),
                    ] else if (status == PlpLessonStatus.locked &&
                        prerequisiteTitles.isNotEmpty) ...[
                      const SizedBox(height: 7),
                      Text(
                        'Complete ${prerequisiteTitles.join(', ')} first',
                        style: const TextStyle(
                          color: AppColors.textMuted,
                          fontSize: 11,
                        ),
                      ),
                    ] else if (status == PlpLessonStatus.inProgress) ...[
                      const SizedBox(height: 7),
                      Text(
                        lesson.personalizationReason,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: AppColors.primaryLight,
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              if (status != PlpLessonStatus.locked)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Icon(Icons.chevron_right, color: style.foreground),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TinyMeta extends StatelessWidget {
  final IconData icon;
  final String text;

  const _TinyMeta({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 13, color: AppColors.textMuted),
        const SizedBox(width: 3),
        Flexible(
          child: Text(
            text,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 11,
              color: AppColors.textSecondary,
            ),
          ),
        ),
      ],
    );
  }
}

({Color background, Color border, Color iconBackground, Color foreground})
_statusStyle(PlpLessonStatus status) => switch (status) {
  PlpLessonStatus.completed => (
    background: AppColors.success.withValues(alpha: 0.1),
    border: AppColors.success.withValues(alpha: 0.3),
    iconBackground: AppColors.success.withValues(alpha: 0.16),
    foreground: AppColors.success,
  ),
  PlpLessonStatus.inProgress => (
    background: AppColors.primary.withValues(alpha: 0.12),
    border: AppColors.primary,
    iconBackground: AppColors.primary.withValues(alpha: 0.2),
    foreground: AppColors.primaryLight,
  ),
  PlpLessonStatus.available => (
    background: AppColors.surfaceCard,
    border: AppColors.borderLight,
    iconBackground: AppColors.surfaceElevated,
    foreground: AppColors.primary,
  ),
  PlpLessonStatus.locked => (
    background: AppColors.surface,
    border: AppColors.border,
    iconBackground: AppColors.surfaceElevated,
    foreground: AppColors.textMuted,
  ),
};

IconData _lessonIcon(PlpLessonType type) => switch (type) {
  PlpLessonType.vocabulary => Icons.menu_book,
  PlpLessonType.grammar => Icons.account_tree,
  PlpLessonType.pronunciation => Icons.record_voice_over,
  PlpLessonType.reading => Icons.chrome_reader_mode,
  PlpLessonType.listening => Icons.headphones,
  PlpLessonType.speaking => Icons.forum,
  PlpLessonType.discourse => Icons.forum_outlined,
  PlpLessonType.assessment => Icons.fact_check,
};

String _lessonTypeLabel(PlpLessonType type) => switch (type) {
  PlpLessonType.vocabulary => 'Vocabulary',
  PlpLessonType.grammar => 'Grammar',
  PlpLessonType.pronunciation => 'Pronunciation',
  PlpLessonType.reading => 'Reading',
  PlpLessonType.listening => 'Listening',
  PlpLessonType.speaking => 'Conversation language',
  PlpLessonType.discourse => 'Communication',
  PlpLessonType.assessment => 'Checkpoint',
};

String _metadataLabel(String value) => value
    .split('_')
    .where((part) => part.isNotEmpty)
    .map((part) => '${part.substring(0, 1).toUpperCase()}${part.substring(1)}')
    .join(' ');
