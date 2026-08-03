part of 'lesson_screens.dart';

class _LessonGoalCard extends StatelessWidget {
  final Color color;
  final String goal;

  const _LessonGoalCard({required this.color, required this.goal});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: AppColors.surfaceCard,
        borderRadius: BorderRadius.circular(15),
        border: Border.all(color: color.withValues(alpha: 0.32)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.13),
              shape: BoxShape.circle,
            ),
            child: Icon(Icons.flag_outlined, color: color, size: 18),
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'LESSON GOAL',
                  style: TextStyle(
                    color: color,
                    fontSize: 10,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 0.6,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  goal,
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 14,
                    height: 1.4,
                    fontWeight: FontWeight.w600,
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

class _MetaChip extends StatelessWidget {
  final IconData icon;
  final String label;

  const _MetaChip({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.surfaceCard,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.borderLight),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: AppColors.textSecondary),
          const SizedBox(width: 5),
          Text(label, style: const TextStyle(fontSize: 12)),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String text;

  const _SectionTitle(this.text);

  @override
  Widget build(BuildContext context) => Text(
    text,
    style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w900),
  );
}

class _ExampleCard extends StatelessWidget {
  final IconData icon;
  final String text;

  const _ExampleCard({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 9),
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: AppColors.surfaceCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.borderLight),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: AppColors.primaryLight, size: 21),
          const SizedBox(width: 11),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(fontSize: 16, height: 1.4),
            ),
          ),
        ],
      ),
    );
  }
}

class _QuestionLabel extends StatelessWidget {
  final String hint;

  const _QuestionLabel({required this.hint});

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const Icon(Icons.psychology_alt, color: AppColors.primaryLight),
      const SizedBox(width: 8),
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Knowledge check',
              style: TextStyle(
                color: AppColors.primaryLight,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              hint,
              style: const TextStyle(
                fontSize: 12,
                color: AppColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    ],
  );
}

class _AnswerOption extends StatelessWidget {
  final String label;
  final bool selected;
  final bool correct;
  final bool incorrect;
  final bool enabled;
  final Color themeColor;
  final VoidCallback onTap;

  const _AnswerOption({
    required this.label,
    required this.selected,
    required this.correct,
    required this.incorrect,
    required this.enabled,
    required this.themeColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final color = correct
        ? Colors.green
        : incorrect
        ? Colors.red
        : selected
        ? themeColor
        : AppColors.borderLight;
    return Padding(
      padding: const EdgeInsets.only(bottom: 11),
      child: InkWell(
        onTap: enabled ? onTap : null,
        borderRadius: BorderRadius.circular(16),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          padding: const EdgeInsets.all(17),
          decoration: BoxDecoration(
            color: correct
                ? Colors.green.withValues(alpha: 0.1)
                : incorrect
                ? Colors.red.withValues(alpha: 0.1)
                : selected
                ? themeColor.withValues(alpha: 0.12)
                : AppColors.surfaceCard,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: color,
              width: selected || correct ? 2 : 1.5,
            ),
          ),
          child: Row(
            children: [
              Icon(
                correct
                    ? Icons.check_circle
                    : incorrect
                    ? Icons.cancel
                    : selected
                    ? Icons.radio_button_checked
                    : Icons.radio_button_off,
                color: color,
              ),
              const SizedBox(width: 13),
              Expanded(
                child: Text(
                  label,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
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

class _AnswerExplanation extends StatelessWidget {
  final bool isCorrect;
  final String text;

  const _AnswerExplanation({required this.isCorrect, required this.text});

  @override
  Widget build(BuildContext context) {
    final color = isCorrect ? Colors.green : Colors.red;
    return Container(
      margin: const EdgeInsets.only(top: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(isCorrect ? Icons.check_circle : Icons.info, color: color),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(height: 1.4, fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}

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
  PlpLessonType.speaking => 'Speaking',
  PlpLessonType.discourse => 'Communication',
  PlpLessonType.assessment => 'Checkpoint',
};

String _activityPhaseLabel(PlpActivityPhase phase) => switch (phase) {
  PlpActivityPhase.unspecified => 'Lesson activity',
  PlpActivityPhase.learn => 'Learn',
  PlpActivityPhase.guidedPractice => 'Guided practice',
  PlpActivityPhase.independentCheck => 'Independent check',
  PlpActivityPhase.review => 'Review',
};

IconData _activityPhaseIcon(PlpActivityPhase phase) => switch (phase) {
  PlpActivityPhase.unspecified => Icons.layers_outlined,
  PlpActivityPhase.learn => Icons.menu_book_outlined,
  PlpActivityPhase.guidedPractice => Icons.assistant_outlined,
  PlpActivityPhase.independentCheck => Icons.fact_check_outlined,
  PlpActivityPhase.review => Icons.history,
};

Color _activityPhaseColor(PlpActivityPhase phase) => switch (phase) {
  PlpActivityPhase.unspecified => AppColors.textSecondary,
  PlpActivityPhase.learn => AppColors.primaryLight,
  PlpActivityPhase.guidedPractice => AppColors.success,
  PlpActivityPhase.independentCheck => AppColors.warning,
  PlpActivityPhase.review => AppColors.accentLight,
};
