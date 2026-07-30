import 'dart:async';

import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../core/data/practice_word_store.dart';
import '../core/data/phoneme_progress_store.dart';
import '../lesson_screens.dart';
import 'plp_models.dart';
import 'onboarding_screen.dart';
import 'plp_repository.dart';

class LearningPlanScreen extends StatefulWidget {
  final PlpRepository? repository;
  final VoidCallback? onPlanReady;
  final bool embedded;
  final Widget? embeddedTop;

  const LearningPlanScreen({
    super.key,
    this.repository,
    this.onPlanReady,
    this.embedded = false,
    this.embeddedTop,
  });

  @override
  State<LearningPlanScreen> createState() => _LearningPlanScreenState();
}

class _LearningPlanScreenState extends State<LearningPlanScreen> {
  late final PlpRepository _repository;
  PlpDocument? _document;
  Object? _loadError;
  JsonMap? _generation;
  Timer? _pollTimer;
  Timer? _cooldownTimer;
  bool _resetting = false;
  bool _retryingGeneration = false;
  bool _notifiedPlanReady = false;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? HttpPlpRepository();
    _loadPlan();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _cooldownTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadPlan({
    bool showLoader = true,
    bool managePolling = true,
  }) async {
    setState(() {
      if (showLoader) _document = null;
      _loadError = null;
    });
    try {
      final document = await _repository.loadPlan();
      if (!mounted) return;
      setState(() {
        _document = document;
        _generation = null;
      });
      final generation = document.generation;
      _syncCooldownTimer(generation?.retryAvailableAt);
      if (widget.onPlanReady != null &&
          !_notifiedPlanReady &&
          (generation == null ||
              (!_isGenerating(generation.status) &&
                  generation.readyWeeks > 0))) {
        _notifiedPlanReady = true;
        widget.onPlanReady!();
        return;
      }
      if (managePolling && generation != null) {
        if (_isGenerating(generation.status)) {
          _startPolling(generation.jobId);
        } else {
          _pollTimer?.cancel();
        }
      }
    } catch (error) {
      if (!mounted) return;
      if (_repository.isRemote &&
          error is PlpApiException &&
          error.statusCode == 404) {
        try {
          final latest = await _repository.latestGeneration();
          if (!mounted) return;
          final state = latest['status']?.toString();
          final jobId = latest['job_id']?.toString();
          setState(() {
            _generation = latest;
            _loadError = null;
          });
          _syncCooldownTimer(_retryAtFromMap(latest));
          if (jobId != null && _isGenerating(state)) {
            _startPolling(jobId);
          }
          return;
        } on PlpApiException catch (latestError) {
          if (latestError.statusCode != 404) {
            setState(() => _loadError = latestError);
            return;
          }
        } catch (latestError) {
          setState(() => _loadError = latestError);
          return;
        }
      }
      setState(() => _loadError = error);
    }
  }

  Future<void> _beginOnboarding() async {
    final jobId = await Navigator.push<String>(
      context,
      MaterialPageRoute(
        builder: (_) => PlpOnboardingScreen(repository: _repository),
      ),
    );
    if (!mounted || jobId == null) return;
    await _loadPlan();
  }

  void _startPolling(String jobId) {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(
      const Duration(seconds: 3),
      (_) => _pollGeneration(jobId),
    );
    _pollGeneration(jobId);
  }

  void _syncCooldownTimer(DateTime? retryAt) {
    _cooldownTimer?.cancel();
    if (_retryRemaining(retryAt) <= 0) return;
    _cooldownTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted || _retryRemaining(retryAt) <= 0) {
        timer.cancel();
        if (mounted) setState(() {});
        return;
      }
      setState(() {});
    });
  }

  Future<void> _pollGeneration(String jobId) async {
    try {
      final status = await _repository.generationStatus(jobId);
      if (!mounted) return;
      final state = status['status'] as String?;
      final readyWeeks = status['ready_weeks'] as int? ?? 0;
      if (!_isGenerating(state) && readyWeeks > 0) {
        _pollTimer?.cancel();
        await _loadPlan(showLoader: false, managePolling: false);
        return;
      }
      if (_document == null) {
        setState(() => _generation = status);
        _syncCooldownTimer(_retryAtFromMap(status));
      } else {
        await _loadPlan(showLoader: false, managePolling: false);
      }
      if (!_isGenerating(state)) _pollTimer?.cancel();
    } catch (error) {
      if (mounted) setState(() => _loadError = error);
      _pollTimer?.cancel();
    }
  }

  Future<void> _retryGeneration(String jobId) async {
    if (_retryingGeneration) return;
    setState(() => _retryingGeneration = true);
    try {
      final status = await _repository.retryGeneration(jobId);
      if (!mounted) return;
      setState(() {
        _loadError = null;
        _generation = status;
      });
      _syncCooldownTimer(null);
      _startPolling(jobId);
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not retry generation: $error')),
      );
    } finally {
      if (mounted) setState(() => _retryingGeneration = false);
    }
  }

  Future<void> _resetAndOnboard() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Reset learning plan?'),
        content: const Text(
          'This deletes your onboarding answers, generated lessons, progress, '
          'attempts, streaks, roleplay history, saved practice words, phoneme '
          'measurements, and adaptation history. The reviewed curriculum and '
          'pronunciation models are not changed.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Colors.red.shade700),
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Reset and start over'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() => _resetting = true);
    try {
      _pollTimer?.cancel();
      await _repository.resetLearner();
      await PracticeWordStore.instance.clear();
      await PhonemeProgressStore.instance.clear();
      if (!mounted) return;
      setState(() {
        _document = null;
        _generation = null;
        _loadError = null;
        _resetting = false;
      });
      await _beginOnboarding();
    } catch (error) {
      if (!mounted) return;
      setState(() => _resetting = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not reset the learning plan: $error')),
      );
    }
  }

  Future<void> _openLesson(PlpLesson lesson) async {
    final document = _document;
    if (document == null ||
        document.statusOf(lesson) == PlpLessonStatus.locked) {
      return;
    }
    final result = await Navigator.push<LessonResult>(
      context,
      MaterialPageRoute(
        builder: (context) => InteractiveLessonScreen(
          lesson: lesson,
          completedActivityIds:
              document.progress.lessonStates[lesson.id]?.completedActivityIds
                  .toSet() ??
              const {},
          submitAttempt: _repository.isRemote
              ? _repository.submitAttempt
              : null,
        ),
      ),
    );
    if (!mounted || result == null) return;
    if (_repository.isRemote) {
      await _loadPlan();
    } else {
      setState(() {
        _document = document.withLessonResult(
          lesson.id,
          score: result.score ?? 0,
        );
      });
    }
    if (!mounted) return;
    if (!result.passed) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            result.score == null
                ? 'This checkpoint stays open for another attempt.'
                : 'Score ${result.score}%. This checkpoint stays open for '
                      'another attempt.',
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final content = _document != null
        ? _buildPlan(_document!)
        : _withEmbeddedTop(
            _loadError != null
                ? _buildError(_loadError!)
                : _generation != null
                ? _buildGenerationProgress(_generation!)
                : const Center(child: CircularProgressIndicator()),
          );

    if (widget.embedded) {
      return Material(color: AppColors.background, child: content);
    }

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Your Learning Plan'),
        elevation: 0,
        backgroundColor: AppColors.surface,
        foregroundColor: AppColors.textPrimary,
        actions: [
          if (_repository.isRemote)
            TextButton.icon(
              onPressed: _resetting ? null : _resetAndOnboard,
              style: TextButton.styleFrom(
                foregroundColor: AppColors.textPrimary,
                disabledForegroundColor: AppColors.textMuted,
              ),
              icon: _resetting
                  ? const SizedBox.square(
                      dimension: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: AppColors.textPrimary,
                      ),
                    )
                  : const Icon(Icons.delete_outline, size: 19),
              label: const Text('Reset'),
            ),
          IconButton(
            onPressed: _loadPlan,
            tooltip: 'Refresh learning plan',
            icon: const Icon(Icons.restart_alt),
          ),
        ],
      ),
      body: content,
    );
  }

  Widget _withEmbeddedTop(Widget child) {
    final top = widget.embeddedTop;
    if (!widget.embedded || top == null) return child;
    return Column(
      children: [
        Padding(padding: const EdgeInsets.fromLTRB(16, 12, 16, 0), child: top),
        Expanded(child: child),
      ],
    );
  }

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
    final generation = document.generation;
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
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
