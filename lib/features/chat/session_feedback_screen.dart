import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:go_router/go_router.dart';
import 'dart:math' as math;

// ─────────────────────────────────────────────
// Colors
// ─────────────────────────────────────────────

const _background    = Color(0xFF090E1A);
const _surface       = Color(0xFF111827);
const _surfaceCard   = Color(0xFF1A2235);
// ignore: unused_element
const _surfaceCard2  = Color(0xFF1E2D45);
const _primary       = Color(0xFF4F7FFF);
const _accent        = Color(0xFF8B5CF6);
const _success       = Color(0xFF22C55E);
const _warning       = Color(0xFFF59E0B);
const _error         = Color(0xFFEF4444);
const _textPrimary   = Color(0xFFF1F5FF);
const _textSecondary = Color(0xFF8896B0);
const _border        = Color(0xFF1E2D45);

// ─────────────────────────────────────────────
// Session Feedback Screen
// ─────────────────────────────────────────────

class SessionFeedbackScreen extends StatelessWidget {
  const SessionFeedbackScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _background,
      appBar: _buildAppBar(context),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _HeroCard().animate().fadeIn(duration: 400.ms).slideY(begin: -0.05, end: 0),
            const SizedBox(height: 20),
            _ScoreCirclesRow().animate().fadeIn(delay: 150.ms, duration: 400.ms),
            const SizedBox(height: 20),
            _GrammarErrorCard().animate().fadeIn(delay: 250.ms, duration: 400.ms),
            const SizedBox(height: 20),
            _MispronounceSection().animate().fadeIn(delay: 350.ms, duration: 400.ms),
            const SizedBox(height: 20),
            _CorrectionsSection().animate().fadeIn(delay: 450.ms, duration: 400.ms),
            const SizedBox(height: 20),
            _PhonemeSection().animate().fadeIn(delay: 550.ms, duration: 400.ms),
            const SizedBox(height: 28),
            _SaveWordsButton(onTap: () => context.go('/practice')),
          ],
        ),
      ),
    );
  }

  AppBar _buildAppBar(BuildContext context) {
    return AppBar(
      backgroundColor: _surface,
      elevation: 0,
      automaticallyImplyLeading: false,
      title: Text(
        'Session Summary',
        style: GoogleFonts.inter(
          color: _textPrimary,
          fontWeight: FontWeight.w700,
          fontSize: 18,
        ),
      ),
      actions: [
        IconButton(
          icon: const Icon(Icons.close_rounded, color: _textPrimary),
          onPressed: () => context.go('/home'),
        ),
      ],
      bottom: PreferredSize(
        preferredSize: const Size.fromHeight(1),
        child: Container(height: 1, color: _border),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Hero Card
// ─────────────────────────────────────────────

class _HeroCard extends StatelessWidget {
  const _HeroCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [_primary.withOpacity(0.25), _accent.withOpacity(0.2)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: _primary.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(colors: [_primary, _accent]),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Text('✈️', style: TextStyle(fontSize: 22)),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Airport Check-in',
                      style: GoogleFonts.inter(
                        color: _textPrimary,
                        fontWeight: FontWeight.w800,
                        fontSize: 20,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      'Session completed',
                      style: GoogleFonts.inter(color: _textSecondary, fontSize: 13),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          const Divider(color: Color(0xFF1E2D45), height: 1),
          const SizedBox(height: 14),
          Row(
            children: [
              _StatItem(label: 'Duration', value: '8 min 34 sec', icon: Icons.timer_outlined),
              const SizedBox(width: 24),
              _StatItem(label: 'Messages', value: '5 exchanges', icon: Icons.chat_bubble_outline_rounded),
              const SizedBox(width: 24),
              _StatItem(label: 'Errors', value: '4 found', icon: Icons.warning_amber_rounded),
            ],
          ),
        ],
      ),
    );
  }
}

class _StatItem extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  const _StatItem({required this.label, required this.value, required this.icon});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(icon, color: _primary, size: 14),
            const SizedBox(width: 4),
            Text(label, style: GoogleFonts.inter(color: _textSecondary, fontSize: 11)),
          ],
        ),
        const SizedBox(height: 3),
        Text(value, style: GoogleFonts.inter(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 13)),
      ],
    );
  }
}

// ─────────────────────────────────────────────
// Score circles row
// ─────────────────────────────────────────────

class _ScoreCirclesRow extends StatelessWidget {
  const _ScoreCirclesRow();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(child: _ScoreCircle(label: 'Pronunciation', score: 71, color: _primary)),
        const SizedBox(width: 12),
        Expanded(child: _ScoreCircle(label: 'Fluency', score: 65, color: _accent)),
        const SizedBox(width: 12),
        Expanded(child: _ScoreCircle(label: 'Lexical', score: 78, color: _success)),
      ],
    );
  }
}

class _ScoreCircle extends StatelessWidget {
  final String label;
  final int score;
  final Color color;
  const _ScoreCircle({required this.label, required this.score, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 8),
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: _border),
      ),
      child: Column(
        children: [
          SizedBox(
            width: 72,
            height: 72,
            child: CustomPaint(
              painter: _ArcPainter(progress: score / 100, color: color),
              child: Center(
                child: Text(
                  '$score',
                  style: GoogleFonts.inter(
                    color: _textPrimary,
                    fontWeight: FontWeight.w800,
                    fontSize: 20,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 10),
          Text(
            label,
            style: GoogleFonts.inter(
              color: _textSecondary,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Arc painter
// ─────────────────────────────────────────────

class _ArcPainter extends CustomPainter {
  final double progress;
  final Color color;

  const _ArcPainter({required this.progress, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = (size.width / 2) - 6;
    const startAngle = -math.pi / 2;

    // Background arc
    final bgPaint = Paint()
      ..color = color.withOpacity(0.12)
      ..strokeWidth = 7
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    canvas.drawCircle(center, radius, bgPaint);

    // Progress arc
    final fgPaint = Paint()
      ..color = color
      ..strokeWidth = 7
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      startAngle,
      2 * math.pi * progress,
      false,
      fgPaint,
    );

    // Glow effect
    final glowPaint = Paint()
      ..color = color.withOpacity(0.25)
      ..strokeWidth = 12
      ..style = PaintingStyle.stroke
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6);

    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      startAngle,
      2 * math.pi * progress,
      false,
      glowPaint,
    );
  }

  @override
  bool shouldRepaint(_ArcPainter old) => old.progress != progress || old.color != color;
}

// ─────────────────────────────────────────────
// Grammar error card
// ─────────────────────────────────────────────

class _GrammarErrorCard extends StatelessWidget {
  const _GrammarErrorCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _error.withOpacity(0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _error.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: _error.withOpacity(0.15),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.warning_amber_rounded, color: _error, size: 22),
          ),
          const SizedBox(width: 14),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '4 errors found',
                style: GoogleFonts.inter(
                  color: _error,
                  fontWeight: FontWeight.w700,
                  fontSize: 16,
                ),
              ),
              Text(
                'Grammar & phrasing issues detected',
                style: GoogleFonts.inter(color: _textSecondary, fontSize: 12),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Mispronounced words
// ─────────────────────────────────────────────

class _MispronounceSection extends StatelessWidget {
  const _MispronounceSection();

  static const List<String> _words = ['thoroughly', 'particularly', 'enthusiastic'];

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionHeader(
          icon: Icons.record_voice_over_rounded,
          title: 'Mispronounced Words',
          color: _error,
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: _words.asMap().entries.map((e) {
            return Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: _error.withOpacity(0.1),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: _error.withOpacity(0.35)),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.volume_up_rounded, color: _error, size: 14),
                  const SizedBox(width: 5),
                  Text(
                    e.value,
                    style: GoogleFonts.inter(
                      color: _error,
                      fontWeight: FontWeight.w600,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ).animate(delay: Duration(milliseconds: e.key * 80)).fadeIn().scale(begin: const Offset(0.9, 0.9), end: const Offset(1, 1));
          }).toList(),
        ),
      ],
    );
  }
}

// ─────────────────────────────────────────────
// Corrections section
// ─────────────────────────────────────────────

class _CorrectionsSection extends StatelessWidget {
  const _CorrectionsSection();

  static const List<String> _corrections = [
    "Use 'a window seat' not 'window seat'",
    "'I'd like to check in' is more natural",
    "Use present perfect: 'I have been waiting'",
  ];

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionHeader(
          icon: Icons.lightbulb_rounded,
          title: 'Corrections',
          color: _warning,
        ),
        const SizedBox(height: 12),
        ..._corrections.asMap().entries.map((e) {
          return Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: _surfaceCard,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: _border),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  margin: const EdgeInsets.only(top: 1),
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: _warning.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.lightbulb_outline_rounded, color: _warning, size: 14),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    e.value,
                    style: GoogleFonts.inter(color: _textPrimary, fontSize: 13, height: 1.5),
                  ),
                ),
              ],
            ),
          ).animate(delay: Duration(milliseconds: e.key * 80)).fadeIn().slideX(begin: 0.03, end: 0);
        }),
      ],
    );
  }
}

// ─────────────────────────────────────────────
// Phoneme section
// ─────────────────────────────────────────────

class _PhonemeSection extends StatelessWidget {
  const _PhonemeSection();

  static const List<Map<String, dynamic>> _phonemes = [
    {'ph': '/θ/', 'word': 'thoroughly', 'score': 42, 'color': _error},
    {'ph': '/ɪ/', 'word': 'particularly', 'score': 58, 'color': _warning},
    {'ph': '/æ/', 'word': 'enthusiastic', 'score': 63, 'color': _warning},
    {'ph': '/ɑː/', 'word': 'passport', 'score': 85, 'color': _success},
    {'ph': '/iː/', 'word': 'seat', 'score': 91, 'color': _success},
  ];

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionHeader(
          icon: Icons.equalizer_rounded,
          title: 'Phoneme Detail',
          color: _primary,
          useCustomIcon: false,
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: _phonemes.asMap().entries.map((e) {
            final ph   = e.value;
            final clr  = ph['color'] as Color;
            final sc   = ph['score'] as int;
            return Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: _surfaceCard,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: clr.withOpacity(0.35)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    ph['ph'] as String,
                    style: GoogleFonts.jetBrainsMono(
                      color: clr,
                      fontWeight: FontWeight.w700,
                      fontSize: 14,
                    ),
                  ),
                  Text(
                    ph['word'] as String,
                    style: GoogleFonts.inter(color: _textSecondary, fontSize: 10),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '$sc%',
                    style: GoogleFonts.inter(color: _textPrimary, fontWeight: FontWeight.w700, fontSize: 13),
                  ),
                ],
              ),
            ).animate(delay: Duration(milliseconds: e.key * 70)).fadeIn().scale(begin: const Offset(0.92, 0.92), end: const Offset(1, 1));
          }).toList(),
        ),
      ],
    );
  }
}

// Workaround for waveform icon (not available on all versions)
extension on IconData {
  // ignore
}

// ─────────────────────────────────────────────
// Save Words button
// ─────────────────────────────────────────────

class _SaveWordsButton extends StatelessWidget {
  final VoidCallback onTap;
  const _SaveWordsButton({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 16),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [_primary, _accent],
            begin: Alignment.centerLeft,
            end: Alignment.centerRight,
          ),
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: _primary.withOpacity(0.4),
              blurRadius: 20,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.bookmark_add_rounded, color: Colors.white, size: 22),
            const SizedBox(width: 10),
            Text(
              'Save words to Practice',
              style: GoogleFonts.inter(
                color: Colors.white,
                fontWeight: FontWeight.w700,
                fontSize: 16,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Section header widget
// ─────────────────────────────────────────────

class _SectionHeader extends StatelessWidget {
  final IconData icon;
  final String title;
  final Color color;
  final bool useCustomIcon;

  const _SectionHeader({
    required this.icon,
    required this.title,
    required this.color,
    this.useCustomIcon = false,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(7),
          decoration: BoxDecoration(
            color: color.withOpacity(0.13),
            borderRadius: BorderRadius.circular(9),
          ),
          child: Icon(
            useCustomIcon ? Icons.graphic_eq_rounded : icon,
            color: color,
            size: 16,
          ),
        ),
        const SizedBox(width: 10),
        Text(
          title,
          style: GoogleFonts.inter(
            color: _textPrimary,
            fontWeight: FontWeight.w700,
            fontSize: 16,
          ),
        ),
      ],
    );
  }
}
