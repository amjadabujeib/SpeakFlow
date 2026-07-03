import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:go_router/go_router.dart';

// ─────────────────────────── Colors ───────────────────────────
const _background = Color(0xFF090E1A);
const _surfaceCard = Color(0xFF1E2D45);
const _primary = Color(0xFF4F7FFF);
const _accent = Color(0xFF8B5CF6);
const _success = Color(0xFF22C55E);
const _warning = Color(0xFFF59E0B);
const _error = Color(0xFFEF4444);
const _textPrimary = Color(0xFFF1F5FF);
const _textSecondary = Color(0xFF8896B0);

// ─────────────────────────── Mock Data ────────────────────────

class _WordEntry {
  final String word;
  final String ipa;
  final int score;
  final String source;
  final String? info;

  _WordEntry({
    required this.word,
    required this.ipa,
    required this.score,
    required this.source,
    this.info,
  });

  _WordEntry copyWith({int? score}) => _WordEntry(
        word: word,
        ipa: ipa,
        score: score ?? this.score,
        source: source,
        info: info,
      );
}

final _initialWords = [
  _WordEntry(
      word: 'thoroughly',
      ipa: '/ˈθɜːrəli/',
      score: 42,
      source: 'Airport roleplay'),
  _WordEntry(
      word: 'comfortable',
      ipa: '/ˈkʌmftəbəl/',
      score: 58,
      source: 'Hotel check-in roleplay'),
  _WordEntry(
      word: 'enthusiasm',
      ipa: '/ɪnˈθjuːziæzəm/',
      score: 35,
      source: 'Job interview roleplay'),
  _WordEntry(
      word: 'particularly',
      ipa: '/pəˈtɪkjələrli/',
      score: 61,
      source: 'Coffee shop roleplay'),
  _WordEntry(
      word: 'literature',
      ipa: '/ˈlɪtrətʃər/',
      score: 48,
      source: 'Own practice'),
];

class _PhonemeEntry {
  final String symbol;
  final int score;
  const _PhonemeEntry(this.symbol, this.score);
}

const _vowels = [
  _PhonemeEntry('iː', 88),
  _PhonemeEntry('ɪ', 72),
  _PhonemeEntry('e', 65),
  _PhonemeEntry('æ', 44),
  _PhonemeEntry('ɑː', 78),
  _PhonemeEntry('ɒ', 55),
  _PhonemeEntry('ɔː', 82),
  _PhonemeEntry('ʊ', 68),
  _PhonemeEntry('uː', 90),
  _PhonemeEntry('ʌ', 50),
  _PhonemeEntry('ɜː', 38),
  _PhonemeEntry('ə', 71),
  _PhonemeEntry('eɪ', 85),
  _PhonemeEntry('aɪ', 76),
  _PhonemeEntry('ɔɪ', 62),
  _PhonemeEntry('aʊ', 58),
  _PhonemeEntry('əʊ', 74),
  _PhonemeEntry('ɪə', 45),
  _PhonemeEntry('eə', 41),
  _PhonemeEntry('ʊə', 39),
];

const _consonants = [
  _PhonemeEntry('p', 92),
  _PhonemeEntry('b', 88),
  _PhonemeEntry('t', 85),
  _PhonemeEntry('d', 80),
  _PhonemeEntry('k', 87),
  _PhonemeEntry('g', 75),
  _PhonemeEntry('f', 83),
  _PhonemeEntry('v', 70),
  _PhonemeEntry('θ', 28),
  _PhonemeEntry('ð', 32),
  _PhonemeEntry('s', 86),
  _PhonemeEntry('z', 72),
  _PhonemeEntry('ʃ', 65),
  _PhonemeEntry('ʒ', 48),
  _PhonemeEntry('h', 91),
  _PhonemeEntry('tʃ', 77),
  _PhonemeEntry('dʒ', 68),
  _PhonemeEntry('m', 94),
  _PhonemeEntry('n', 90),
  _PhonemeEntry('ŋ', 60),
  _PhonemeEntry('l', 82),
  _PhonemeEntry('r', 55),
  _PhonemeEntry('j', 88),
  _PhonemeEntry('w', 89),
];

// ──────────────────── Score Color Helper ──────────────────────
Color _scoreColor(int score) {
  if (score < 50) return _error;
  if (score <= 80) return _warning;
  return _success;
}

// ──────────────────── Arc Painter ─────────────────────────────
class _ArcPainter extends CustomPainter {
  final double progress; // 0.0 – 1.0
  final Color arcColor;

  _ArcPainter({required this.progress, required this.arcColor});

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height / 2;
    final radius = (size.width / 2) - 8;
    final rect = Rect.fromCircle(center: Offset(cx, cy), radius: radius);

    // Track
    final trackPaint = Paint()
      ..color = const Color(0xFF1E2D45)
      ..strokeWidth = 10
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(rect, -math.pi / 2, 2 * math.pi, false, trackPaint);

    // Arc
    final arcPaint = Paint()
      ..shader = const LinearGradient(
        colors: [_primary, _accent],
      ).createShader(rect)
      ..strokeWidth = 10
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(
        rect, -math.pi / 2, 2 * math.pi * progress, false, arcPaint);
  }

  @override
  bool shouldRepaint(_ArcPainter old) => old.progress != progress;
}

// ──────────────────── Main Widget ─────────────────────────────
class PracticeTab extends StatefulWidget {
  const PracticeTab({super.key});

  @override
  State<PracticeTab> createState() => _PracticeTabState();
}

class _PracticeTabState extends State<PracticeTab>
    with TickerProviderStateMixin {
  int _selectedSegment = 0;
  final List<_WordEntry> _words = List.from(_initialWords);
  final TextEditingController _addWordCtrl = TextEditingController();
  late AnimationController _arcController;
  late Animation<double> _arcAnimation;

  // Overall average score for phoneme map
  int get _overallScore {
    final all = [..._vowels, ..._consonants];
    return all.fold(0, (sum, p) => sum + p.score) ~/ all.length;
  }

  @override
  void initState() {
    super.initState();
    _arcController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    );
    _arcAnimation = CurvedAnimation(
      parent: _arcController,
      curve: Curves.easeOutCubic,
    );
    _arcController.forward();
  }

  @override
  void dispose() {
    _arcController.dispose();
    _addWordCtrl.dispose();
    super.dispose();
  }

  void _removeWord(int index) {
    setState(() => _words.removeAt(index));
  }

  void _addWord() {
    final text = _addWordCtrl.text.trim();
    if (text.isEmpty) return;
    setState(() {
      _words.add(_WordEntry(
        word: text,
        ipa: '/${text.toLowerCase()}/',
        score: 0,
        source: 'Custom',
        info: 'Added by you. Practice pronunciation to score.',
      ));
      _addWordCtrl.clear();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _background,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            _buildFeatureCards(),
            _buildSegmentedControl(),
            Expanded(
              child: AnimatedSwitcher(
                duration: const Duration(milliseconds: 300),
                transitionBuilder: (child, animation) => FadeTransition(
                  opacity: animation,
                  child: child,
                ),
                child: _selectedSegment == 0
                    ? _WordPracticeSection(
                        key: const ValueKey('word'),
                        words: _words,
                        onRemove: _removeWord,
                        addWordCtrl: _addWordCtrl,
                        onAdd: _addWord,
                      )
                    : _PhonemeMapSection(
                        key: const ValueKey('phoneme'),
                        overallScore: _overallScore,
                        arcAnimation: _arcAnimation,
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Row(
        children: [
          Text(
            'Practice',
            style: GoogleFonts.outfit(
              fontSize: 28,
              fontWeight: FontWeight.w700,
              color: _textPrimary,
              letterSpacing: -0.5,
            ),
          ),
          const Spacer(),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: _surfaceCard,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.tune_rounded, color: _textSecondary, size: 20),
          ),
        ],
      ).animate().fadeIn(duration: 400.ms).slideY(begin: -0.2, end: 0),
    );
  }

  Widget _buildFeatureCards() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
      child: Row(
        children: [
          Expanded(
            child: GestureDetector(
              onTap: () => context.push('/grammar-check'),
              child: Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [_primary.withOpacity(0.15), _accent.withOpacity(0.08)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: _primary.withOpacity(0.25), width: 1),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(colors: [_primary, _accent]),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: const Icon(Icons.spellcheck_rounded, color: Colors.white, size: 18),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      'Grammar\nCheck',
                      style: GoogleFonts.inter(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: _textPrimary,
                        height: 1.2,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'AI-powered corrections',
                      style: GoogleFonts.inter(fontSize: 11, color: _textSecondary),
                    ),
                  ],
                ),
              ),
            ).animate().fadeIn(duration: 400.ms, delay: 50.ms).slideX(begin: -0.1, end: 0),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: GestureDetector(
              onTap: () => context.push('/plp/lessons'),
              child: Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [_accent.withOpacity(0.15), _primary.withOpacity(0.08)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: _accent.withOpacity(0.25), width: 1),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(colors: [_accent, _primary]),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: const Icon(Icons.auto_awesome_rounded, color: Colors.white, size: 18),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      'AI\nLessons',
                      style: GoogleFonts.inter(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: _textPrimary,
                        height: 1.2,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'PLP structured learning',
                      style: GoogleFonts.inter(fontSize: 11, color: _textSecondary),
                    ),
                  ],
                ),
              ),
            ).animate().fadeIn(duration: 400.ms, delay: 100.ms).slideX(begin: 0.1, end: 0),
          ),
        ],
      ),
    );
  }

  Widget _buildSegmentedControl() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      child: Container(
        height: 48,
        padding: const EdgeInsets.all(4),
        decoration: BoxDecoration(
          color: const Color(0xFF111827),
          borderRadius: BorderRadius.circular(28),
          border: Border.all(color: const Color(0xFF1E2D45), width: 1),
        ),
        child: Row(
          children: [
            _buildSegmentPill(0, 'Word Practice', Icons.record_voice_over_rounded),
            _buildSegmentPill(1, 'Phoneme Map', Icons.grid_view_rounded),
          ],
        ),
      ).animate().fadeIn(duration: 500.ms, delay: 100.ms),
    );
  }

  Widget _buildSegmentPill(int index, String label, IconData icon) {
    final isSelected = _selectedSegment == index;
    return Expanded(
      child: GestureDetector(
        onTap: () {
          setState(() => _selectedSegment = index);
          if (index == 1) {
            _arcController.reset();
            _arcController.forward();
          }
        },
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeInOut,
          decoration: BoxDecoration(
            gradient: isSelected
                ? const LinearGradient(
                    colors: [_primary, _accent],
                    begin: Alignment.centerLeft,
                    end: Alignment.centerRight,
                  )
                : null,
            borderRadius: BorderRadius.circular(24),
            boxShadow: isSelected
                ? [
                    BoxShadow(
                      color: _primary.withAlpha(80),
                      blurRadius: 12,
                      offset: const Offset(0, 4),
                    )
                  ]
                : null,
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, size: 16,
                  color: isSelected ? Colors.white : _textSecondary),
              const SizedBox(width: 6),
              Text(
                label,
                style: GoogleFonts.outfit(
                  fontSize: 13,
                  fontWeight:
                      isSelected ? FontWeight.w600 : FontWeight.w400,
                  color: isSelected ? Colors.white : _textSecondary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ─────────────── Word Practice Section ────────────────────────
class _WordPracticeSection extends StatelessWidget {
  final List<_WordEntry> words;
  final void Function(int) onRemove;
  final TextEditingController addWordCtrl;
  final VoidCallback onAdd;

  const _WordPracticeSection({
    super.key,
    required this.words,
    required this.onRemove,
    required this.addWordCtrl,
    required this.onAdd,
  });

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
      children: [
        _SectionHeader(
          label: 'Words to Practice',
          count: words.length,
        ).animate().fadeIn(duration: 400.ms).slideX(begin: -0.1, end: 0),
        const SizedBox(height: 12),
        ...List.generate(words.length, (i) {
          return _WordCard(
            entry: words[i],
            onPractice: () {},
            onMarkCorrect: () => onRemove(i),
          )
              .animate(delay: Duration(milliseconds: 60 * i))
              .fadeIn(duration: 350.ms)
              .slideY(begin: 0.15, end: 0);
        }),
        const SizedBox(height: 20),
        _AddWordSection(ctrl: addWordCtrl, onAdd: onAdd)
            .animate(delay: 300.ms)
            .fadeIn(duration: 400.ms),
      ],
    );
  }
}

// ─────────────── Section Header ───────────────────────────────
class _SectionHeader extends StatelessWidget {
  final String label;
  final int count;

  const _SectionHeader({required this.label, required this.count});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(
          label,
          style: GoogleFonts.outfit(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: _textPrimary,
          ),
        ),
        const SizedBox(width: 10),
        Container(
          width: 28,
          height: 28,
          decoration: const BoxDecoration(
            shape: BoxShape.circle,
            gradient: LinearGradient(
              colors: [_primary, _accent],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
          ),
          alignment: Alignment.center,
          child: Text(
            '$count',
            style: GoogleFonts.outfit(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: Colors.white,
            ),
          ),
        ),
      ],
    );
  }
}

// ─────────────── Word Card ────────────────────────────────────
class _WordCard extends StatelessWidget {
  final _WordEntry entry;
  final VoidCallback onPractice;
  final VoidCallback onMarkCorrect;

  const _WordCard({
    required this.entry,
    required this.onPractice,
    required this.onMarkCorrect,
  });

  @override
  Widget build(BuildContext context) {
    final borderColor = _scoreColor(entry.score);
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(14),
        border: Border(
          left: BorderSide(color: borderColor, width: 3),
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withAlpha(50),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    entry.word,
                    style: GoogleFonts.outfit(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      color: _textPrimary,
                    ),
                  ),
                  if (entry.ipa.isNotEmpty) ...[
                    const SizedBox(height: 3),
                    Text(
                      entry.ipa,
                      style: GoogleFonts.outfit(
                        fontSize: 13,
                        fontWeight: FontWeight.w400,
                        color: _accent,
                      ),
                    ),
                  ],
                  if (entry.info != null) ...[
                    const SizedBox(height: 3),
                    Text(
                      entry.info!,
                      style: GoogleFonts.outfit(
                        fontSize: 12,
                        fontWeight: FontWeight.w400,
                        color: _textSecondary,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                  ],
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      _ScorePill(score: entry.score),
                      const SizedBox(width: 10),
                      if (entry.source.isNotEmpty)
                        Expanded(
                          child: Text(
                            entry.source,
                            overflow: TextOverflow.ellipsis,
                            style: GoogleFonts.outfit(
                              fontSize: 11,
                              color: _textSecondary,
                            ),
                          ),
                        ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            Column(
              children: [
                _ActionBtn(
                  icon: Icons.mic_rounded,
                  color: _primary,
                  onTap: onPractice,
                  tooltip: 'Practice',
                ),
                const SizedBox(height: 8),
                _ActionBtn(
                  icon: Icons.check_circle_outline_rounded,
                  color: _success,
                  onTap: onMarkCorrect,
                  tooltip: 'Mark as correct',
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────── Score Pill ───────────────────────────────────
class _ScorePill extends StatelessWidget {
  final int score;
  const _ScorePill({required this.score});

  @override
  Widget build(BuildContext context) {
    final color = _scoreColor(score);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
      decoration: BoxDecoration(
        color: color.withAlpha(40),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withAlpha(100), width: 1),
      ),
      child: Text(
        '$score%',
        style: GoogleFonts.outfit(
          fontSize: 12,
          fontWeight: FontWeight.w600,
          color: color,
        ),
      ),
    );
  }
}

// ─────────────── Action Button ────────────────────────────────
class _ActionBtn extends StatelessWidget {
  final IconData icon;
  final Color color;
  final VoidCallback onTap;
  final String tooltip;

  const _ActionBtn({
    required this.icon,
    required this.color,
    required this.onTap,
    required this.tooltip,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          width: 38,
          height: 38,
          decoration: BoxDecoration(
            color: color.withAlpha(25),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: color.withAlpha(70), width: 1),
          ),
          child: Icon(icon, color: color, size: 18),
        ),
      ),
    );
  }
}

// ─────────────── Add Word Section ─────────────────────────────
class _AddWordSection extends StatelessWidget {
  final TextEditingController ctrl;
  final VoidCallback onAdd;

  const _AddWordSection({required this.ctrl, required this.onAdd});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Add your own word',
          style: GoogleFonts.outfit(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            color: _textSecondary,
            letterSpacing: 0.3,
          ),
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: TextField(
                controller: ctrl,
                style: GoogleFonts.outfit(
                  color: _textPrimary,
                  fontSize: 15,
                ),
                decoration: InputDecoration(
                  hintText: 'e.g. pronunciation',
                  hintStyle: GoogleFonts.outfit(
                    color: _textSecondary,
                    fontSize: 15,
                  ),
                  filled: true,
                  fillColor: _surfaceCard,
                  contentPadding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 14),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide.none,
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(
                        color: Color(0xFF2A3E5A), width: 1),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide:
                        const BorderSide(color: _primary, width: 1.5),
                  ),
                ),
                onSubmitted: (_) => onAdd(),
              ),
            ),
            const SizedBox(width: 10),
            GestureDetector(
              onTap: onAdd,
              child: Container(
                height: 50,
                width: 50,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [_primary, _accent],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(12),
                  boxShadow: [
                    BoxShadow(
                      color: _primary.withAlpha(80),
                      blurRadius: 12,
                      offset: const Offset(0, 4),
                    )
                  ],
                ),
                child: const Icon(Icons.add_rounded,
                    color: Colors.white, size: 24),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

// ─────────────── Phoneme Map Section ──────────────────────────
class _PhonemeMapSection extends StatelessWidget {
  final int overallScore;
  final Animation<double> arcAnimation;

  const _PhonemeMapSection({
    super.key,
    required this.overallScore,
    required this.arcAnimation,
  });

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
      children: [
        _OverallScoreArc(
          score: overallScore,
          animation: arcAnimation,
        ).animate().fadeIn(duration: 500.ms).scale(
              begin: const Offset(0.85, 0.85),
              end: const Offset(1, 1),
              duration: 500.ms,
              curve: Curves.easeOutBack,
            ),
        const SizedBox(height: 24),
        _LegendRow()
            .animate(delay: 200.ms)
            .fadeIn(duration: 400.ms),
        const SizedBox(height: 24),
        _PhonemeGroupSection(
          title: 'Vowels',
          phonemes: _vowels,
        )
            .animate(delay: 300.ms)
            .fadeIn(duration: 400.ms)
            .slideY(begin: 0.1, end: 0),
        const SizedBox(height: 20),
        _PhonemeGroupSection(
          title: 'Consonants',
          phonemes: _consonants,
        )
            .animate(delay: 450.ms)
            .fadeIn(duration: 400.ms)
            .slideY(begin: 0.1, end: 0),
      ],
    );
  }
}

// ─────────────── Overall Score Arc ────────────────────────────
class _OverallScoreArc extends StatelessWidget {
  final int score;
  final Animation<double> animation;

  const _OverallScoreArc({required this.score, required this.animation});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFF2A3E5A), width: 1),
      ),
      child: Column(
        children: [
          Text(
            'Your Pronunciation Profile',
            style: GoogleFonts.outfit(
              fontSize: 17,
              fontWeight: FontWeight.w700,
              color: _textPrimary,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Based on all your recent sessions',
            style: GoogleFonts.outfit(
              fontSize: 13,
              color: _textSecondary,
            ),
          ),
          const SizedBox(height: 24),
          AnimatedBuilder(
            animation: animation,
            builder: (context, _) {
              final progress = animation.value * (score / 100.0);
              return SizedBox(
                width: 140,
                height: 140,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    CustomPaint(
                      size: const Size(140, 140),
                      painter: _ArcPainter(
                          progress: progress,
                          arcColor: _scoreColor(score)),
                    ),
                    Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          '$score%',
                          style: GoogleFonts.outfit(
                            fontSize: 36,
                            fontWeight: FontWeight.w800,
                            color: _textPrimary,
                            height: 1,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Overall',
                          style: GoogleFonts.outfit(
                            fontSize: 12,
                            color: _textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              );
            },
          ),
        ],
      ),
    );
  }
}

// ─────────────── Legend ───────────────────────────────────────
class _LegendRow extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        _LegendDot(color: _error, label: 'Needs Work (<50%)'),
        const SizedBox(width: 18),
        _LegendDot(color: _warning, label: 'Fair (50–80%)'),
        const SizedBox(width: 18),
        _LegendDot(color: _success, label: 'Good (>80%)'),
      ],
    );
  }
}

class _LegendDot extends StatelessWidget {
  final Color color;
  final String label;

  const _LegendDot({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 5),
        Text(
          label,
          style: GoogleFonts.outfit(fontSize: 11, color: _textSecondary),
        ),
      ],
    );
  }
}

// ─────────────── Phoneme Group ────────────────────────────────
class _PhonemeGroupSection extends StatelessWidget {
  final String title;
  final List<_PhonemeEntry> phonemes;

  const _PhonemeGroupSection(
      {required this.title, required this.phonemes});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              width: 3,
              height: 18,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [_primary, _accent],
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                ),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(width: 8),
            Text(
              title,
              style: GoogleFonts.outfit(
                fontSize: 15,
                fontWeight: FontWeight.w700,
                color: _textPrimary,
              ),
            ),
            const Spacer(),
            Text(
              '${phonemes.length} phonemes',
              style: GoogleFonts.outfit(
                fontSize: 12,
                color: _textSecondary,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          children: phonemes
              .map((p) => _PhonemeCell(entry: p))
              .toList(),
        ),
      ],
    );
  }
}

// ─────────────── Phoneme Cell ─────────────────────────────────
class _PhonemeCell extends StatefulWidget {
  final _PhonemeEntry entry;
  const _PhonemeCell({required this.entry});

  @override
  State<_PhonemeCell> createState() => _PhonemeCellState();
}

class _PhonemeCellState extends State<_PhonemeCell> {
  bool _pressed = false;

  Color get _cellColor {
    final s = widget.entry.score;
    if (s < 50) return _error;
    if (s <= 80) return _warning;
    return _success;
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) => setState(() => _pressed = false),
      onTapCancel: () => setState(() => _pressed = false),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 120),
        width: 48,
        height: 48,
        decoration: BoxDecoration(
          color: _pressed
              ? _cellColor.withAlpha(230)
              : _cellColor.withAlpha(200),
          borderRadius: BorderRadius.circular(10),
          boxShadow: [
            BoxShadow(
              color: _cellColor.withAlpha(_pressed ? 80 : 40),
              blurRadius: _pressed ? 8 : 4,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        transform: _pressed
            ? (Matrix4.identity()..scaleByDouble(0.93, 0.93, 1, 1))
            : Matrix4.identity(),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              widget.entry.symbol,
              style: GoogleFonts.outfit(
                fontSize: 14,
                fontWeight: FontWeight.w700,
                color: Colors.white,
                height: 1.1,
              ),
            ),
            Text(
              '${widget.entry.score}%',
              style: const TextStyle(
                fontSize: 9,
                fontWeight: FontWeight.w500,
                color: Colors.white70,
                height: 1.2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
