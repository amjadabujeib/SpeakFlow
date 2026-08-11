import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:speakflow/core/theme/local_fonts.dart';

import 'roleplay_feedback_data.dart';

part 'roleplay_session_summary_sections.dart';

const _background = Color(0xFF090E1A);
const _surface = Color(0xFF111827);
const _card = Color(0xFF1A2235);
const _primary = Color(0xFF4F7FFF);
const _accent = Color(0xFF8B5CF6);
const _success = Color(0xFF22C55E);
const _warning = Color(0xFFF59E0B);
const _text = Color(0xFFF1F5FF);
const _muted = Color(0xFF8896B0);
const _border = Color(0xFF263550);

class SessionFeedbackScreen extends StatelessWidget {
  final RoleplayFeedbackData feedback;

  const SessionFeedbackScreen({super.key, required this.feedback});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _background,
      appBar: AppBar(
        automaticallyImplyLeading: false,
        backgroundColor: _surface,
        elevation: 0,
        title: Text(
          'Session summary',
          style: GoogleFonts.inter(
            color: _text,
            fontSize: 18,
            fontWeight: FontWeight.w700,
          ),
        ),
        actions: [
          IconButton(
            tooltip: 'Close',
            onPressed: () => context.go('/chat'),
            icon: const Icon(Icons.close_rounded, color: _text),
          ),
        ],
        bottom: const PreferredSize(
          preferredSize: Size.fromHeight(1),
          child: Divider(height: 1, color: _border),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 34),
        children: [
          _SummaryHero(feedback: feedback),
          const SizedBox(height: 18),
          _EvidenceNotice(feedback: feedback),
          const SizedBox(height: 18),
          _ScoreGrid(feedback: feedback),
          if (feedback.scenarioEvidence.isNotEmpty) ...[
            const SizedBox(height: 18),
            _ScenarioEvidenceSection(items: feedback.scenarioEvidence),
          ],
          if (feedback.corrections.isNotEmpty) ...[
            const SizedBox(height: 18),
            _CorrectionSection(corrections: feedback.corrections),
          ],
          if (feedback.practiceWordsAdded > 0) ...[
            const SizedBox(height: 18),
            _PracticeListNotice(count: feedback.practiceWordsAdded),
          ],
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}

class _SummaryHero extends StatelessWidget {
  final RoleplayFeedbackData feedback;

  const _SummaryHero({required this.feedback});

  @override
  Widget build(BuildContext context) {
    final minutes = feedback.durationSeconds ~/ 60;
    final seconds = feedback.durationSeconds % 60;
    return Container(
      padding: const EdgeInsets.all(21),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            _primary.withValues(alpha: .24),
            _accent.withValues(alpha: .18),
          ],
        ),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: _primary.withValues(alpha: .3)),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 48,
                height: 48,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: _surface.withValues(alpha: .65),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Text(
                  feedback.icon,
                  style: const TextStyle(fontSize: 23),
                ),
              ),
              const SizedBox(width: 13),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      feedback.scenario,
                      style: GoogleFonts.inter(
                        color: _text,
                        fontSize: 19,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Icon(
                          feedback.objectiveCompleted
                              ? Icons.check_circle_rounded
                              : Icons.timelapse_rounded,
                          size: 15,
                          color: feedback.objectiveCompleted
                              ? _success
                              : _warning,
                        ),
                        const SizedBox(width: 5),
                        Expanded(
                          child: Text(
                            feedback.objectiveCompleted
                                ? 'Conversation goals completed'
                                : 'Practice ended before every goal',
                            style: GoogleFonts.inter(
                              color: feedback.objectiveCompleted
                                  ? _success
                                  : _warning,
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 17),
          const Divider(height: 1, color: _border),
          const SizedBox(height: 14),
          Row(
            children: [
              _Stat(
                icon: Icons.chat_bubble_outline_rounded,
                value: '${feedback.messageCount}',
                label: 'turns',
              ),
              const SizedBox(width: 24),
              _Stat(
                icon: Icons.schedule_rounded,
                value: '$minutes:${seconds.toString().padLeft(2, '0')}',
                label: 'session time',
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  final IconData icon;
  final String value;
  final String label;

  const _Stat({required this.icon, required this.value, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, color: _primary, size: 17),
        const SizedBox(width: 7),
        Text(
          '$value $label',
          style: GoogleFonts.inter(
            color: _text,
            fontSize: 12,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

class _ScoreGrid extends StatelessWidget {
  final RoleplayFeedbackData feedback;

  const _ScoreGrid({required this.feedback});

  static const _dimensions = <(String, String, Color)>[
    ('task_achievement', 'Goals', _primary),
    ('interaction', 'Interaction', _accent),
    ('grammar_control', 'Grammar', _success),
    ('vocabulary_function', 'Vocabulary', _warning),
    ('delivery_fluency', 'Speaking fluency', Color(0xFF38BDF8)),
  ];

  @override
  Widget build(BuildContext context) {
    final visible = _dimensions
        .where((item) => feedback.scores[item.$1] != null)
        .toList(growable: false);
    if (visible.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Performance',
          style: GoogleFonts.inter(
            color: _text,
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 10),
        GridView.count(
          crossAxisCount: 2,
          mainAxisSpacing: 10,
          crossAxisSpacing: 10,
          childAspectRatio: 2.25,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          children: [
            for (final item in visible)
              _DimensionCard(
                label: item.$2,
                value: feedback.scores[item.$1]!,
                color: item.$3,
              ),
          ],
        ),
      ],
    );
  }
}

class _DimensionCard extends StatelessWidget {
  final String label;
  final int value;
  final Color color;

  const _DimensionCard({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 10),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(15),
        border: Border.all(color: _border),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 45,
            height: 45,
            child: CustomPaint(
              painter: _RingPainter(value / 100, color),
              child: Center(
                child: Text(
                  '$value',
                  style: GoogleFonts.inter(
                    color: _text,
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              label,
              style: GoogleFonts.inter(
                color: _muted,
                fontSize: 11,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PracticeListNotice extends StatelessWidget {
  final int count;

  const _PracticeListNotice({required this.count});

  @override
  Widget build(BuildContext context) {
    final noun = count == 1 ? 'word' : 'words';
    return Container(
      key: const ValueKey('roleplay-practice-words-added'),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: _primary.withValues(alpha: .09),
        borderRadius: BorderRadius.circular(15),
        border: Border.all(color: _primary.withValues(alpha: .3)),
      ),
      child: Row(
        children: [
          const Icon(Icons.playlist_add_check_rounded, color: _primary),
          const SizedBox(width: 11),
          Expanded(
            child: Text(
              '$count $noun needing pronunciation checks '
              '${count == 1 ? 'was' : 'were'} moved to your Practice list.',
              style: GoogleFonts.inter(
                color: _text,
                fontSize: 12,
                fontWeight: FontWeight.w600,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  final double progress;
  final Color color;

  const _RingPainter(this.progress, this.color);

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2 - 4;
    final background = Paint()
      ..color = color.withValues(alpha: .13)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5;
    final foreground = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round;
    canvas.drawCircle(center, radius, background);
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -math.pi / 2,
      2 * math.pi * progress.clamp(0, 1),
      false,
      foreground,
    );
  }

  @override
  bool shouldRepaint(covariant _RingPainter oldDelegate) =>
      oldDelegate.progress != progress || oldDelegate.color != color;
}
