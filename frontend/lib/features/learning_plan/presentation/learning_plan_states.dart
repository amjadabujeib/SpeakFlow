part of 'learning_plan_screen.dart';

extension _LearningPlanStates on _LearningPlanScreenState {
  Widget _buildGenerationProgress(JsonMap generation) {
    final status = generation['status']?.toString() ?? 'queued';
    final isWaiting = status == 'waiting_for_model';
    final jobId = generation['job_id']?.toString();
    final retryRemaining = _retryRemaining(_retryAtFromMap(generation));
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              isWaiting ? Icons.schedule_rounded : Icons.auto_awesome,
              color: AppColors.primary,
              size: 56,
            ),
            const SizedBox(height: 18),
            Text(
              status == 'failed'
                  ? 'Lesson generation stopped'
                  : isWaiting
                  ? 'Waiting for Groq’s token window'
                  : 'Preparing your first lessons',
              style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 8),
            Text(
              status == 'failed'
                  ? generation['error']?.toString() ??
                        'A lesson could not pass generation validation.'
                  : isWaiting
                  ? 'Your roadmap and lesson progress are safe. Generation '
                        'will resume automatically'
                        '${retryRemaining > 0 ? ' in about ${retryRemaining}s' : ''}.'
                  : 'Your roadmap is saved. The five lessons in Week 1 are '
                        'being written and validated together.',
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: AppColors.textSecondary,
                height: 1.4,
              ),
            ),
            const SizedBox(height: 22),
            LinearProgressIndicator(value: status == 'failed' ? 0 : null),
            if (status != 'failed') ...[
              const SizedBox(height: 8),
              Text(
                isWaiting
                    ? retryRemaining > 0
                          ? 'Continuing automatically in ${retryRemaining}s…'
                          : 'Continuing automatically…'
                    : 'Preparing your first week…',
              ),
            ],
            if (status == 'failed' && jobId != null) ...[
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _retryingGeneration || retryRemaining > 0
                    ? null
                    : () => _retryGeneration(jobId),
                icon: _retryingGeneration
                    ? const SizedBox.square(
                        dimension: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.refresh),
                label: Text(
                  _retryingGeneration
                      ? 'Retrying…'
                      : retryRemaining > 0
                      ? 'Retry in ${retryRemaining}s'
                      : 'Retry generation',
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildError(Object error) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.data_object, size: 52, color: Colors.red.shade400),
            const SizedBox(height: 16),
            Text(
              _repository.isRemote
                  ? 'Your learning plan is not ready yet.'
                  : 'The learning-plan mock data is invalid.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 19, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              '$error',
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.textSecondary),
            ),
            const SizedBox(height: 20),
            if (_repository.isRemote)
              FilledButton.icon(
                onPressed: _beginOnboarding,
                icon: const Icon(Icons.auto_awesome),
                label: const Text('Set up my plan'),
              )
            else
              FilledButton.icon(
                onPressed: _loadPlan,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildPlan(PlpDocument document) {
    final generation = _generation == null
        ? document.generation
        : PlpGeneration.fromJson(_generation!);
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (widget.embeddedTop case final top?) ...[
            top,
            const SizedBox(height: 16),
          ],
          if (generation != null &&
              (_isGenerating(generation.status) ||
                  generation.status == 'failed')) ...[
            _GenerationBanner(
              document: document,
              generation: generation,
              onRetry: () => _retryGeneration(generation.jobId),
              retrying: _retryingGeneration,
              retryRemaining: _retryRemaining(generation.retryAvailableAt),
            ),
            const SizedBox(height: 16),
          ],
          _PlanHeader(document: document),
          const SizedBox(height: 16),
          _ProgressOverview(document: document),
          const SizedBox(height: 28),
          Row(
            children: [
              Expanded(
                child: Text(
                  '${document.plan.schedule.durationWeeks}-week path',
                  style: Theme.of(
                    context,
                  ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
                ),
              ),
              Text(
                '${document.completedLessonCount}/${document.lessons.length} lessons',
                style: TextStyle(
                  color: AppColors.primaryLight,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          for (final week in document.plan.weeks)
            _WeekCard(
              document: document,
              week: week,
              onOpenLesson: _openLesson,
            ),
        ],
      ),
    );
  }
}
