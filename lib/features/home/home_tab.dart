import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:go_router/go_router.dart';

// ─── Color Palette ───────────────────────────────────────────────────────────
const _background   = Color(0xFF090E1A);
const _surface      = Color(0xFF111827);
const _surfaceCard  = Color(0xFF1E2D45);
const _primary      = Color(0xFF4F7FFF);
const _success      = Color(0xFF22C55E);
const _textPrimary  = Color(0xFFF1F5FF);
const _textSecondary= Color(0xFF8896B0);
const _textMuted    = Color(0xFF4A5568);
const _border       = Color(0xFF1E2D45);
const _streakActive = Color(0xFFFF6B35);

// ─── Data Models ─────────────────────────────────────────────────────────────
enum UnitStatus { completed, inProgress, locked }
enum LessonStatus { completed, inProgress, locked }
enum LessonType { pronunciation, grammar, vocabulary, exam }

class LessonData {
  final String name;
  final LessonStatus status;
  final LessonType type;
  const LessonData({
    required this.name,
    required this.status,
    required this.type,
  });
}

class UnitData {
  final int number;
  final String title;
  final String description;
  final UnitStatus status;
  final List<LessonData> lessons;
  const UnitData({
    required this.number,
    required this.title,
    required this.description,
    required this.status,
    required this.lessons,
  });
}

// ─── Mock Data ────────────────────────────────────────────────────────────────
const List<UnitData> _units = [
  UnitData(
    number: 1,
    title: 'Everyday Greetings',
    description: 'Master common greetings and farewells used in daily conversations.',
    status: UnitStatus.completed,
    lessons: [
      LessonData(name: 'Hello & Goodbye',      status: LessonStatus.completed,  type: LessonType.pronunciation),
      LessonData(name: 'Formal Introductions',  status: LessonStatus.completed,  type: LessonType.grammar),
      LessonData(name: 'Common Phrases',        status: LessonStatus.completed,  type: LessonType.vocabulary),
      LessonData(name: 'Unit 1 Assessment',     status: LessonStatus.completed,  type: LessonType.exam),
    ],
  ),
  UnitData(
    number: 2,
    title: 'Talking About Yourself',
    description: 'Learn to describe yourself, your hobbies, and your background.',
    status: UnitStatus.inProgress,
    lessons: [
      LessonData(name: 'Personal Information', status: LessonStatus.completed,   type: LessonType.vocabulary),
      LessonData(name: 'Hobbies & Interests',  status: LessonStatus.inProgress,  type: LessonType.grammar),
      LessonData(name: 'Your Daily Routine',   status: LessonStatus.locked,      type: LessonType.pronunciation),
      LessonData(name: 'Unit 2 Assessment',    status: LessonStatus.locked,      type: LessonType.exam),
    ],
  ),
  UnitData(
    number: 3,
    title: 'Getting Around',
    description: 'Navigate cities, ask for directions, and use public transport.',
    status: UnitStatus.locked,
    lessons: [
      LessonData(name: 'Asking for Directions', status: LessonStatus.locked, type: LessonType.pronunciation),
      LessonData(name: 'Using Public Transport', status: LessonStatus.locked, type: LessonType.vocabulary),
      LessonData(name: 'Reading Maps',           status: LessonStatus.locked, type: LessonType.grammar),
      LessonData(name: 'Unit 3 Assessment',      status: LessonStatus.locked, type: LessonType.exam),
    ],
  ),
  UnitData(
    number: 4,
    title: 'At the Restaurant',
    description: 'Order food, understand menus, and interact with restaurant staff.',
    status: UnitStatus.locked,
    lessons: [
      LessonData(name: 'Reading a Menu',     status: LessonStatus.locked, type: LessonType.vocabulary),
      LessonData(name: 'Placing an Order',   status: LessonStatus.locked, type: LessonType.pronunciation),
      LessonData(name: 'Paying the Bill',    status: LessonStatus.locked, type: LessonType.grammar),
      LessonData(name: 'Unit 4 Assessment',  status: LessonStatus.locked, type: LessonType.exam),
    ],
  ),
];

const List<bool> _weekStudied = [true, true, false, true, true, true, false];
const List<String> _weekLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

// ─── HomeTab Widget ───────────────────────────────────────────────────────────
class HomeTab extends StatefulWidget {
  const HomeTab({super.key});

  @override
  State<HomeTab> createState() => _HomeTabState();
}

class _HomeTabState extends State<HomeTab> {
  late List<bool> _expanded;

  @override
  void initState() {
    super.initState();
    // Default: expand first in-progress unit
    _expanded = _units.map((u) => u.status == UnitStatus.inProgress).toList();
  }

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: _background,
      child: CustomScrollView(
        physics: const BouncingScrollPhysics(),
        slivers: [
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 8),
            sliver: SliverList(
              delegate: SliverChildListDelegate([
                // ── Section 1: Streak Card ──────────────────────────────
                _StreakCard(),
                const SizedBox(height: 20),

                // ── Quick Actions ────────────────────────────────────
                Text(
                  'Quick Actions',
                  style: GoogleFonts.inter(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: _textPrimary,
                  ),
                ).animate().fadeIn(duration: 350.ms, delay: 50.ms),
                const SizedBox(height: 10),
                Row(
                  children: [
                    _QuickActionTile(
                      icon: Icons.spellcheck_rounded,
                      label: 'Grammar\nCheck',
                      gradientColors: const [_primary, Color(0xFF8B5CF6)],
                      onTap: () => context.push('/grammar-check'),
                    ),
                    const SizedBox(width: 12),
                    _QuickActionTile(
                      icon: Icons.auto_awesome_rounded,
                      label: 'AI\nLessons',
                      gradientColors: const [Color(0xFF8B5CF6), _primary],
                      onTap: () => context.push('/plp/lessons'),
                    ),
                    const SizedBox(width: 12),
                    _QuickActionTile(
                      icon: Icons.chat_rounded,
                      label: 'Chat\nPractice',
                      gradientColors: const [_success, Color(0xFF06B6D4)],
                      onTap: () => context.go('/chat'),
                    ),
                  ],
                ).animate().fadeIn(duration: 400.ms, delay: 100.ms).slideY(begin: 0.05, end: 0),
                const SizedBox(height: 24),

                // ── Section 2: Learning Plan ────────────────────────────
                _LearningPlanHeader(),
                const SizedBox(height: 14),

                // Unit cards
                ...List.generate(_units.length, (i) {
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 14),
                    child: _UnitCard(
                      unit: _units[i],
                      isExpanded: _expanded[i],
                      onToggle: _units[i].status != UnitStatus.locked
                          ? () => setState(() => _expanded[i] = !_expanded[i])
                          : null,
                    ),
                  ).animate(delay: Duration(milliseconds: 80 * i))
                      .fadeIn(duration: 400.ms)
                      .slideY(begin: 0.08, end: 0, curve: Curves.easeOut);
                }),

                const SizedBox(height: 40),
              ]),
            ),
          ),
        ],
      ),
    );
  }
}

// ─── Streak Card ─────────────────────────────────────────────────────────────
class _StreakCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _border.withOpacity(0.6), width: 1.2),
        boxShadow: [
          BoxShadow(
            color: _streakActive.withOpacity(0.06),
            blurRadius: 24,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Top row: flame + count + label
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              const Text('🔥', style: TextStyle(fontSize: 30)),
              const SizedBox(width: 10),
              Text(
                '7',
                style: GoogleFonts.inter(
                  fontSize: 32,
                  fontWeight: FontWeight.w800,
                  color: _streakActive,
                  height: 1,
                ),
              ),
              const SizedBox(width: 8),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'day streak',
                    style: GoogleFonts.inter(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: _textPrimary,
                    ),
                  ),
                  Text(
                    'Keep it up!',
                    style: GoogleFonts.inter(
                      fontSize: 11,
                      color: _textSecondary,
                    ),
                  ),
                ],
              ),
              const Spacer(),
              // Small badge
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: _streakActive.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: _streakActive.withOpacity(0.3)),
                ),
                child: Text(
                  'This Week',
                  style: GoogleFonts.inter(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: _streakActive,
                  ),
                ),
              ),
            ],
          ),

          const SizedBox(height: 18),

          // Day circles row
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: List.generate(7, (i) {
              final studied = _weekStudied[i];
              final label = _weekLabels[i];
              return _DayCircle(label: label, studied: studied, index: i);
            }),
          ),
        ],
      ),
    )
        .animate()
        .fadeIn(duration: 500.ms, curve: Curves.easeOut)
        .slideY(begin: -0.05, end: 0, duration: 500.ms, curve: Curves.easeOut);
  }
}

class _DayCircle extends StatelessWidget {
  final String label;
  final bool studied;
  final int index;

  const _DayCircle({
    required this.label,
    required this.studied,
    required this.index,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Circle
        Container(
          width: 36,
          height: 36,
          decoration: studied
              ? BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: const LinearGradient(
                    colors: [Color(0xFFFF8C42), Color(0xFFFF6B35)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: _streakActive.withOpacity(0.4),
                      blurRadius: 8,
                      offset: const Offset(0, 3),
                    ),
                  ],
                )
              : BoxDecoration(
                  shape: BoxShape.circle,
                  color: const Color(0xFF0D1B2E),
                  border: Border.all(color: _textMuted.withOpacity(0.4), width: 1),
                ),
          child: Center(
            child: Text(
              label[0],
              style: GoogleFonts.inter(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: studied ? Colors.white : _textMuted,
              ),
            ),
          ),
        )
            .animate(delay: Duration(milliseconds: 60 * index))
            .scale(begin: const Offset(0.7, 0.7), end: const Offset(1, 1), duration: 350.ms, curve: Curves.elasticOut),

        const SizedBox(height: 6),

        // Label
        Text(
          label,
          style: GoogleFonts.inter(
            fontSize: 10,
            fontWeight: FontWeight.w500,
            color: studied ? _streakActive : _textMuted,
          ),
        ),
      ],
    );
  }
}

// ─── Learning Plan Header ─────────────────────────────────────────────────────
class _LearningPlanHeader extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(
          'My Learning Plan',
          style: GoogleFonts.inter(
            fontSize: 18,
            fontWeight: FontWeight.w700,
            color: _textPrimary,
          ),
        ),
        const SizedBox(width: 10),
        // B1 badge
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
          decoration: BoxDecoration(
            color: _primary.withOpacity(0.18),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: _primary.withOpacity(0.4)),
          ),
          child: Text(
            'B1',
            style: GoogleFonts.inter(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: _primary,
            ),
          ),
        ),
      ],
    )
        .animate()
        .fadeIn(duration: 400.ms)
        .slideX(begin: -0.04, end: 0, duration: 400.ms, curve: Curves.easeOut);
  }
}

// ─── Unit Card ────────────────────────────────────────────────────────────────
class _UnitCard extends StatelessWidget {
  final UnitData unit;
  final bool isExpanded;
  final VoidCallback? onToggle;

  const _UnitCard({
    required this.unit,
    required this.isExpanded,
    required this.onToggle,
  });

  Color get _stripColor {
    switch (unit.status) {
      case UnitStatus.completed:  return _success;
      case UnitStatus.inProgress: return _primary;
      case UnitStatus.locked:     return _textMuted;
    }
  }

  @override
  Widget build(BuildContext context) {
    final isLocked = unit.status == UnitStatus.locked;

    return Opacity(
      opacity: isLocked ? 0.55 : 1.0,
      child: GestureDetector(
        onTap: onToggle,
        behavior: HitTestBehavior.opaque,
        child: Container(
          decoration: BoxDecoration(
            color: _surfaceCard,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: _border.withOpacity(0.5), width: 1),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.2),
                blurRadius: 12,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          clipBehavior: Clip.hardEdge,
          child: IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Left coloured strip
                Container(width: 4, color: _stripColor),

                // Card body
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Header row
                        Row(
                          children: [
                            _UnitNumberCircle(
                              number: unit.number,
                              stripColor: _stripColor,
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Text(
                                unit.title,
                                style: GoogleFonts.inter(
                                  fontSize: 15,
                                  fontWeight: FontWeight.w700,
                                  color: _textPrimary,
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            const SizedBox(width: 8),
                            _StatusIcon(status: unit.status),
                            const SizedBox(width: 4),
                            // Expand/collapse chevron
                            if (!isLocked)
                              AnimatedRotation(
                                turns: isExpanded ? 0.5 : 0,
                                duration: const Duration(milliseconds: 300),
                                child: Icon(
                                  Icons.keyboard_arrow_down_rounded,
                                  color: _textSecondary,
                                  size: 20,
                                ),
                              ),
                          ],
                        ),

                        const SizedBox(height: 6),

                        // Description
                        Text(
                          unit.description,
                          style: GoogleFonts.inter(
                            fontSize: 12,
                            color: _textSecondary,
                            height: 1.5,
                          ),
                        ),

                        // Expanded lesson list
                        AnimatedSize(
                          duration: const Duration(milliseconds: 320),
                          curve: Curves.easeInOut,
                          child: isExpanded
                              ? Column(
                                  children: [
                                    const SizedBox(height: 12),
                                    Divider(
                                      color: _textMuted.withOpacity(0.25),
                                      height: 1,
                                    ),
                                    const SizedBox(height: 8),
                                    ...unit.lessons.map(
                                      (lesson) => _LessonRow(
                                        lesson: lesson,
                                        unitLocked: isLocked,
                                      ),
                                    ),
                                  ],
                                )
                              : const SizedBox.shrink(),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ─── Unit Number Circle ───────────────────────────────────────────────────────
class _UnitNumberCircle extends StatelessWidget {
  final int number;
  final Color stripColor;

  const _UnitNumberCircle({required this.number, required this.stripColor});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 30,
      height: 30,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: stripColor.withOpacity(0.15),
        border: Border.all(color: stripColor.withOpacity(0.4), width: 1.5),
      ),
      child: Center(
        child: Text(
          '$number',
          style: GoogleFonts.inter(
            fontSize: 13,
            fontWeight: FontWeight.w700,
            color: stripColor,
          ),
        ),
      ),
    );
  }
}

// ─── Status Icon ──────────────────────────────────────────────────────────────
class _StatusIcon extends StatelessWidget {
  final UnitStatus status;
  const _StatusIcon({required this.status});

  @override
  Widget build(BuildContext context) {
    switch (status) {
      case UnitStatus.completed:
        return const Icon(Icons.check_circle_rounded, color: _success, size: 20);
      case UnitStatus.inProgress:
        return _PulsingDot();
      case UnitStatus.locked:
        return const Icon(Icons.lock_rounded, color: _textMuted, size: 18);
    }
  }
}

// ─── Pulsing Dot (in-progress indicator) ─────────────────────────────────────
class _PulsingDot extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      width: 10,
      height: 10,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: _primary,
      ),
    )
        .animate(onPlay: (ctrl) => ctrl.repeat(reverse: true))
        .scaleXY(begin: 1.0, end: 1.5, duration: 700.ms, curve: Curves.easeInOut)
        .fadeIn(begin: 0.5, duration: 700.ms, curve: Curves.easeInOut);
  }
}

// ─── Lesson Row ───────────────────────────────────────────────────────────────
class _LessonRow extends StatelessWidget {
  final LessonData lesson;
  final bool unitLocked;

  const _LessonRow({required this.lesson, required this.unitLocked});

  IconData get _typeIcon {
    switch (lesson.type) {
      case LessonType.pronunciation: return Icons.mic_rounded;
      case LessonType.grammar:       return Icons.menu_book_rounded;
      case LessonType.vocabulary:    return Icons.label_rounded;
      case LessonType.exam:          return Icons.emoji_events_rounded;
    }
  }

  Color get _typeColor {
    switch (lesson.type) {
      case LessonType.pronunciation: return const Color(0xFFEC4899);
      case LessonType.grammar:       return const Color(0xFF8B5CF6);
      case LessonType.vocabulary:    return const Color(0xFF14B8A6);
      case LessonType.exam:          return const Color(0xFFF59E0B);
    }
  }

  @override
  Widget build(BuildContext context) {
    final isLocked = lesson.status == LessonStatus.locked;
    final isInProgress = lesson.status == LessonStatus.inProgress;
    final isCompleted = lesson.status == LessonStatus.completed;

    return Opacity(
      opacity: isLocked ? 0.45 : 1.0,
      child: GestureDetector(
        onTap: isLocked ? null : () => context.push('/lesson', extra: lesson.name),
        behavior: HitTestBehavior.opaque,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(
          children: [
            // Type icon
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: _typeColor.withOpacity(0.12),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(_typeIcon, color: _typeColor, size: 16),
            ),
            const SizedBox(width: 10),

            // Lesson name
            Expanded(
              child: Text(
                lesson.name,
                style: GoogleFonts.inter(
                  fontSize: 13,
                  fontWeight: isInProgress ? FontWeight.w600 : FontWeight.w500,
                  color: isLocked ? _textMuted : _textPrimary,
                ),
              ),
            ),

            const SizedBox(width: 8),

            // Status indicator
            if (isCompleted)
              const Icon(Icons.check_circle_rounded, color: _success, size: 20)
            else if (isInProgress)
              _InProgressIndicator()
            else
              const Icon(Icons.lock_outline_rounded, color: _textMuted, size: 18),
          ],
        ),
      ),
      ),
    );
  }
}

// ─── In-Progress Lesson Indicator ────────────────────────────────────────────
class _InProgressIndicator extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Stack(
      alignment: Alignment.center,
      children: [
        Icon(Icons.radio_button_unchecked_rounded, color: _primary.withOpacity(0.3), size: 22),
        Container(
          width: 8,
          height: 8,
          decoration: const BoxDecoration(
            shape: BoxShape.circle,
            color: _primary,
          ),
        )
            .animate(onPlay: (ctrl) => ctrl.repeat(reverse: true))
            .scaleXY(begin: 0.8, end: 1.3, duration: 600.ms, curve: Curves.easeInOut),
      ],
    );
  }
}

// ─── Quick Action Tile ───────────────────────────────────────────────────────
class _QuickActionTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final List<Color> gradientColors;
  final VoidCallback onTap;

  const _QuickActionTile({
    required this.icon,
    required this.label,
    required this.gradientColors,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 14),
          decoration: BoxDecoration(
            color: _surfaceCard,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: _border, width: 1),
          ),
          child: Column(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  gradient: LinearGradient(colors: gradientColors),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: Colors.white, size: 20),
              ),
              const SizedBox(height: 8),
              Text(
                label,
                textAlign: TextAlign.center,
                style: GoogleFonts.inter(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: _textPrimary,
                  height: 1.2,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
