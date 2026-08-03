part of 'learning_plan_screen.dart';

class _WeekCard extends StatelessWidget {
  final PlpDocument document;
  final PlpWeek week;
  final ValueChanged<PlpLesson> onOpenLesson;

  const _WeekCard({
    required this.document,
    required this.week,
    required this.onOpenLesson,
  });

  @override
  Widget build(BuildContext context) {
    final lessons = [for (final unit in week.units) ...unit.lessons];
    final completed = lessons
        .where(
          (lesson) => document.statusOf(lesson) == PlpLessonStatus.completed,
        )
        .length;
    final containsCurrent = lessons.any(
      (lesson) => document.progress.currentLessonId == lesson.id,
    );
    return Card(
      margin: const EdgeInsets.only(bottom: 14),
      elevation: 0,
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(
          color: containsCurrent ? AppColors.primary : AppColors.border,
          width: containsCurrent ? 1.5 : 1,
        ),
      ),
      child: ExpansionTile(
        initiallyExpanded: containsCurrent || week.sequence == 1,
        tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 14),
        leading: CircleAvatar(
          backgroundColor: completed == lessons.length
              ? AppColors.success.withValues(alpha: 0.16)
              : AppColors.primary.withValues(alpha: 0.14),
          foregroundColor: completed == lessons.length
              ? AppColors.success
              : AppColors.primaryLight,
          child: completed == lessons.length
              ? const Icon(Icons.check)
              : Text('${week.sequence}'),
        ),
        title: Text(
          week.title,
          style: const TextStyle(fontWeight: FontWeight.w800),
        ),
        subtitle: Text('$completed of ${lessons.length} lessons completed'),
        children: [
          if (week.mission case final mission?)
            _MissionSummary(mission: mission),
          for (final unit in week.units)
            _UnitSection(
              document: document,
              unit: unit,
              onOpenLesson: onOpenLesson,
            ),
        ],
      ),
    );
  }
}

class _MissionSummary extends StatelessWidget {
  final PlpWeekMission mission;

  const _MissionSummary({required this.mission});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(top: 8, bottom: 4),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surfaceElevated,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(
                Icons.flag_outlined,
                color: AppColors.primary,
                size: 21,
              ),
              const SizedBox(width: 9),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'YOUR WEEKLY OUTCOME',
                      style: TextStyle(
                        color: AppColors.primaryLight,
                        fontSize: 11,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 0.7,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      mission.canDo,
                      style: const TextStyle(
                        fontSize: 15,
                        height: 1.3,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(
                Icons.task_alt,
                size: 17,
                color: AppColors.textSecondary,
              ),
              const SizedBox(width: 7),
              Expanded(
                child: Text(
                  'Finish with ${mission.product.replaceFirst(RegExp(r'[.!?]+$'), '')}.',
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    height: 1.35,
                    fontSize: 13,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 7,
            runSpacing: 7,
            children: [
              _MissionTag(
                icon: Icons.track_changes,
                label: 'Goal · ${mission.goalLabel}',
              ),
              _MissionTag(
                icon: Icons.interests_outlined,
                label: 'Interest · ${mission.interestLabel}',
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MissionTag extends StatelessWidget {
  final IconData icon;
  final String label;

  const _MissionTag({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.surfaceCard,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.borderLight),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: AppColors.primary),
          const SizedBox(width: 5),
          Text(
            label,
            style: TextStyle(
              color: AppColors.textPrimary,
              fontSize: 11,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}
