import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/providers.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/data/practice_word_store.dart';
import '../../../core/data/phoneme_progress_store.dart';
import '../data/plp_repository.dart';
import '../domain/plp_models.dart';
import 'lesson/lesson_screens.dart';
import 'onboarding_screen.dart';

part 'learning_plan_states.dart';
part 'learning_plan_header.dart';
part 'learning_plan_weeks.dart';
part 'learning_plan_lessons.dart';
part 'learning_plan_generation.dart';

class LearningPlanScreen extends ConsumerStatefulWidget {
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
  ConsumerState<LearningPlanScreen> createState() => _LearningPlanScreenState();
}

class _LearningPlanScreenState extends ConsumerState<LearningPlanScreen> {
  late final PlpRepository _repository;
  PlpDocument? _document;
  Object? _loadError;
  JsonMap? _generation;
  Timer? _pollTimer;
  Timer? _cooldownTimer;
  bool _resetting = false;
  bool _retryingGeneration = false;
  bool _notifiedPlanReady = false;
  bool _pollInFlight = false;

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
      final trackedJobId = ref.read(appStateProvider).pendingGenerationJobId;
      if (managePolling && trackedJobId != null) {
        _startPolling(trackedJobId);
        return;
      }
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
    final jobId = await Navigator.of(context, rootNavigator: true).push<String>(
      MaterialPageRoute<String>(
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
    if (_pollInFlight) return;
    _pollInFlight = true;
    try {
      final status = await _repository.generationStatus(jobId);
      if (!mounted) return;
      final state = status['status'] as String?;
      final readyWeeks = status['ready_weeks'] as int? ?? 0;
      setState(() => _generation = status);
      _syncCooldownTimer(_retryAtFromMap(status));
      if (state == 'failed') {
        _pollTimer?.cancel();
        return;
      }
      if (!_isGenerating(state) && readyWeeks > 0) {
        _pollTimer?.cancel();
        ref.read(appStateProvider).clearTrackedPlanGeneration(jobId);
        await _loadPlan(showLoader: false, managePolling: false);
        return;
      }
      if (!_isGenerating(state)) _pollTimer?.cancel();
    } catch (error) {
      if (mounted) setState(() => _loadError = error);
      _pollTimer?.cancel();
    } finally {
      _pollInFlight = false;
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
    final result = await Navigator.of(context, rootNavigator: true)
        .push<LessonResult>(
          MaterialPageRoute<LessonResult>(
            builder: (context) => InteractiveLessonScreen(
              lesson: lesson,
              completedActivityIds:
                  document
                      .progress
                      .lessonStates[lesson.id]
                      ?.completedActivityIds
                      .toSet() ??
                  const {},
              pronunciationActivityProgress:
                  document
                      .progress
                      .lessonStates[lesson.id]
                      ?.pronunciationActivityProgress ??
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
}
