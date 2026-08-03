import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

import '../../../../app/providers.dart';
import '../../../../core/theme/app_colors.dart';
import '../../data/plp_repository.dart';
import '../../domain/plp_models.dart';

part 'lesson_controller.dart';
part 'lesson_content_widgets.dart';
part 'lesson_pronunciation_widgets.dart';
part 'lesson_question_widgets.dart';
part 'lesson_completion_widgets.dart';
part 'lesson_guided_speaking_page.dart';
part 'lesson_pronunciation_page.dart';
part 'lesson_feedback_widgets.dart';
part 'lesson_common_widgets.dart';

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
  void _update(VoidCallback change) => setState(change);

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
  final Map<String, JsonMap> _guidedSpeakingResults = {};
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
}
