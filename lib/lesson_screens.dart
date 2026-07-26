import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

import 'core/theme/app_colors.dart';
import 'plp/plp_models.dart';
import 'plp/plp_repository.dart';

class LessonResult {
  final int? score;
  final int correctAnswers;
  final int totalQuestions;
  final bool passed;
  final bool newlyCompleted;
  final int xpAwarded;

  const LessonResult({
    required this.score,
    required this.correctAnswers,
    required this.totalQuestions,
    required this.passed,
    this.newlyCompleted = false,
    this.xpAwarded = 0,
  });
}

class InteractiveLessonScreen extends StatefulWidget {
  final PlpLesson lesson;
  final Future<PlpAttemptResult> Function(String, JsonMap)? submitAttempt;
  final Set<String> completedActivityIds;

  const InteractiveLessonScreen({
    super.key,
    required this.lesson,
    this.submitAttempt,
    this.completedActivityIds = const {},
  });

  @override
  State<InteractiveLessonScreen> createState() =>
      _InteractiveLessonScreenState();
}

class _InteractiveLessonScreenState extends State<InteractiveLessonScreen> {
  final PageController _pageController = PageController();
  late final String _attemptSessionId =
      'lesson_${DateTime.now().microsecondsSinceEpoch}';
  final Map<String, String> _answers = {};
  final Map<String, TextEditingController> _textControllers = {};
  final Set<String> _checkedQuestionIds = {};
  final Set<String> _correctQuestionIds = {};
  final Set<String> _initialQuestionIds = {};
  final Set<String> _initialCorrectQuestionIds = {};
  final Set<String> _correctedQuestionIds = {};
  late final Set<String> _submittedActivityIds = {
    ...widget.completedActivityIds,
  };
  final Map<String, String> _serverExplanations = {};
  final Map<String, JsonMap> _serverCorrectResponses = {};
  final Map<String, List<String>> _orderedAnswers = {};
  final Map<String, Set<String>> _passedPronunciationTargets = {};
  final AudioPlayer _audioPlayer = AudioPlayer();

  int _currentPage = 0;
  bool _showCompletion = false;
  bool _submitting = false;
  bool _reviewingMistakes = false;
  List<int> _reviewPageIndexes = const [];
  int _reviewPageCursor = 0;
  int? _serverLessonScore;
  bool _serverLessonCompleted = false;
  bool _serverNewlyCompleted = false;
  int _serverXpAwarded = 0;

  List<PlpActivity> get _activities => widget.lesson.content!.activities;

  int get _pageCount => _activities.length + 1;

  PlpActivity? get _currentActivity =>
      _currentPage == 0 ? null : _activities[_currentPage - 1];

  Set<String> get _scoredQuestionIds => {
    for (final activity in _activities)
      if (activity.required && activity.isQuestion) activity.id,
  };

  int get _questionCount => _activities
      .where((activity) => activity.required && activity.isQuestion)
      .length;

  int get _initialCorrectQuestionCount =>
      _initialCorrectQuestionIds.where(_scoredQuestionIds.contains).length;

  String get _currentPhase {
    if (_currentPage == 0) return 'Overview';
    return _activityPhaseLabel(_currentActivity!.phase);
  }

  Color get _themeColor => switch (widget.lesson.type) {
    PlpLessonType.vocabulary => AppColors.success,
    PlpLessonType.grammar => AppColors.accentLight,
    PlpLessonType.pronunciation => AppColors.warning,
    PlpLessonType.reading => AppColors.primaryLight,
    PlpLessonType.listening => const Color(0xFF22D3EE),
    PlpLessonType.speaking => const Color(0xFFFB923C),
    PlpLessonType.discourse => AppColors.accent,
    PlpLessonType.assessment => AppColors.primary,
  };

  @override
  void dispose() {
    _pageController.dispose();
    _audioPlayer.dispose();
    for (final controller in _textControllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _checkCurrentAnswer() async {
    final activity = _currentActivity;
    if (activity == null || !activity.isQuestion) return;
    if (!_hasCompleteAnswer(activity)) return;
    final answer = _answers[activity.id]?.trim();
    final ordered = _orderedAnswers[activity.id];

    bool isCorrect;
    String explanation;
    if (widget.submitAttempt case final submit?) {
      final payload = <String, dynamic>{};
      if (activity.type == PlpActivityType.multipleChoice ||
          activity.type == PlpActivityType.readingComprehension ||
          activity.type == PlpActivityType.listeningComprehension) {
        payload['selected_option_id'] = answer;
      } else if (activity.type == PlpActivityType.fillBlank) {
        payload['text_answer'] = answer;
      } else if (activity.type == PlpActivityType.sentenceOrder) {
        payload['ordered_token_ids'] = ordered;
      }
      payload['attempt_kind'] = _reviewingMistakes ? 'correction' : 'initial';
      payload['attempt_session_id'] = _attemptSessionId;
      final result = await _submitRemote(submit, activity.id, payload);
      if (result == null) return;
      _recordServerLessonResult(result);
      isCorrect = result.correct ?? result.score >= 70;
      explanation = result.explanation;
      if (result.correctResponse case final response?) {
        _serverCorrectResponses[activity.id] = response;
      }
      _submittedActivityIds.add(activity.id);
    } else {
      isCorrect = switch (activity.type) {
        PlpActivityType.multipleChoice =>
          answer == activity.data['correct_option_id'],
        PlpActivityType.fillBlank =>
          (activity.data['accepted_answers'] as List)
              .cast<String>()
              .map(_normalizeAnswer)
              .contains(_normalizeAnswer(answer!)),
        _ => false,
      };
      explanation = activity.data['explanation']?.toString() ?? '';
    }
    setState(() {
      if (!_reviewingMistakes && !_initialQuestionIds.contains(activity.id)) {
        _initialQuestionIds.add(activity.id);
        if (isCorrect) _initialCorrectQuestionIds.add(activity.id);
      }
      _checkedQuestionIds.add(activity.id);
      if (isCorrect) {
        _correctQuestionIds.add(activity.id);
        if (_reviewingMistakes) _correctedQuestionIds.add(activity.id);
      } else {
        _correctQuestionIds.remove(activity.id);
        if (_reviewingMistakes) _correctedQuestionIds.remove(activity.id);
      }
      _serverExplanations[activity.id] = explanation;
    });
  }

  bool _hasCompleteAnswer(PlpActivity activity) {
    if (activity.type != PlpActivityType.sentenceOrder) {
      return _answers[activity.id]?.trim().isNotEmpty ?? false;
    }
    final tokens = (activity.data['tokens'] as List)
        .cast<JsonMap>()
        .map((token) => token['id'] as String)
        .toSet();
    final selected = _orderedAnswers[activity.id] ?? const <String>[];
    return selected.length == tokens.length &&
        selected.toSet().length == tokens.length &&
        selected.every(tokens.contains);
  }

  String _normalizeAnswer(String value) => value
      .trim()
      .toLowerCase()
      .replaceAll(RegExp(r'\s+'), ' ')
      .replaceAll('’', "'");

  Future<void> _continue() async {
    final activity = _currentActivity;
    final submit = widget.submitAttempt;
    if (activity != null &&
        !_submittedActivityIds.contains(activity.id) &&
        submit != null) {
      final result = await _submitRemote(submit, activity.id, {
        'attempt_kind': _reviewingMistakes ? 'correction' : 'initial',
        'attempt_session_id': _attemptSessionId,
      });
      if (result == null) return;
      _recordServerLessonResult(result);
      _submittedActivityIds.add(activity.id);
      _serverExplanations[activity.id] = result.explanation;
      if (result.correctResponse case final response?) {
        _serverCorrectResponses[activity.id] = response;
      }
    }
    if (_reviewingMistakes) {
      if (_reviewPageCursor < _reviewPageIndexes.length - 1) {
        _reviewPageCursor += 1;
        _pageController.animateToPage(
          _reviewPageIndexes[_reviewPageCursor],
          duration: const Duration(milliseconds: 280),
          curve: Curves.easeOut,
        );
      } else {
        setState(() {
          _reviewingMistakes = false;
          _showCompletion = true;
        });
      }
      return;
    }
    if (_currentPage < _pageCount - 1) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 280),
        curve: Curves.easeOut,
      );
      return;
    }
    setState(() => _showCompletion = true);
  }

  void _recordServerLessonResult(PlpAttemptResult result) {
    if (result.lessonScore case final score?) {
      _serverLessonScore = score;
    }
    _serverLessonCompleted = result.lessonCompleted;
    _serverNewlyCompleted = _serverNewlyCompleted || result.newlyCompleted;
    if (result.xpAwarded > _serverXpAwarded) {
      _serverXpAwarded = result.xpAwarded;
    }
  }

  void _startMistakeReview() {
    final pages = <int>[];
    for (var index = 0; index < _activities.length; index++) {
      final activity = _activities[index];
      if (activity.required &&
          activity.isQuestion &&
          !_initialCorrectQuestionIds.contains(activity.id)) {
        pages.add(index + 1);
        _checkedQuestionIds.remove(activity.id);
        _correctQuestionIds.remove(activity.id);
        _answers.remove(activity.id);
        _orderedAnswers[activity.id]?.clear();
        _serverCorrectResponses.remove(activity.id);
        _serverExplanations.remove(activity.id);
        _textControllers[activity.id]?.clear();
      }
    }
    if (pages.isEmpty) return;
    setState(() {
      _reviewPageIndexes = pages;
      _reviewPageCursor = 0;
      _reviewingMistakes = true;
      _showCompletion = false;
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _pageController.hasClients) {
        _pageController.jumpToPage(pages.first);
      }
    });
  }

  Future<PlpAttemptResult?> _submitRemote(
    Future<PlpAttemptResult> Function(String, JsonMap) submit,
    String activityId,
    JsonMap payload,
  ) async {
    if (_submitting) return null;
    setState(() => _submitting = true);
    try {
      return await submit(activityId, payload);
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not save this activity: $error')),
        );
      }
      return null;
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_showCompletion) return _buildCompletion();
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            Expanded(
              child: PageView.builder(
                controller: _pageController,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: _pageCount,
                onPageChanged: (page) => setState(() => _currentPage = page),
                itemBuilder: (context, index) => index == 0
                    ? _buildIntroduction()
                    : _buildActivity(_activities[index - 1]),
              ),
            ),
            _buildBottomBar(),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 10, 18, 10),
      child: Row(
        children: [
          IconButton(
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.close, color: AppColors.textSecondary),
          ),
          const SizedBox(width: 4),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(10),
              child: LinearProgressIndicator(
                value: (_currentPage + 1) / _pageCount,
                minHeight: 12,
                color: _themeColor,
                backgroundColor: AppColors.surfaceElevated,
              ),
            ),
          ),
          const SizedBox(width: 14),
          Text(
            '$_currentPhase  •  ${_currentPage + 1}/$_pageCount',
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildIntroduction() {
    final goal =
        widget.lesson.canDoStatement ??
        (widget.lesson.objectives.isNotEmpty
            ? widget.lesson.objectives.first
            : 'Complete the lesson activities.');
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: _themeColor.withValues(alpha: 0.12),
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: _themeColor.withValues(alpha: 0.28),
                  ),
                ),
                child: Icon(
                  _lessonIcon(widget.lesson.type),
                  color: _themeColor,
                  size: 26,
                ),
              ),
              const SizedBox(width: 13),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _lessonTypeLabel(widget.lesson.type).toUpperCase(),
                      style: TextStyle(
                        color: _themeColor,
                        fontSize: 11,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 0.7,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      widget.lesson.title,
                      style: const TextStyle(
                        fontSize: 23,
                        height: 1.15,
                        fontWeight: FontWeight.w900,
                        color: AppColors.textPrimary,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          Text(
            widget.lesson.content!.intro,
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 15,
              height: 1.45,
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 18),
          _LessonGoalCard(color: _themeColor, goal: goal),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _MetaChip(
                icon: Icons.schedule,
                label: '${widget.lesson.estimatedMinutes} min',
              ),
              _MetaChip(
                icon: Icons.layers_outlined,
                label:
                    '${_activities.length} '
                    '${_activities.length == 1 ? 'step' : 'steps'}',
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(
                Icons.touch_app_outlined,
                size: 18,
                color: AppColors.textMuted,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  _questionCount > 0
                      ? 'Work through each step in order. Checks give you '
                            'feedback immediately.'
                      : 'Work through each short step in order, then finish '
                            'the lesson.',
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 13,
                    height: 1.4,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildActivity(PlpActivity activity) => switch (activity.type) {
    PlpActivityType.vocabularyCard => _buildVocabulary(activity),
    PlpActivityType.concept => _buildConcept(activity),
    PlpActivityType.pronunciationDrill => _buildPronunciation(activity),
    PlpActivityType.multipleChoice => _buildMultipleChoice(activity),
    PlpActivityType.fillBlank => _buildFillBlank(activity),
    PlpActivityType.readingComprehension => _buildReading(activity),
    PlpActivityType.listeningComprehension => _buildListening(activity),
    PlpActivityType.sentenceOrder => _buildSentenceOrder(activity),
    PlpActivityType.guidedSpeaking => _buildGuidedSpeaking(activity),
  };

  Widget _activityPage({
    required PlpActivity activity,
    required List<Widget> children,
  }) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(24, 18, 24, 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _ActivityPhaseBanner(
            key: ValueKey('activity-phase-${activity.id}'),
            phase: activity.phase,
          ),
          const SizedBox(height: 18),
          ...children,
        ],
      ),
    );
  }

  List<Widget> _nativeHintWidgets(JsonMap data) {
    final hint = data['native_hint'];
    if (hint is! String || hint.trim().isEmpty) return const [];
    return [
      const SizedBox(height: 18),
      _InfoPanel(
        color: AppColors.accentLight,
        icon: Icons.translate,
        title: 'Native-language hint',
        children: [hint.trim()],
      ),
    ];
  }

  Widget _buildVocabulary(PlpActivity activity) {
    final data = activity.data;
    final examples = (data['examples'] as List).cast<String>();
    final collocations = (data['collocations'] as List).cast<String>();
    return _activityPage(
      activity: activity,
      children: [
        const Text(
          'Vocabulary',
          style: TextStyle(
            color: AppColors.textSecondary,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 10),
        Card(
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(22),
            side: const BorderSide(color: AppColors.borderLight, width: 1.5),
          ),
          child: Padding(
            padding: const EdgeInsets.all(26),
            child: Column(
              children: [
                Text(
                  data['word'] as String,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: _themeColor,
                    fontSize: 34,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  '${data['part_of_speech']}  •  ${data['ipa']}',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 16,
                  ),
                ),
                const SizedBox(height: 22),
                const Divider(color: AppColors.border),
                const SizedBox(height: 18),
                Text(
                  data['definition'] as String,
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 18, height: 1.45),
                ),
              ],
            ),
          ),
        ),
        ..._nativeHintWidgets(data),
        const SizedBox(height: 22),
        const _SectionTitle('In context'),
        const SizedBox(height: 10),
        for (final example in examples)
          _ExampleCard(icon: Icons.format_quote, text: example),
        if (collocations.isNotEmpty) ...[
          const SizedBox(height: 12),
          const _SectionTitle('Natural combinations'),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: collocations
                .map(
                  (item) => Chip(
                    label: Text(item),
                    backgroundColor: _themeColor.withValues(alpha: 0.08),
                    side: BorderSide(
                      color: _themeColor.withValues(alpha: 0.18),
                    ),
                  ),
                )
                .toList(growable: false),
          ),
        ],
      ],
    );
  }

  Widget _buildConcept(PlpActivity activity) {
    final data = activity.data;
    final keyPoints = (data['key_points'] as List).cast<String>();
    final examples = (data['examples'] as List).cast<String>();
    return _activityPage(
      activity: activity,
      children: [
        Text(
          (data['title'] ?? 'Key idea') as String,
          style: const TextStyle(
            fontSize: 28,
            fontWeight: FontWeight.w900,
            color: AppColors.textPrimary,
          ),
        ),
        const SizedBox(height: 14),
        Text(
          data['explanation'] as String,
          style: const TextStyle(fontSize: 18, height: 1.5),
        ),
        ..._nativeHintWidgets(data),
        const SizedBox(height: 24),
        _InfoPanel(
          color: _themeColor,
          icon: Icons.rule,
          title: 'Key points',
          children: keyPoints,
        ),
        const SizedBox(height: 24),
        const _SectionTitle('Examples'),
        const SizedBox(height: 10),
        for (final example in examples)
          _ExampleCard(icon: Icons.chat_bubble_outline, text: example),
      ],
    );
  }

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
          onPressed: () => _audioPlayer.play(
            UrlSource(
              'http://127.0.0.1:8000/api/tts?text='
              '${Uri.encodeQueryComponent(target)}',
            ),
          ),
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
    setState(() {
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

  Widget _buildMultipleChoice(PlpActivity activity) {
    final data = activity.data;
    final options = (data['options'] as List).cast<Map<String, dynamic>>();
    final selected = _answers[activity.id];
    final checked = _checkedQuestionIds.contains(activity.id);
    final correctId =
        data['correct_option_id'] as String? ??
        _serverCorrectResponses[activity.id]?['selected_option_id'] as String?;
    return _activityPage(
      activity: activity,
      children: [
        const _QuestionLabel(hint: 'Choose one answer.'),
        const SizedBox(height: 16),
        Text(
          data['prompt'] as String,
          style: const TextStyle(
            fontSize: 23,
            height: 1.35,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 24),
        for (final option in options)
          _AnswerOption(
            label: option['text'] as String,
            selected: selected == option['id'],
            correct:
                checked &&
                ((correctId != null && option['id'] == correctId) ||
                    (correctId == null &&
                        selected == option['id'] &&
                        _correctQuestionIds.contains(activity.id))),
            incorrect:
                checked &&
                selected == option['id'] &&
                !_correctQuestionIds.contains(activity.id),
            enabled: !checked,
            themeColor: _themeColor,
            onTap: () =>
                setState(() => _answers[activity.id] = option['id'] as String),
          ),
        if (checked)
          _AnswerExplanation(
            isCorrect: _correctQuestionIds.contains(activity.id),
            text:
                _serverExplanations[activity.id] ??
                data['explanation'] as String,
          ),
      ],
    );
  }

  Widget _buildFillBlank(PlpActivity activity) {
    final data = activity.data;
    final checked = _checkedQuestionIds.contains(activity.id);
    final isCorrect = _correctQuestionIds.contains(activity.id);
    final controller = _textControllers.putIfAbsent(
      activity.id,
      () => TextEditingController(text: _answers[activity.id]),
    );
    final explanation =
        _serverExplanations[activity.id] ?? data['explanation'] as String;
    final expectedAnswer =
        _serverCorrectResponses[activity.id]?['text_answer'] ??
        (data['accepted_answers'] is List &&
                (data['accepted_answers'] as List).isNotEmpty
            ? (data['accepted_answers'] as List).first
            : null);
    return _activityPage(
      activity: activity,
      children: [
        const _QuestionLabel(hint: 'Complete the one missing answer.'),
        const SizedBox(height: 16),
        Text(
          data['prompt'] as String,
          style: const TextStyle(
            fontSize: 23,
            height: 1.4,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 26),
        TextField(
          controller: controller,
          enabled: !checked,
          autocorrect: false,
          style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w700),
          decoration: InputDecoration(
            hintText: 'Type the missing word or phrase',
            filled: true,
            fillColor: checked
                ? (isCorrect
                      ? Colors.green.withValues(alpha: 0.12)
                      : Colors.red.withValues(alpha: 0.12))
                : AppColors.surfaceElevated,
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(16)),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: const BorderSide(
                color: AppColors.borderLight,
                width: 1.5,
              ),
            ),
            disabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: BorderSide(
                color: isCorrect ? Colors.green : Colors.red,
                width: 2,
              ),
            ),
            contentPadding: const EdgeInsets.all(19),
          ),
          onChanged: (value) => setState(() => _answers[activity.id] = value),
        ),
        if (checked)
          _AnswerExplanation(
            isCorrect: isCorrect,
            text: !isCorrect && expectedAnswer != null
                ? 'Expected answer: $expectedAnswer\n\n$explanation'
                : explanation,
          ),
      ],
    );
  }

  Widget _buildReading(PlpActivity activity) {
    final data = activity.data;
    return _activityPage(
      activity: activity,
      children: [
        Text(
          data['title'] as String,
          style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 14),
        Container(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            color: AppColors.surfaceCard,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.borderLight),
          ),
          child: Text(
            data['passage'] as String,
            style: const TextStyle(fontSize: 17, height: 1.55),
          ),
        ),
        const SizedBox(height: 22),
        ..._nestedQuestionWidgets(activity, data['question'] as JsonMap),
      ],
    );
  }

  Widget _buildListening(PlpActivity activity) {
    final data = activity.data;
    return _activityPage(
      activity: activity,
      children: [
        Text(
          data['title'] as String,
          style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: data['transcript'] is String
              ? () => _audioPlayer.play(
                  UrlSource(
                    'http://127.0.0.1:8000/api/tts?text='
                    '${Uri.encodeQueryComponent(data['transcript'] as String)}',
                  ),
                )
              : null,
          icon: const Icon(Icons.play_arrow),
          label: const Text('PLAY LISTENING'),
        ),
        const SizedBox(height: 22),
        ..._nestedQuestionWidgets(activity, data['question'] as JsonMap),
      ],
    );
  }

  List<Widget> _nestedQuestionWidgets(PlpActivity activity, JsonMap question) {
    final options = (question['options'] as List).cast<JsonMap>();
    final selected = _answers[activity.id];
    final checked = _checkedQuestionIds.contains(activity.id);
    final isCorrect = _correctQuestionIds.contains(activity.id);
    final correctId =
        question['correct_option_id'] as String? ??
        _serverCorrectResponses[activity.id]?['selected_option_id'] as String?;
    return [
      const _QuestionLabel(hint: 'Choose one answer from the text.'),
      const SizedBox(height: 12),
      Text(
        question['prompt'] as String,
        style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
      ),
      const SizedBox(height: 18),
      for (final option in options)
        _AnswerOption(
          label: option['text'] as String,
          selected: selected == option['id'],
          correct: checked && correctId == option['id'],
          incorrect: checked && !isCorrect && selected == option['id'],
          enabled: !checked,
          themeColor: _themeColor,
          onTap: () =>
              setState(() => _answers[activity.id] = option['id'] as String),
        ),
      if (checked)
        _AnswerExplanation(
          isCorrect: isCorrect,
          text:
              _serverExplanations[activity.id] ??
              question['explanation'] as String,
        ),
    ];
  }

  Widget _buildSentenceOrder(PlpActivity activity) {
    final data = activity.data;
    final tokens = (data['tokens'] as List).cast<JsonMap>();
    final selected = _orderedAnswers.putIfAbsent(activity.id, () => []);
    final checked = _checkedQuestionIds.contains(activity.id);
    final serverCorrectOrder =
        _serverCorrectResponses[activity.id]?['ordered_token_ids'];
    String textFor(String id) =>
        tokens.firstWhere((item) => item['id'] == id)['text'] as String;
    return _activityPage(
      activity: activity,
      children: [
        const _QuestionLabel(hint: 'Use every chunk once.'),
        const SizedBox(height: 14),
        Text(
          data['prompt'] as String,
          style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 18),
        Container(
          constraints: const BoxConstraints(minHeight: 70),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppColors.surfaceCard,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: AppColors.borderLight),
          ),
          child: Wrap(
            spacing: 7,
            runSpacing: 7,
            children: selected
                .map((id) => Chip(label: Text(textFor(id))))
                .toList(),
          ),
        ),
        const SizedBox(height: 14),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: tokens
              .where((item) => !selected.contains(item['id']))
              .map(
                (item) => ActionChip(
                  label: Text(item['text'] as String),
                  onPressed: checked
                      ? null
                      : () => setState(() {
                          selected.add(item['id'] as String);
                          _answers[activity.id] = 'ordered';
                        }),
                ),
              )
              .toList(),
        ),
        if (!checked && selected.isNotEmpty)
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton(
              onPressed: () => setState(() {
                selected.clear();
                _answers.remove(activity.id);
              }),
              child: const Text('RESET ORDER'),
            ),
          ),
        if (checked)
          _AnswerExplanation(
            isCorrect: _correctQuestionIds.contains(activity.id),
            text:
                _serverExplanations[activity.id] ??
                data['explanation'] as String,
          ),
        if (checked && serverCorrectOrder is List<dynamic>)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: _InfoPanel(
              color: Colors.green,
              icon: Icons.check_circle_outline,
              title: 'Correct order',
              children: [
                serverCorrectOrder.map((id) => textFor(id as String)).join(' '),
              ],
            ),
          ),
      ],
    );
  }

  Widget _buildGuidedSpeaking(PlpActivity activity) {
    final data = activity.data;
    final expressions = (data['target_expressions'] as List).cast<String>();
    return _activityPage(
      activity: activity,
      children: [
        const Text(
          'Guided speaking',
          style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
        ),
        const SizedBox(height: 10),
        Text(
          data['prompt'] as String,
          style: const TextStyle(fontSize: 25, fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 16),
        _InfoPanel(
          color: _themeColor,
          icon: Icons.lightbulb_outline,
          title: 'Prepare',
          children: [data['preparation_tip'] as String],
        ),
        const SizedBox(height: 16),
        const _SectionTitle('Try to use'),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          children: expressions.map((item) => Chip(label: Text(item))).toList(),
        ),
        const SizedBox(height: 16),
        const Text(
          'This is participation practice, not a pronunciation score. '
          'Target-free speaking assessment remains intentionally separate.',
          style: TextStyle(color: AppColors.textSecondary, height: 1.4),
        ),
      ],
    );
  }

  Widget _buildBottomBar() {
    final activity = _currentActivity;
    final isQuestion = activity?.isQuestion ?? false;
    final isChecked =
        activity != null && _checkedQuestionIds.contains(activity.id);
    final hasAnswer = activity != null && _hasCompleteAnswer(activity);
    final needsCheck = isQuestion && !isChecked;
    final needsPronunciationPass =
        activity?.type == PlpActivityType.pronunciationDrill &&
        widget.submitAttempt != null &&
        !_submittedActivityIds.contains(activity!.id);
    final enabled =
        !_submitting && !needsPronunciationPass && (!needsCheck || hasAnswer);
    final buttonLabel = needsPronunciationPass
        ? 'PASS ALL SOUND CHECKS TO CONTINUE'
        : needsCheck
        ? 'CHECK ANSWER'
        : _reviewingMistakes &&
              _reviewPageCursor == _reviewPageIndexes.length - 1
        ? 'FINISH REVIEW'
        : _currentPage == _pageCount - 1
        ? 'FINISH LESSON'
        : 'CONTINUE';

    return Container(
      padding: const EdgeInsets.fromLTRB(18, 12, 18, 16),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(top: BorderSide(color: AppColors.border)),
      ),
      child: SafeArea(
        top: false,
        child: Row(
          children: [
            if (_currentPage > 0 && !isChecked && !_reviewingMistakes)
              TextButton(
                onPressed: () => _pageController.previousPage(
                  duration: const Duration(milliseconds: 250),
                  curve: Curves.easeOut,
                ),
                child: const Text('BACK'),
              )
            else
              const SizedBox(width: 70),
            const SizedBox(width: 10),
            Expanded(
              child: SizedBox(
                height: 54,
                child: FilledButton(
                  onPressed: enabled
                      ? (needsCheck ? _checkCurrentAnswer : _continue)
                      : null,
                  style: FilledButton.styleFrom(
                    backgroundColor: _themeColor,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(15),
                    ),
                  ),
                  child: _submitting
                      ? const SizedBox.square(
                          dimension: 22,
                          child: CircularProgressIndicator(
                            strokeWidth: 2.5,
                            color: Colors.white,
                          ),
                        )
                      : Text(
                          buttonLabel,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w900,
                            letterSpacing: 0.5,
                          ),
                        ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCompletion() {
    final usesServerResult = widget.submitAttempt != null;
    final localFirstTryScore = _questionCount > 0
        ? ((_initialCorrectQuestionCount / _questionCount) * 100).round()
        : null;
    final score = usesServerResult ? _serverLessonScore : localFirstTryScore;
    final passed = usesServerResult
        ? _serverLessonCompleted
        : widget.lesson.completionPolicy.isSatisfiedBy(localFirstTryScore ?? 0);
    final newlyCompleted = usesServerResult ? _serverNewlyCompleted : passed;
    final xpAwarded = usesServerResult
        ? (newlyCompleted ? _serverXpAwarded : 0)
        : (passed ? widget.lesson.xp : 0);
    final hasScore = score != null;
    final initialMistakes = _questionCount - _initialCorrectQuestionCount;
    final correctedMistakes = _correctedQuestionIds
        .where(
          (id) =>
              _scoredQuestionIds.contains(id) &&
              !_initialCorrectQuestionIds.contains(id),
        )
        .length;
    final canReviewMistakes =
        _questionCount > 0 &&
        widget.lesson.type != PlpLessonType.assessment &&
        initialMistakes > 0;
    final completionTitle = !passed
        ? widget.lesson.type == PlpLessonType.assessment
              ? 'Checkpoint not passed yet'
              : 'Lesson not complete yet'
        : !hasScore
        ? newlyCompleted
              ? 'Activities complete'
              : 'Activities reviewed'
        : newlyCompleted
        ? 'Lesson complete'
        : 'Lesson reviewed';
    final completionMessage = !passed
        ? widget.lesson.type == PlpLessonType.assessment
              ? score == null
                    ? 'The checkpoint remains open because no aggregate score '
                          'was returned. Review the activities and try again.'
                    : 'Your lesson score is $score%. You need '
                          '${widget.lesson.completionPolicy.minimumScore}% to '
                          'unlock the next lesson.'
              : 'The lesson is not yet marked complete. Return to the plan and '
                    'retry any unfinished required activity.'
        : !hasScore
        ? 'You completed every required activity. This lesson did not include '
              'a scored check.'
        : _questionCount == 0
        ? 'Your lesson result was recorded.'
        : initialMistakes == 0
        ? 'You retrieved every answer correctly on the first try.'
        : canReviewMistakes
        ? 'First try: $_initialCorrectQuestionCount of $_questionCount correct. '
              'Correct the missed items now; the checkpoint will test them '
              'again later.'
        : 'You answered $_initialCorrectQuestionCount of $_questionCount '
              'correctly. Review the feedback, then retry the full checkpoint.';
    final minimumScore = widget.lesson.completionPolicy.minimumScore;
    final resultLabel = score == null
        ? passed
              ? xpAwarded > 0
                    ? 'Completion recorded  •  +$xpAwarded XP'
                    : 'Completion recorded'
              : 'Completion not confirmed'
        : passed
        ? xpAwarded > 0
              ? 'Score $score%  •  +$xpAwarded XP'
              : 'Score $score%'
        : minimumScore == null
        ? 'Score $score%'
        : 'Score $score%  •  Need $minimumScore%';
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Spacer(),
              Icon(
                !passed
                    ? Icons.refresh_rounded
                    : !hasScore
                    ? Icons.task_alt
                    : newlyCompleted
                    ? Icons.emoji_events
                    : Icons.check_circle_outline,
                color: _themeColor,
                size: 104,
              ),
              const SizedBox(height: 24),
              Text(
                completionTitle,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 34,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                completionMessage,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: AppColors.textSecondary,
                  fontSize: 18,
                ),
              ),
              const SizedBox(height: 24),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 24,
                  vertical: 14,
                ),
                decoration: BoxDecoration(
                  color: AppColors.surfaceCard,
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(
                    color: _themeColor.withValues(alpha: 0.42),
                  ),
                ),
                child: Text(
                  resultLabel,
                  style: TextStyle(
                    color: _themeColor,
                    fontSize: 20,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              if (correctedMistakes > 0) ...[
                const SizedBox(height: 12),
                Text(
                  'Corrected after feedback: $correctedMistakes of $initialMistakes',
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
              const Spacer(),
              if (canReviewMistakes) ...[
                SizedBox(
                  width: double.infinity,
                  height: 54,
                  child: OutlinedButton.icon(
                    onPressed: _startMistakeReview,
                    icon: const Icon(Icons.replay),
                    label: Text(
                      correctedMistakes == initialMistakes
                          ? 'PRACTISE MISTAKES AGAIN'
                          : 'CORRECT $initialMistakes MISSED '
                                '${initialMistakes == 1 ? 'ITEM' : 'ITEMS'}',
                    ),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppColors.primaryLight,
                      side: const BorderSide(color: AppColors.primary),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
              ],
              SizedBox(
                width: double.infinity,
                height: 56,
                child: FilledButton(
                  onPressed: () => Navigator.pop(
                    context,
                    LessonResult(
                      score: score,
                      correctAnswers: _initialCorrectQuestionCount,
                      totalQuestions: _questionCount,
                      passed: passed,
                      newlyCompleted: newlyCompleted,
                      xpAwarded: xpAwarded,
                    ),
                  ),
                  style: FilledButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                  ),
                  child: const Text(
                    'RETURN TO PLAN',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900),
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

class _LessonPronunciationPracticePage extends StatefulWidget {
  final String initialTarget;
  final List<String> assignedTargets;
  final String? activityId;
  final String attemptSessionId;

  const _LessonPronunciationPracticePage({
    required this.initialTarget,
    required this.assignedTargets,
    required this.activityId,
    required this.attemptSessionId,
  });

  @override
  State<_LessonPronunciationPracticePage> createState() =>
      _LessonPronunciationPracticePageState();
}

class _LessonPronunciationPracticePageState
    extends State<_LessonPronunciationPracticePage> {
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();

  bool _recording = false;
  bool _processing = false;
  bool _playing = false;
  JsonMap? _result;
  PlpAttemptResult? _lessonAttempt;
  String? _error;

  String get _target => widget.initialTarget.trim();

  @override
  void dispose() {
    _recorder.dispose();
    _player.dispose();
    super.dispose();
  }

  Future<void> _playTarget() async {
    if (_target.isEmpty || _playing) return;
    setState(() {
      _playing = true;
      _error = null;
    });
    try {
      await _player.play(
        UrlSource(
          'http://127.0.0.1:8000/api/tts?text='
          '${Uri.encodeQueryComponent(_target)}',
        ),
      );
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Kokoro playback could not be started.');
      }
    } finally {
      if (mounted) setState(() => _playing = false);
    }
  }

  Future<void> _startRecording() async {
    if (_target.isEmpty) {
      setState(() => _error = 'Enter a word or sentence first.');
      return;
    }
    final permission = await Permission.microphone.request();
    if (permission != PermissionStatus.granted ||
        !await _recorder.hasPermission()) {
      if (mounted) {
        setState(() => _error = 'Microphone permission is required.');
      }
      return;
    }
    final directory = await getTemporaryDirectory();
    final path =
        '${directory.path}/lesson_pronunciation_'
        '${DateTime.now().microsecondsSinceEpoch}.wav';
    await _recorder.start(
      const RecordConfig(
        encoder: AudioEncoder.wav,
        sampleRate: 16000,
        numChannels: 1,
      ),
      path: path,
    );
    if (!mounted) return;
    setState(() {
      _recording = true;
      _result = null;
      _lessonAttempt = null;
      _error = null;
    });
  }

  Future<void> _stopAndScore() async {
    final path = await _recorder.stop();
    if (!mounted) return;
    setState(() {
      _recording = false;
      _processing = true;
      _error = null;
    });
    if (path == null) {
      setState(() {
        _processing = false;
        _error = 'The recording could not be saved.';
      });
      return;
    }
    try {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('http://127.0.0.1:8000/api/pronunciation'),
      );
      request.fields['target_word'] = _target;
      if (widget.activityId != null) {
        request.fields['activity_id'] = widget.activityId!;
        request.fields['attempt_session_id'] = widget.attemptSessionId;
      }
      request.files.add(await http.MultipartFile.fromPath('file', path));
      final response = await request.send();
      final body = await response.stream.bytesToString();
      if (!mounted) return;
      if (response.statusCode != 200) {
        var message = 'Pronunciation scoring failed (${response.statusCode}).';
        try {
          final decoded = jsonDecode(body);
          if (decoded is Map && decoded['detail'] != null) {
            message = decoded['detail'].toString();
          }
        } catch (_) {}
        setState(() {
          _processing = false;
          _error = message;
        });
        return;
      }
      final decoded = jsonDecode(body);
      if (decoded is! JsonMap) {
        throw const FormatException('Pronunciation response is not an object.');
      }
      final lessonAttempt = decoded['lesson_attempt'] is JsonMap
          ? PlpAttemptResult.fromJson(decoded['lesson_attempt'] as JsonMap)
          : null;
      setState(() {
        _processing = false;
        _result = decoded;
        _lessonAttempt = lessonAttempt;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _processing = false;
        _error = 'Could not reach the local pronunciation service.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final scores = _result?['scores'] is Map
        ? Map<String, dynamic>.from(_result!['scores'] as Map)
        : null;
    final analysis = _result?['analysis'] is List
        ? _result!['analysis'] as List
        : const [];
    final targetIndex = widget.assignedTargets.indexWhere(
      (item) => item.trim().toLowerCase() == _target.toLowerCase(),
    );
    return Scaffold(
      appBar: AppBar(title: const Text('Sound check')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              key: const ValueKey('lesson-pronunciation-target'),
              padding: const EdgeInsets.fromLTRB(18, 14, 10, 14),
              decoration: BoxDecoration(
                color: AppColors.surfaceCard,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppColors.borderLight),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          targetIndex >= 0
                              ? 'TARGET ${targetIndex + 1} OF '
                                    '${widget.assignedTargets.length}'
                              : 'ASSIGNED TARGET',
                          style: const TextStyle(
                            color: AppColors.primaryLight,
                            fontSize: 11,
                            fontWeight: FontWeight.w900,
                            letterSpacing: 0.6,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          _target,
                          style: const TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 22,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    key: const ValueKey('lesson-pronunciation-tts'),
                    tooltip: 'Hear with Kokoro',
                    onPressed: _playing ? null : _playTarget,
                    icon: _playing
                        ? const SizedBox.square(
                            dimension: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.volume_up_rounded),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            const Text(
              'Listen if helpful, then record yourself saying the complete '
              'target exactly as shown.',
              style: TextStyle(color: AppColors.textSecondary, height: 1.4),
            ),
            const SizedBox(height: 26),
            Center(
              child: FilledButton.icon(
                key: const ValueKey('lesson-pronunciation-record'),
                onPressed: _processing
                    ? null
                    : (_recording ? _stopAndScore : _startRecording),
                style: FilledButton.styleFrom(
                  backgroundColor: _recording
                      ? AppColors.error
                      : AppColors.primary,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 24,
                    vertical: 16,
                  ),
                ),
                icon: _processing
                    ? const SizedBox.square(
                        dimension: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : Icon(_recording ? Icons.stop : Icons.mic),
                label: Text(
                  _processing
                      ? 'ANALYSING…'
                      : _recording
                      ? 'STOP AND SCORE'
                      : 'START RECORDING',
                ),
              ),
            ),
            if (_error case final error?) ...[
              const SizedBox(height: 18),
              _LessonPracticeMessage(
                color: Colors.red,
                icon: Icons.error_outline,
                text: error,
              ),
            ],
            if (_lessonAttempt case final attempt?) ...[
              const SizedBox(height: 18),
              _LessonPracticeMessage(
                color: attempt.correct == true ? Colors.green : Colors.orange,
                icon: attempt.correct == true ? Icons.verified : Icons.replay,
                text: attempt.explanation,
              ),
            ],
            if (scores != null) ...[
              const SizedBox(height: 24),
              Text(
                '${(scores['overall_score'] as num?)?.round() ?? 0}/100',
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 42,
                  fontWeight: FontWeight.w900,
                  color: AppColors.primaryLight,
                ),
              ),
              const Text(
                'Overall pronunciation quality',
                textAlign: TextAlign.center,
                style: TextStyle(color: AppColors.textSecondary),
              ),
              const SizedBox(height: 18),
              for (final metric in const [
                ('Accuracy', 'accuracy'),
                ('Fluency', 'fluency'),
                ('Prosody', 'prosody'),
                ('Completeness', 'completeness'),
              ])
                if (scores[metric.$2] is num)
                  _LessonScoreBar(
                    label: metric.$1,
                    score: (scores[metric.$2] as num).round(),
                  ),
            ],
            if (analysis.isNotEmpty) ...[
              const SizedBox(height: 20),
              const Text(
                'Sound feedback',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  for (final raw in analysis)
                    if (raw is Map)
                      _LessonPhoneChip(data: Map<String, dynamic>.from(raw)),
                ],
              ),
            ],
            if (_result?['feedback'] case final String feedback
                when feedback.isNotEmpty) ...[
              const SizedBox(height: 18),
              _LessonPracticeMessage(
                color: Colors.blue,
                icon: Icons.tips_and_updates_outlined,
                text: feedback,
              ),
            ],
            if (_lessonAttempt?.correct == true) ...[
              const SizedBox(height: 24),
              FilledButton.icon(
                onPressed: () => Navigator.pop(context, _lessonAttempt),
                icon: const Icon(Icons.check_circle),
                label: const Text('BACK TO TARGETS'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

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
