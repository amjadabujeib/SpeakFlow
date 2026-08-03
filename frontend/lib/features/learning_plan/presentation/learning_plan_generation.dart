part of 'learning_plan_screen.dart';

class _GenerationBanner extends StatelessWidget {
  final PlpDocument document;
  final PlpGeneration generation;
  final VoidCallback onRetry;
  final bool retrying;
  final int retryRemaining;

  const _GenerationBanner({
    required this.document,
    required this.generation,
    required this.onRetry,
    required this.retrying,
    required this.retryRemaining,
  });

  @override
  Widget build(BuildContext context) {
    final isFailed = generation.status == 'failed';
    final isWaiting = generation.status == 'waiting_for_model';
    final interests = document.learnerSnapshot.interests;
    final interestText = interests.isEmpty ? null : interests.join(' · ');
    final statusColor = isFailed ? AppColors.warning : AppColors.primary;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            statusColor.withValues(alpha: 0.18),
            AppColors.surfaceElevated,
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: statusColor.withValues(alpha: 0.45)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 46,
                height: 46,
                decoration: BoxDecoration(
                  color: statusColor.withValues(alpha: 0.18),
                  shape: BoxShape.circle,
                ),
                child: isFailed
                    ? const Icon(Icons.pause_rounded, color: AppColors.warning)
                    : isWaiting
                    ? const Icon(
                        Icons.schedule_rounded,
                        color: AppColors.primaryLight,
                      )
                    : const Padding(
                        padding: EdgeInsets.all(13),
                        child: CircularProgressIndicator(
                          strokeWidth: 2.5,
                          color: AppColors.primaryLight,
                        ),
                      ),
              ),
              const SizedBox(width: 13),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      isFailed
                          ? 'Plan generation paused'
                          : isWaiting
                          ? 'Waiting for Groq’s token window'
                          : 'Building your new plan',
                      style: const TextStyle(
                        fontSize: 19,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      isFailed
                          ? 'Your roadmap is safe. Generation can continue '
                                'from the failed week.'
                          : isWaiting
                          ? 'Your roadmap is safe. Generation will resume '
                                'automatically'
                                '${retryRemaining > 0 ? ' in about ${retryRemaining}s' : ''}.'
                          : 'Your preferences are applied and the new roadmap '
                                'is ready. Week 1 is being written and checked.',
                      style: const TextStyle(
                        color: AppColors.textSecondary,
                        height: 1.35,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (interestText != null) ...[
            const SizedBox(height: 14),
            Row(
              children: [
                const Icon(
                  Icons.tune_rounded,
                  size: 16,
                  color: AppColors.primaryLight,
                ),
                const SizedBox(width: 7),
                Expanded(
                  child: Text(
                    interestText,
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
          ],
          const SizedBox(height: 16),
          _GenerationStep(
            label: 'Preferences applied',
            state: _GenerationStepState.done,
          ),
          const SizedBox(height: 9),
          _GenerationStep(
            label: 'Four-week roadmap created',
            state: _GenerationStepState.done,
          ),
          const SizedBox(height: 9),
          _GenerationStep(
            label: isFailed
                ? 'Writing and checking Week 1 paused'
                : isWaiting
                ? 'Waiting for Groq, then continuing automatically'
                : 'Writing and checking Week 1',
            state: isFailed
                ? _GenerationStepState.failed
                : _GenerationStepState.active,
          ),
          if (!isFailed) ...[
            const SizedBox(height: 16),
            const LinearProgressIndicator(
              minHeight: 5,
              borderRadius: BorderRadius.all(Radius.circular(999)),
            ),
            const SizedBox(height: 9),
            Text(
              isWaiting
                  ? retryRemaining > 0
                        ? 'The next attempt starts in ${retryRemaining}s. '
                              'You can use the other tabs while you wait.'
                        : 'The next attempt is starting automatically.'
                  : 'This page updates automatically. You can use the other '
                        'tabs while the lessons are prepared.',
              style: TextStyle(
                fontSize: 12,
                color: AppColors.textSecondary,
                height: 1.35,
              ),
            ),
          ],
          if (isFailed) ...[
            const SizedBox(height: 14),
            Text(
              generation.error ?? 'The lesson writer could not finish.',
              style: const TextStyle(
                color: AppColors.textSecondary,
                fontSize: 12,
                height: 1.35,
              ),
            ),
            const SizedBox(height: 14),
            FilledButton.icon(
              onPressed: retrying || retryRemaining > 0 ? null : onRetry,
              icon: retrying
                  ? const SizedBox.square(
                      dimension: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.refresh),
              label: Text(
                retrying
                    ? 'Retrying…'
                    : retryRemaining > 0
                    ? 'Retry in ${retryRemaining}s'
                    : 'Continue generating',
              ),
            ),
          ],
        ],
      ),
    );
  }
}

enum _GenerationStepState { done, active, failed }

class _GenerationStep extends StatelessWidget {
  final String label;
  final _GenerationStepState state;

  const _GenerationStep({required this.label, required this.state});

  @override
  Widget build(BuildContext context) {
    final icon = switch (state) {
      _GenerationStepState.done => Icons.check_circle_rounded,
      _GenerationStepState.active => Icons.auto_awesome_rounded,
      _GenerationStepState.failed => Icons.error_rounded,
    };
    final color = switch (state) {
      _GenerationStepState.done => AppColors.success,
      _GenerationStepState.active => AppColors.primaryLight,
      _GenerationStepState.failed => AppColors.warning,
    };
    return Row(
      children: [
        Icon(icon, size: 18, color: color),
        const SizedBox(width: 9),
        Expanded(
          child: Text(
            label,
            style: TextStyle(
              color: state == _GenerationStepState.active
                  ? AppColors.textPrimary
                  : AppColors.textSecondary,
              fontSize: 13,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
    );
  }
}

DateTime? _retryAtFromMap(JsonMap generation) {
  final value = generation['retry_available_at'];
  return value is String ? DateTime.tryParse(value) : null;
}

int _retryRemaining(DateTime? retryAt) {
  if (retryAt == null) return 0;
  final milliseconds = retryAt
      .toUtc()
      .difference(DateTime.now().toUtc())
      .inMilliseconds;
  if (milliseconds <= 0) return 0;
  return (milliseconds / 1000).ceil();
}

bool _isGenerating(String? status) => const {
  'queued',
  'generating_initial',
  'generating_next',
  'waiting_for_model',
  // Legacy states are accepted only so interrupted older jobs can recover.
  'generating_week_one',
  'generating_future_weeks',
}.contains(status);
