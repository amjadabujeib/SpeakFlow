part of 'lesson_screens.dart';

class _LessonScoreBar extends StatelessWidget {
  final String label;
  final int score;

  const _LessonScoreBar({required this.label, required this.score});

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [Text(label), Text('$score%')],
        ),
        const SizedBox(height: 5),
        LinearProgressIndicator(value: score.clamp(0, 100) / 100),
      ],
    ),
  );
}

class _LessonPhoneChip extends StatelessWidget {
  final JsonMap data;

  const _LessonPhoneChip({required this.data});

  @override
  Widget build(BuildContext context) {
    final status = data['status']?.toString();
    final color = switch (status) {
      'correct' => Colors.green,
      'warning' => Colors.orange,
      'omitted' => Colors.grey,
      _ => Colors.red,
    };
    final label = data['char']?.toString().replaceAll('_', '').trim();
    return Chip(
      backgroundColor: color.withValues(alpha: 0.12),
      side: BorderSide(color: color.withValues(alpha: 0.55)),
      label: Text(
        label?.isNotEmpty == true ? label! : '?',
        style: TextStyle(color: color.shade300, fontWeight: FontWeight.w800),
      ),
    );
  }
}

class _LessonPracticeMessage extends StatelessWidget {
  final MaterialColor color;
  final IconData icon;
  final String text;

  const _LessonPracticeMessage({
    required this.color,
    required this.icon,
    required this.text,
  });

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.1),
      border: Border.all(color: color.withValues(alpha: 0.38)),
      borderRadius: BorderRadius.circular(12),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: color.shade300),
        const SizedBox(width: 10),
        Expanded(child: Text(text, style: const TextStyle(height: 1.4))),
      ],
    ),
  );
}

class _ActivityPhaseBanner extends StatelessWidget {
  final PlpActivityPhase phase;

  const _ActivityPhaseBanner({super.key, required this.phase});

  @override
  Widget build(BuildContext context) {
    final color = _activityPhaseColor(phase);
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.09),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: color.withValues(alpha: 0.22)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(_activityPhaseIcon(phase), size: 16, color: color),
            const SizedBox(width: 6),
            Text(
              _activityPhaseLabel(phase),
              style: TextStyle(
                color: color,
                fontSize: 12,
                fontWeight: FontWeight.w900,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _InfoPanel extends StatelessWidget {
  final Color color;
  final IconData icon;
  final String title;
  final List<String> children;

  const _InfoPanel({
    required this.color,
    required this.icon,
    required this.title,
    required this.children,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.18)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: color, size: 21),
              const SizedBox(width: 8),
              Text(
                title,
                style: TextStyle(color: color, fontWeight: FontWeight.w900),
              ),
            ],
          ),
          const SizedBox(height: 10),
          for (final item in children)
            Padding(
              padding: const EdgeInsets.only(bottom: 7),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('• ', style: TextStyle(color: color, fontSize: 18)),
                  Expanded(
                    child: Text(
                      item,
                      style: const TextStyle(
                        height: 1.35,
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
