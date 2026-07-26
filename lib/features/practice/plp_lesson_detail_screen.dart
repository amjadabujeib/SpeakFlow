// lib/features/practice/plp_lesson_detail_screen.dart
import 'package:flutter/material.dart';
import 'package:just_talk/core/theme/local_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:go_router/go_router.dart';
import '../../core/models/plp_models.dart';
import '../../core/services/api_service.dart';

// ─────────────────────── Colors ──────────────────────────────
const _background = Color(0xFF090E1A);
const _surface = Color(0xFF111827);
const _surfaceCard = Color(0xFF1E2D45);
const _primary = Color(0xFF4F7FFF);
const _accent = Color(0xFF8B5CF6);
const _success = Color(0xFF22C55E);
const _warning = Color(0xFFF59E0B);
const _error = Color(0xFFEF4444);
const _textPrimary = Color(0xFFF1F5FF);
const _textSecondary = Color(0xFF8896B0);
const _border = Color(0xFF1E2D45);

class PLPLessonDetailScreen extends StatefulWidget {
  final Map<String, dynamic> lessonData;

  const PLPLessonDetailScreen({super.key, required this.lessonData});

  @override
  State<PLPLessonDetailScreen> createState() =>
      _PLPLessonDetailScreenState();
}

class _PLPLessonDetailScreenState
    extends State<PLPLessonDetailScreen>
    with TickerProviderStateMixin {
  late final TabController _tabController;
  late final PLPLesson _lesson;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _lesson = PLPLesson.fromJson(widget.lessonData);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _background,
      appBar: _buildAppBar(),
      body: TabBarView(
        controller: _tabController,
        children: [
          _PresentationTab(lesson: _lesson),
          _PracticeTab(lesson: _lesson),
          _ProductionTab(lesson: _lesson),
        ],
      ),
    );
  }

  AppBar _buildAppBar() {
    return AppBar(
      backgroundColor: _surface,
      elevation: 0,
      leading: IconButton(
        icon: const Icon(Icons.arrow_back_ios_new_rounded,
            color: _textPrimary, size: 20),
        onPressed: () {
          if (context.canPop()) {
            context.pop();
          } else {
            context.go('/practice');
          }
        },
      ),
      title: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _lesson.title,
            style: GoogleFonts.inter(
              fontWeight: FontWeight.w700,
              fontSize: 16,
              color: _textPrimary,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          Text(
            '${_lesson.level} • ${_lesson.topic}',
            style: GoogleFonts.inter(
              fontSize: 12,
              color: _textSecondary,
            ),
          ),
        ],
      ),
      bottom: PreferredSize(
        preferredSize: const Size.fromHeight(50),
        child: Container(
          decoration: const BoxDecoration(
            border: Border(
              bottom: BorderSide(color: _border, width: 1),
            ),
          ),
          child: TabBar(
            controller: _tabController,
            indicatorColor: _primary,
            indicatorWeight: 3,
            labelColor: _primary,
            unselectedLabelColor: _textSecondary,
            labelStyle: GoogleFonts.inter(
                fontSize: 13, fontWeight: FontWeight.w700),
            unselectedLabelStyle: GoogleFonts.inter(
                fontSize: 13, fontWeight: FontWeight.w500),
            tabs: const [
              Tab(
                  icon: Icon(Icons.menu_book_rounded, size: 18),
                  text: 'Learn'),
              Tab(
                  icon: Icon(Icons.quiz_rounded, size: 18),
                  text: 'Practice'),
              Tab(
                  icon: Icon(Icons.edit_note_rounded, size: 18),
                  text: 'Produce'),
            ],
          ),
        ),
      ),
    );
  }
}

// ══════════════════════════════════════════════════════════════
//  TAB 1: PRESENTATION
// ══════════════════════════════════════════════════════════════

class _PresentationTab extends StatelessWidget {
  final PLPLesson lesson;
  const _PresentationTab({required this.lesson});

  @override
  Widget build(BuildContext context) {
    final pres = lesson.presentation;
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 40),
      children: [
        // Vocabulary Section
        if (pres.vocabulary.isNotEmpty) ...[
          _SectionTitle(
              icon: Icons.abc_rounded,
              title: 'Vocabulary',
              count: pres.vocabulary.length),
          const SizedBox(height: 10),
          ...List.generate(pres.vocabulary.length, (i) {
            return _VocabularyCard(vocab: pres.vocabulary[i])
                .animate(
                    delay: Duration(milliseconds: 60 * i))
                .fadeIn(duration: 350.ms)
                .slideY(begin: 0.1, end: 0);
          }),
          const SizedBox(height: 24),
        ],

        // Grammar Points
        if (pres.grammarPoints.isNotEmpty) ...[
          _SectionTitle(
              icon: Icons.auto_stories_rounded,
              title: 'Grammar',
              count: pres.grammarPoints.length),
          const SizedBox(height: 10),
          ...List.generate(pres.grammarPoints.length, (i) {
            return _GrammarPointCard(
                    point: pres.grammarPoints[i])
                .animate(
                    delay: Duration(milliseconds: 60 * i + 200))
                .fadeIn(duration: 350.ms)
                .slideY(begin: 0.1, end: 0);
          }),
          const SizedBox(height: 24),
        ],

        // Example Sentences
        if (pres.exampleSentences.isNotEmpty) ...[
          _SectionTitle(
              icon: Icons.format_quote_rounded,
              title: 'Examples',
              count: pres.exampleSentences.length),
          const SizedBox(height: 10),
          ...List.generate(pres.exampleSentences.length, (i) {
            return Container(
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: _surfaceCard,
                borderRadius: BorderRadius.circular(12),
                border: Border(
                    left: BorderSide(
                        color: _primary.withOpacity(0.6),
                        width: 3)),
              ),
              child: Text(
                pres.exampleSentences[i],
                style: GoogleFonts.inter(
                  fontSize: 14,
                  color: _textPrimary,
                  height: 1.5,
                  fontStyle: FontStyle.italic,
                ),
              ),
            )
                .animate(
                    delay: Duration(milliseconds: 60 * i + 400))
                .fadeIn(duration: 300.ms);
          }),
        ],

        // Cultural Notes
        if (pres.culturalNotes != null &&
            pres.culturalNotes!.isNotEmpty) ...[
          const SizedBox(height: 20),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  _accent.withOpacity(0.12),
                  _primary.withOpacity(0.05)
                ],
              ),
              borderRadius: BorderRadius.circular(14),
              border:
                  Border.all(color: _accent.withOpacity(0.3)),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('🌍', style: TextStyle(fontSize: 20)),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment:
                        CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Cultural Notes',
                        style: GoogleFonts.inter(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: _accent,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        pres.culturalNotes!,
                        style: GoogleFonts.inter(
                          fontSize: 13,
                          color: _textSecondary,
                          height: 1.5,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ).animate().fadeIn(delay: 500.ms, duration: 400.ms),
        ],
      ],
    );
  }
}

// ── Vocabulary Card ──────────────────────────────────────────
class _VocabularyCard extends StatelessWidget {
  final PLPVocabulary vocab;
  const _VocabularyCard({required this.vocab});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: _border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                vocab.word,
                style: GoogleFonts.outfit(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: _primary,
                ),
              ),
              if (vocab.partOfSpeech != null) ...[
                const SizedBox(width: 10),
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: _accent.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    vocab.partOfSpeech!,
                    style: GoogleFonts.inter(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: _accent,
                    ),
                  ),
                ),
              ],
            ],
          ),
          const SizedBox(height: 8),
          Text(
            vocab.definition,
            style: GoogleFonts.inter(
              fontSize: 14,
              color: _textPrimary,
              height: 1.4,
            ),
          ),
          if (vocab.arabicTranslation != null) ...[
            const SizedBox(height: 6),
            Text(
              vocab.arabicTranslation!,
              style: GoogleFonts.cairo(
                fontSize: 14,
                color: _textSecondary,
              ),
              textDirection: TextDirection.rtl,
            ),
          ],
          if (vocab.exampleSentence != null) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: _primary.withOpacity(0.06),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.format_quote_rounded,
                      color: _primary.withOpacity(0.5),
                      size: 16),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      vocab.exampleSentence!,
                      style: GoogleFonts.inter(
                        fontSize: 13,
                        color: _textSecondary,
                        fontStyle: FontStyle.italic,
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// ── Grammar Point Card ───────────────────────────────────────
class _GrammarPointCard extends StatefulWidget {
  final PLPGrammarPoint point;
  const _GrammarPointCard({required this.point});

  @override
  State<_GrammarPointCard> createState() =>
      _GrammarPointCardState();
}

class _GrammarPointCardState
    extends State<_GrammarPointCard> {
  bool _expanded = true;

  @override
  Widget build(BuildContext context) {
    final p = widget.point;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: _border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          InkWell(
            onTap: () =>
                setState(() => _expanded = !_expanded),
            borderRadius: const BorderRadius.vertical(
                top: Radius.circular(14)),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                children: [
                  Icon(Icons.auto_stories_rounded,
                      color: _accent, size: 18),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      p.title,
                      style: GoogleFonts.inter(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: _textPrimary,
                      ),
                    ),
                  ),
                  AnimatedRotation(
                    turns: _expanded ? 0.5 : 0,
                    duration: const Duration(milliseconds: 250),
                    child: const Icon(
                        Icons.keyboard_arrow_down_rounded,
                        color: _textSecondary,
                        size: 22),
                  ),
                ],
              ),
            ),
          ),
          // Body
          AnimatedCrossFade(
            duration: const Duration(milliseconds: 280),
            crossFadeState: _expanded
                ? CrossFadeState.showSecond
                : CrossFadeState.showFirst,
            firstChild: const SizedBox.shrink(),
            secondChild: Padding(
              padding:
                  const EdgeInsets.fromLTRB(14, 0, 14, 14),
              child: Column(
                crossAxisAlignment:
                    CrossAxisAlignment.start,
                children: [
                  const Divider(color: _border, height: 16),
                  Text(
                    p.explanation,
                    style: GoogleFonts.inter(
                      fontSize: 14,
                      color: _textPrimary,
                      height: 1.5,
                    ),
                  ),
                  // Formula
                  if (p.formula != null &&
                      p.formula!.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: _surface,
                        borderRadius:
                            BorderRadius.circular(10),
                        border: Border.all(
                            color: _primary.withOpacity(0.3)),
                      ),
                      child: Text(
                        p.formula!,
                        style: GoogleFonts.sourceCodePro(
                          fontSize: 13,
                          color: _primary,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                  // Examples
                  if (p.examples.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Text(
                      'Examples:',
                      style: GoogleFonts.inter(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: _success,
                      ),
                    ),
                    const SizedBox(height: 6),
                    ...p.examples.map((e) => Padding(
                          padding: const EdgeInsets.only(
                              bottom: 4),
                          child: Row(
                            crossAxisAlignment:
                                CrossAxisAlignment.start,
                            children: [
                              Text('• ',
                                  style: GoogleFonts.inter(
                                      color: _success,
                                      fontSize: 14)),
                              Expanded(
                                child: Text(
                                  e,
                                  style: GoogleFonts.inter(
                                    fontSize: 13,
                                    color: _textPrimary,
                                    height: 1.4,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        )),
                  ],
                  // Common Mistakes
                  if (p.commonMistakes.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: _error.withOpacity(0.08),
                        borderRadius:
                            BorderRadius.circular(10),
                        border: Border.all(
                            color: _error.withOpacity(0.25)),
                      ),
                      child: Column(
                        crossAxisAlignment:
                            CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              const Icon(
                                  Icons.warning_rounded,
                                  color: _error,
                                  size: 16),
                              const SizedBox(width: 6),
                              Text(
                                'Common Mistakes',
                                style: GoogleFonts.inter(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w600,
                                  color: _error,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          ...p.commonMistakes.map(
                              (m) => Padding(
                                    padding:
                                        const EdgeInsets.only(
                                            bottom: 4),
                                    child: Text(
                                      '✗ $m',
                                      style:
                                          GoogleFonts.inter(
                                        fontSize: 12,
                                        color:
                                            _textSecondary,
                                        height: 1.4,
                                      ),
                                    ),
                                  )),
                        ],
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ══════════════════════════════════════════════════════════════
//  TAB 2: PRACTICE
// ══════════════════════════════════════════════════════════════

class _PracticeTab extends StatefulWidget {
  final PLPLesson lesson;
  const _PracticeTab({required this.lesson});

  @override
  State<_PracticeTab> createState() => _PracticeTabState();
}

class _PracticeTabState extends State<_PracticeTab> {
  int _currentExercise = 0;
  final Map<String, String> _userAnswers = {};
  final Map<String, Map<String, dynamic>> _results = {};
  final Map<String, bool> _checking = {};

  List<PLPExercise> get exercises =>
      widget.lesson.practice.exercises;

  Future<void> _checkAnswer(PLPExercise exercise) async {
    final answer = _userAnswers[exercise.id] ?? '';
    if (answer.trim().isEmpty) return;

    setState(() => _checking[exercise.id] = true);

    final result = await ApiService.checkExerciseAnswer(
        widget.lesson.id, exercise.id, answer);

    if (!mounted) return;
    setState(() {
      _checking[exercise.id] = false;
      _results[exercise.id] = result;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (exercises.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.quiz_rounded,
                color: _textSecondary.withOpacity(0.5),
                size: 48),
            const SizedBox(height: 12),
            Text(
              'No exercises available',
              style: GoogleFonts.inter(
                  color: _textSecondary, fontSize: 15),
            ),
          ],
        ),
      );
    }

    return Column(
      children: [
        // Progress bar
        _buildProgressBar(),
        Expanded(
          child: PageView.builder(
            itemCount: exercises.length,
            onPageChanged: (i) =>
                setState(() => _currentExercise = i),
            itemBuilder: (ctx, i) =>
                _buildExerciseView(exercises[i], i),
          ),
        ),
      ],
    );
  }

  Widget _buildProgressBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: Row(
        children: [
          Text(
            'Exercise ${_currentExercise + 1} of ${exercises.length}',
            style: GoogleFonts.inter(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: _textSecondary,
            ),
          ),
          const Spacer(),
          Text(
            '${_results.length}/${exercises.length} completed',
            style: GoogleFonts.inter(
              fontSize: 12,
              color: _primary,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildExerciseView(PLPExercise ex, int index) {
    final result = _results[ex.id];
    final isChecking = _checking[ex.id] == true;
    final answer = _userAnswers[ex.id] ?? '';

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Type badge
          Container(
            padding: const EdgeInsets.symmetric(
                horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: _accent.withOpacity(0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              _exerciseTypeLabel(ex.type),
              style: GoogleFonts.inter(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: _accent,
              ),
            ),
          ),
          const SizedBox(height: 12),

          // Instruction
          Text(
            ex.instruction,
            style: GoogleFonts.inter(
              fontSize: 14,
              color: _textSecondary,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 16),

          // Question
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: _surfaceCard,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: _border),
            ),
            child: Text(
              ex.question,
              style: GoogleFonts.inter(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: _textPrimary,
                height: 1.5,
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Answer input
          if (ex.type == 'multiple_choice' &&
              ex.options != null) ...[
            ...ex.options!.asMap().entries.map((entry) {
              final opt = entry.value;
              final isSelected = answer == opt;
              final isCorrect = result != null &&
                  result['correct_answer'] == opt;
              final isWrong = result != null &&
                  isSelected &&
                  result['is_correct'] != true;

              Color borderCol = _border;
              if (result != null) {
                if (isCorrect) borderCol = _success;
                if (isWrong) borderCol = _error;
              } else if (isSelected) {
                borderCol = _primary;
              }

              return GestureDetector(
                onTap: result == null
                    ? () => setState(() =>
                        _userAnswers[ex.id] = opt)
                    : null,
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: isSelected && result == null
                        ? _primary.withOpacity(0.1)
                        : isCorrect && result != null
                            ? _success.withOpacity(0.1)
                            : isWrong
                                ? _error.withOpacity(0.1)
                                : _surfaceCard,
                    borderRadius: BorderRadius.circular(12),
                    border:
                        Border.all(color: borderCol, width: 1.5),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          opt,
                          style: GoogleFonts.inter(
                            fontSize: 14,
                            color: _textPrimary,
                            fontWeight: isSelected
                                ? FontWeight.w600
                                : FontWeight.w400,
                          ),
                        ),
                      ),
                      if (result != null && isCorrect)
                        const Icon(Icons.check_circle_rounded,
                            color: _success, size: 20),
                      if (isWrong)
                        const Icon(Icons.cancel_rounded,
                            color: _error, size: 20),
                    ],
                  ),
                ),
              );
            }),
          ] else ...[
            TextField(
              onChanged: (v) =>
                  setState(() => _userAnswers[ex.id] = v),
              enabled: result == null,
              style: GoogleFonts.inter(
                  color: _textPrimary, fontSize: 15),
              maxLines: ex.type == 'correct_error' ? 3 : 1,
              decoration: InputDecoration(
                hintText: ex.type == 'correct_error'
                    ? 'Type the corrected sentence…'
                    : 'Type your answer…',
                hintStyle: GoogleFonts.inter(
                    color: _textSecondary, fontSize: 14),
                filled: true,
                fillColor: _surfaceCard,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide:
                      const BorderSide(color: _primary),
                ),
              ),
            ),
          ],
          const SizedBox(height: 16),

          // Hint
          if (ex.hint != null && result == null)
            GestureDetector(
              onTap: () {},
              child: Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: _warning.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.lightbulb_outline_rounded,
                        color: _warning, size: 16),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        '💡 Hint: ${ex.hint}',
                        style: GoogleFonts.inter(
                          fontSize: 12,
                          color: _warning,
                          fontStyle: FontStyle.italic,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),

          // Check button
          if (result == null) ...[
            const SizedBox(height: 16),
            GestureDetector(
              onTap: isChecking || answer.isEmpty
                  ? null
                  : () => _checkAnswer(ex),
              child: Container(
                width: double.infinity,
                height: 50,
                decoration: BoxDecoration(
                  gradient: answer.isNotEmpty
                      ? const LinearGradient(
                          colors: [_primary, _accent])
                      : null,
                  color: answer.isEmpty ? _surfaceCard : null,
                  borderRadius: BorderRadius.circular(14),
                  boxShadow: answer.isNotEmpty
                      ? [
                          BoxShadow(
                            color: _primary.withOpacity(0.3),
                            blurRadius: 12,
                            offset: const Offset(0, 4),
                          ),
                        ]
                      : null,
                ),
                child: Center(
                  child: isChecking
                      ? const SizedBox(
                          width: 22,
                          height: 22,
                          child: CircularProgressIndicator(
                            color: Colors.white,
                            strokeWidth: 2,
                          ),
                        )
                      : Text(
                          'Check Answer',
                          style: GoogleFonts.inter(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            color: answer.isNotEmpty
                                ? Colors.white
                                : _textSecondary,
                          ),
                        ),
                ),
              ),
            ),
          ],

          // Result feedback
          if (result != null) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: (result['is_correct'] == true
                        ? _success
                        : _error)
                    .withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: (result['is_correct'] == true
                          ? _success
                          : _error)
                      .withOpacity(0.3),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        result['is_correct'] == true
                            ? Icons.check_circle_rounded
                            : Icons.cancel_rounded,
                        color: result['is_correct'] == true
                            ? _success
                            : _error,
                        size: 22,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        result['is_correct'] == true
                            ? 'Correct! 🎉'
                            : 'Not quite right',
                        style: GoogleFonts.inter(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: result['is_correct'] == true
                              ? _success
                              : _error,
                        ),
                      ),
                    ],
                  ),
                  if (result['is_correct'] != true &&
                      result['correct_answer'] != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      'Correct answer: ${result['correct_answer']}',
                      style: GoogleFonts.inter(
                        fontSize: 14,
                        color: _success,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                  if (result['explanation'] != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      result['explanation'],
                      style: GoogleFonts.inter(
                        fontSize: 13,
                        color: _textSecondary,
                        height: 1.4,
                      ),
                    ),
                  ],
                ],
              ),
            )
                .animate()
                .fadeIn(duration: 350.ms)
                .scale(
                    begin: const Offset(0.95, 0.95),
                    end: const Offset(1, 1)),
          ],
        ],
      ),
    );
  }

  String _exerciseTypeLabel(String type) {
    switch (type) {
      case 'multiple_choice':
        return '🔘 Multiple Choice';
      case 'fill_blank':
        return '✏️ Fill in the Blank';
      case 'correct_error':
        return '🔍 Correct the Error';
      case 'reorder':
        return '🔄 Reorder';
      case 'match':
        return '🔗 Match';
      default:
        return '📝 Exercise';
    }
  }
}

// ══════════════════════════════════════════════════════════════
//  TAB 3: PRODUCTION
// ══════════════════════════════════════════════════════════════

class _ProductionTab extends StatefulWidget {
  final PLPLesson lesson;
  const _ProductionTab({required this.lesson});

  @override
  State<_ProductionTab> createState() => _ProductionTabState();
}

class _ProductionTabState extends State<_ProductionTab> {
  final Map<String, TextEditingController> _controllers = {};
  final Map<String, Map<String, dynamic>> _feedback = {};
  final Map<String, bool> _submitting = {};

  @override
  void dispose() {
    for (final c in _controllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  TextEditingController _getController(String taskId) {
    _controllers[taskId] ??= TextEditingController();
    return _controllers[taskId]!;
  }

  Future<void> _submitTask(PLPProductionTask task) async {
    final content = _getController(task.id).text.trim();
    if (content.isEmpty) return;

    setState(() => _submitting[task.id] = true);

    final result = await ApiService.evaluateProduction(
        widget.lesson.id, task.id, content);

    if (!mounted) return;
    setState(() {
      _submitting[task.id] = false;
      _feedback[task.id] = result;
    });
  }

  @override
  Widget build(BuildContext context) {
    final tasks = widget.lesson.production.tasks;

    if (tasks.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.edit_note_rounded,
                color: _textSecondary.withOpacity(0.5),
                size: 48),
            const SizedBox(height: 12),
            Text(
              'No production tasks available',
              style: GoogleFonts.inter(
                  color: _textSecondary, fontSize: 15),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 40),
      itemCount: tasks.length,
      itemBuilder: (ctx, i) {
        final task = tasks[i];
        return _buildTaskCard(task, i);
      },
    );
  }

  Widget _buildTaskCard(PLPProductionTask task, int index) {
    final ctrl = _getController(task.id);
    final isSubmitting = _submitting[task.id] == true;
    final feedback = _feedback[task.id];

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _border),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Type + Title
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: _primary.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(
                    _taskTypeIcon(task.type),
                    color: _primary,
                    size: 20,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment:
                        CrossAxisAlignment.start,
                    children: [
                      Text(
                        task.title,
                        style: GoogleFonts.inter(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          color: _textPrimary,
                        ),
                      ),
                      if (task.timeLimitMinutes != null)
                        Text(
                          '⏱ ${task.timeLimitMinutes} minutes',
                          style: GoogleFonts.inter(
                            fontSize: 12,
                            color: _warning,
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),

            // Description
            Text(
              task.description,
              style: GoogleFonts.inter(
                fontSize: 14,
                color: _textSecondary,
                height: 1.5,
              ),
            ),

            // Prompts
            if (task.prompts.isNotEmpty) ...[
              const SizedBox(height: 12),
              ...task.prompts.map((p) => Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Row(
                      crossAxisAlignment:
                          CrossAxisAlignment.start,
                      children: [
                        Text('💬 ',
                            style: GoogleFonts.inter(
                                fontSize: 13)),
                        Expanded(
                          child: Text(
                            p,
                            style: GoogleFonts.inter(
                              fontSize: 13,
                              color: _textPrimary,
                              height: 1.4,
                            ),
                          ),
                        ),
                      ],
                    ),
                  )),
            ],

            const SizedBox(height: 16),

            // Text area
            TextField(
              controller: ctrl,
              maxLines: 5,
              style: GoogleFonts.inter(
                  color: _textPrimary, fontSize: 14),
              enabled: feedback == null,
              decoration: InputDecoration(
                hintText: 'Write your response here…',
                hintStyle: GoogleFonts.inter(
                    color: _textSecondary, fontSize: 14),
                filled: true,
                fillColor: _surface,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide:
                      const BorderSide(color: _primary),
                ),
              ),
            ),

            // Submit button
            if (feedback == null) ...[
              const SizedBox(height: 12),
              GestureDetector(
                onTap: isSubmitting
                    ? null
                    : () => _submitTask(task),
                child: Container(
                  width: double.infinity,
                  height: 48,
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                        colors: [_primary, _accent]),
                    borderRadius: BorderRadius.circular(12),
                    boxShadow: [
                      BoxShadow(
                        color: _primary.withOpacity(0.3),
                        blurRadius: 12,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: Center(
                    child: isSubmitting
                        ? const SizedBox(
                            width: 22,
                            height: 22,
                            child: CircularProgressIndicator(
                              color: Colors.white,
                              strokeWidth: 2,
                            ),
                          )
                        : Text(
                            'Submit for AI Evaluation ✨',
                            style: GoogleFonts.inter(
                              fontSize: 14,
                              fontWeight: FontWeight.w700,
                              color: Colors.white,
                            ),
                          ),
                  ),
                ),
              ),
            ],

            // Feedback
            if (feedback != null) ...[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      _success.withOpacity(0.1),
                      _primary.withOpacity(0.05)
                    ],
                  ),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                      color: _success.withOpacity(0.3)),
                ),
                child: Column(
                  crossAxisAlignment:
                      CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(
                            Icons.auto_awesome_rounded,
                            color: _success,
                            size: 18),
                        const SizedBox(width: 8),
                        Text(
                          'AI Feedback',
                          style: GoogleFonts.inter(
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                            color: _success,
                          ),
                        ),
                        if (feedback['score'] != null) ...[
                          const Spacer(),
                          Container(
                            padding:
                                const EdgeInsets.symmetric(
                                    horizontal: 10,
                                    vertical: 4),
                            decoration: BoxDecoration(
                              color: _success
                                  .withOpacity(0.2),
                              borderRadius:
                                  BorderRadius.circular(8),
                            ),
                            child: Text(
                              '${feedback['score']}%',
                              style: GoogleFonts.inter(
                                fontSize: 14,
                                fontWeight: FontWeight.w700,
                                color: _success,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 10),
                    Text(
                      feedback['feedback']?.toString() ??
                          feedback['evaluation']
                              ?.toString() ??
                          'Evaluation complete.',
                      style: GoogleFonts.inter(
                        fontSize: 13,
                        color: _textPrimary,
                        height: 1.5,
                      ),
                    ),
                  ],
                ),
              )
                  .animate()
                  .fadeIn(duration: 400.ms)
                  .slideY(begin: 0.05, end: 0),
            ],
          ],
        ),
      ),
    ).animate(delay: Duration(milliseconds: 80 * index)).fadeIn(
        duration: 350.ms);
  }

  IconData _taskTypeIcon(String type) {
    switch (type) {
      case 'speaking':
        return Icons.mic_rounded;
      case 'writing':
        return Icons.edit_rounded;
      case 'discussion':
        return Icons.chat_rounded;
      case 'role_play':
        return Icons.theater_comedy_rounded;
      default:
        return Icons.assignment_rounded;
    }
  }
}

// ── Shared Widgets ───────────────────────────────────────────

class _SectionTitle extends StatelessWidget {
  final IconData icon;
  final String title;
  final int count;

  const _SectionTitle({
    required this.icon,
    required this.title,
    required this.count,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, color: _primary, size: 20),
        const SizedBox(width: 8),
        Text(
          title,
          style: GoogleFonts.inter(
            fontSize: 17,
            fontWeight: FontWeight.w700,
            color: _textPrimary,
          ),
        ),
        const SizedBox(width: 8),
        Container(
          width: 24,
          height: 24,
          decoration: const BoxDecoration(
            gradient: LinearGradient(
                colors: [_primary, _accent]),
            shape: BoxShape.circle,
          ),
          alignment: Alignment.center,
          child: Text(
            '$count',
            style: GoogleFonts.inter(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: Colors.white,
            ),
          ),
        ),
      ],
    );
  }
}
