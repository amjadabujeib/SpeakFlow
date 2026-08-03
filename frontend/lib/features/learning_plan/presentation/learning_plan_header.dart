part of 'learning_plan_screen.dart';

class _PlanHeader extends StatelessWidget {
  final PlpDocument document;

  const _PlanHeader({required this.document});

  @override
  Widget build(BuildContext context) {
    final plan = document.plan;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [AppColors.surfaceCard, Color(0xFF17223A)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.borderLight),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 46,
                height: 46,
                decoration: BoxDecoration(
                  gradient: AppColors.primaryGradient,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(
                  Icons.route_rounded,
                  color: Colors.white,
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  plan.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 17,
                    height: 1.25,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _PlanDetailChip(
                icon: Icons.trending_up_rounded,
                label: '${plan.currentLevel} → ${plan.targetLevel}',
                highlighted: true,
              ),
              _PlanDetailChip(
                icon: Icons.calendar_today_rounded,
                label: '${plan.schedule.durationWeeks} weeks',
              ),
              _PlanDetailChip(
                icon: Icons.schedule_rounded,
                label: '${plan.schedule.minutesPerDay} min/day',
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _PlanDetailChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool highlighted;

  const _PlanDetailChip({
    required this.icon,
    required this.label,
    this.highlighted = false,
  });

  @override
  Widget build(BuildContext context) {
    final color = highlighted
        ? AppColors.primaryLight
        : AppColors.textSecondary;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: highlighted
            ? AppColors.primary.withValues(alpha: 0.12)
            : AppColors.surface.withValues(alpha: 0.72),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: highlighted
              ? AppColors.primary.withValues(alpha: 0.32)
              : AppColors.border,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 5),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _ProgressOverview extends StatelessWidget {
  final PlpDocument document;

  const _ProgressOverview({required this.document});

  @override
  Widget build(BuildContext context) {
    final progress = document.progress;
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: const BorderSide(color: AppColors.border),
      ),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          children: [
            Row(
              children: [
                const Expanded(
                  child: Text(
                    'Plan progress',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800),
                  ),
                ),
                const SizedBox(width: 10),
                Text(
                  '${(document.completionRatio * 100).round()}%',
                  style: TextStyle(
                    color: AppColors.primaryLight,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: document.completionRatio,
                minHeight: 11,
                backgroundColor: AppColors.surface,
                color: AppColors.primary,
              ),
            ),
            const SizedBox(height: 18),
            Row(
              children: [
                _Metric(
                  icon: Icons.local_fire_department,
                  color: Colors.deepOrange,
                  value: '${progress.currentStreakDays}',
                  label: 'day streak',
                ),
                _Metric(
                  icon: Icons.calendar_month,
                  color: Colors.blue,
                  value:
                      '${progress.studiedDatesThisWeek.length}/${progress.weeklyGoalDays}',
                  label: 'days this week',
                ),
                _Metric(
                  icon: Icons.bolt,
                  color: Colors.amber.shade800,
                  value: '${document.earnedXp}',
                  label: 'XP earned',
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String value;
  final String label;

  const _Metric({
    required this.icon,
    required this.color,
    required this.value,
    required this.label,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        children: [
          Icon(icon, color: color, size: 23),
          const SizedBox(height: 4),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w900)),
          Text(
            label,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 11,
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }
}
