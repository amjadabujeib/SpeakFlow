import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';

// Color constants
const _background = Color(0xFF090E1A);
const _surface = Color(0xFF111827);
const _surfaceElevated = Color(0xFF1A2235);
const _primary = Color(0xFF4F7FFF);
const _accent = Color(0xFF8B5CF6);
const _textPrimary = Color(0xFFF1F5FF);
const _textSecondary = Color(0xFF8896B0);
const _textMuted = Color(0xFF4A5568);
const _border = Color(0xFF1E2D45);

// ─── Data ──────────────────────────────────────────────────────────────────

const _levels = [
  {'level': 'A1', 'title': 'Total Beginner', 'desc': 'I know very few words'},
  {'level': 'A2', 'title': 'Elementary', 'desc': 'I handle simple conversations'},
  {'level': 'B1', 'title': 'Intermediate', 'desc': 'I manage most situations'},
  {'level': 'B2', 'title': 'Upper Intermediate', 'desc': 'I discuss complex topics'},
  {'level': 'C1', 'title': 'Advanced', 'desc': 'I express myself fluently'},
  {'level': 'C2', 'title': 'Mastery', 'desc': 'I understand everything'},
];

const _goals = [
  {'icon': '✈️', 'label': 'Travel & Tourism'},
  {'icon': '💼', 'label': 'Business & Career'},
  {'icon': '🎓', 'label': 'Academic Study'},
  {'icon': '💬', 'label': 'Daily Conversation'},
  {'icon': '🎬', 'label': 'Media & Entertainment'},
  {'icon': '🌍', 'label': 'Immigration'},
];

const _interests = [
  'Travel',
  'Business',
  'Technology',
  'Food & Cooking',
  'Sports',
  'Music',
  'Science',
  'History',
  'Health',
  'Arts & Culture',
];

const _languages = [
  'Arabic',
  'French',
  'Spanish',
  'German',
  'Chinese',
  'Japanese',
];

// ─── Main Screen ───────────────────────────────────────────────────────────

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  int _step = 0; // 0..3
  final int _totalSteps = 4;

  // Step 1 – CEFR level
  String? _selectedLevel;

  // Step 2 – Goal
  String? _selectedGoal;

  // Step 3 – Interests
  final Set<String> _selectedInterests = {};
  final TextEditingController _interestController = TextEditingController();
  final List<String> _allInterests = List.from(_interests);

  // Step 4 – Mother tongue
  String? _selectedLanguage;

  @override
  void dispose() {
    _interestController.dispose();
    super.dispose();
  }

  bool get _canProceed {
    switch (_step) {
      case 0:
        return _selectedLevel != null;
      case 1:
        return _selectedGoal != null;
      case 2:
        return _selectedInterests.isNotEmpty;
      case 3:
        return _selectedLanguage != null;
      default:
        return false;
    }
  }

  void _next() {
    if (!_canProceed) return;
    if (_step < _totalSteps - 1) {
      setState(() => _step++);
    } else {
      context.go('/loading');
    }
  }

  void _back() {
    if (_step > 0) setState(() => _step--);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _background,
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF090E1A), Color(0xFF0D1526)],
          ),
        ),
        child: SafeArea(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // ── Top bar ──────────────────────────────────────────────
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
                child: Row(
                  children: [
                    // Back button (hidden on step 0)
                    AnimatedOpacity(
                      opacity: _step > 0 ? 1.0 : 0.0,
                      duration: const Duration(milliseconds: 200),
                      child: GestureDetector(
                        onTap: _step > 0 ? _back : null,
                        child: Container(
                          width: 40,
                          height: 40,
                          decoration: BoxDecoration(
                            color: _surfaceElevated,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: _border),
                          ),
                          child: const Icon(
                            Icons.arrow_back_ios_new_rounded,
                            color: _textSecondary,
                            size: 16,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    // Progress bar
                    Expanded(
                      child: _GradientProgressBar(
                        progress: (_step + 1) / _totalSteps,
                      ),
                    ),
                    const SizedBox(width: 12),
                    // Step counter
                    Text(
                      '${_step + 1}/$_totalSteps',
                      style: GoogleFonts.inter(
                        fontSize: 13,
                        color: _textSecondary,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 28),
              // ── Step content ─────────────────────────────────────────
              Expanded(
                child: AnimatedSwitcher(
                  duration: const Duration(milliseconds: 350),
                  transitionBuilder: (child, animation) {
                    return FadeTransition(
                      opacity: animation,
                      child: SlideTransition(
                        position: Tween<Offset>(
                          begin: const Offset(0.08, 0),
                          end: Offset.zero,
                        ).animate(CurvedAnimation(
                          parent: animation,
                          curve: Curves.easeOutCubic,
                        )),
                        child: child,
                      ),
                    );
                  },
                  child: KeyedSubtree(
                    key: ValueKey(_step),
                    child: _buildStep(),
                  ),
                ),
              ),
              // ── Bottom button ─────────────────────────────────────────
              Padding(
                padding: const EdgeInsets.fromLTRB(24, 12, 24, 28),
                child: _GradientButton(
                  label: _step == _totalSteps - 1 ? 'Generate My Plan' : 'Next',
                  enabled: _canProceed,
                  onTap: _next,
                  trailingIcon: _step == _totalSteps - 1
                      ? Icons.auto_awesome_rounded
                      : Icons.arrow_forward_rounded,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStep() {
    switch (_step) {
      case 0:
        return _StepCefr(
          selected: _selectedLevel,
          onSelect: (v) => setState(() => _selectedLevel = v),
        );
      case 1:
        return _StepGoal(
          selected: _selectedGoal,
          onSelect: (v) => setState(() => _selectedGoal = v),
        );
      case 2:
        return _StepInterests(
          selected: _selectedInterests,
          allInterests: _allInterests,
          controller: _interestController,
          onToggle: (v) => setState(() {
            if (_selectedInterests.contains(v)) {
              _selectedInterests.remove(v);
            } else {
              _selectedInterests.add(v);
            }
          }),
          onAdd: (v) {
            if (v.isNotEmpty && !_allInterests.contains(v)) {
              setState(() {
                _allInterests.add(v);
                _selectedInterests.add(v);
              });
              _interestController.clear();
            }
          },
        );
      case 3:
        return _StepMotherTongue(
          selected: _selectedLanguage,
          onSelect: (v) => setState(() => _selectedLanguage = v),
        );
      default:
        return const SizedBox.shrink();
    }
  }
}

// ─── Gradient Progress Bar ─────────────────────────────────────────────────

class _GradientProgressBar extends StatelessWidget {
  final double progress;
  const _GradientProgressBar({required this.progress});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 6,
      decoration: BoxDecoration(
        color: _surfaceElevated,
        borderRadius: BorderRadius.circular(100),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(100),
        child: ShaderMask(
          shaderCallback: (bounds) => const LinearGradient(
            colors: [_primary, _accent],
          ).createShader(bounds),
          child: AnimatedFractionallySizedBox(
            duration: const Duration(milliseconds: 400),
            curve: Curves.easeOutCubic,
            widthFactor: progress,
            child: Container(color: Colors.white),
          ),
        ),
      ),
    );
  }
}

// ─── Gradient Button ───────────────────────────────────────────────────────

class _GradientButton extends StatefulWidget {
  final String label;
  final VoidCallback onTap;
  final bool enabled;
  final IconData? trailingIcon;

  const _GradientButton({
    required this.label,
    required this.onTap,
    this.enabled = true,
    this.trailingIcon,
  });

  @override
  State<_GradientButton> createState() => _GradientButtonState();
}

class _GradientButtonState extends State<_GradientButton> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: widget.enabled ? (_) => setState(() => _pressed = true) : null,
      onTapUp: widget.enabled
          ? (_) {
              setState(() => _pressed = false);
              widget.onTap();
            }
          : null,
      onTapCancel: () => setState(() => _pressed = false),
      child: AnimatedScale(
        scale: _pressed ? 0.97 : 1.0,
        duration: const Duration(milliseconds: 100),
        child: AnimatedOpacity(
          opacity: widget.enabled ? 1.0 : 0.4,
          duration: const Duration(milliseconds: 200),
          child: Container(
            height: 56,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [_primary, _accent],
                begin: Alignment.centerLeft,
                end: Alignment.centerRight,
              ),
              borderRadius: BorderRadius.circular(16),
              boxShadow: widget.enabled
                  ? [
                      BoxShadow(
                        color: _primary.withOpacity(0.35),
                        blurRadius: 20,
                        offset: const Offset(0, 6),
                      ),
                    ]
                  : [],
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  widget.label,
                  style: GoogleFonts.inter(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                    letterSpacing: 0.3,
                  ),
                ),
                if (widget.trailingIcon != null) ...[
                  const SizedBox(width: 8),
                  Icon(widget.trailingIcon, color: Colors.white, size: 18),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ─── Step Header ───────────────────────────────────────────────────────────

class _StepHeader extends StatelessWidget {
  final String emoji;
  final String title;
  final String subtitle;

  const _StepHeader({
    required this.emoji,
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(emoji, style: const TextStyle(fontSize: 36))
              .animate()
              .fadeIn(duration: 400.ms)
              .slideY(begin: 0.3, end: 0, duration: 400.ms),
          const SizedBox(height: 10),
          Text(
            title,
            style: GoogleFonts.inter(
              fontSize: 24,
              fontWeight: FontWeight.w800,
              color: _textPrimary,
            ),
          )
              .animate()
              .fadeIn(delay: 80.ms, duration: 400.ms)
              .slideY(begin: 0.3, end: 0, duration: 400.ms),
          const SizedBox(height: 6),
          Text(
            subtitle,
            style: GoogleFonts.inter(
              fontSize: 14,
              color: _textSecondary,
            ),
          )
              .animate()
              .fadeIn(delay: 130.ms, duration: 400.ms)
              .slideY(begin: 0.3, end: 0, duration: 400.ms),
        ],
      ),
    );
  }
}

// ─── Step 1: CEFR Level ────────────────────────────────────────────────────

class _StepCefr extends StatelessWidget {
  final String? selected;
  final ValueChanged<String> onSelect;

  const _StepCefr({required this.selected, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _StepHeader(
          emoji: '📊',
          title: "What's your level?",
          subtitle: 'Choose the option that best describes you',
        ),
        const SizedBox(height: 24),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: GridView.builder(
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                childAspectRatio: 1.15,
              ),
              itemCount: _levels.length,
              itemBuilder: (context, index) {
                final item = _levels[index];
                final level = item['level']!;
                final isSelected = selected == level;
                return _CefrCard(
                  level: level,
                  title: item['title']!,
                  desc: item['desc']!,
                  isSelected: isSelected,
                  onTap: () => onSelect(level),
                )
                    .animate()
                    .fadeIn(delay: (index * 60).ms, duration: 350.ms)
                    .slideY(begin: 0.25, end: 0, duration: 350.ms);
              },
            ),
          ),
        ),
      ],
    );
  }
}

class _CefrCard extends StatefulWidget {
  final String level;
  final String title;
  final String desc;
  final bool isSelected;
  final VoidCallback onTap;

  const _CefrCard({
    required this.level,
    required this.title,
    required this.desc,
    required this.isSelected,
    required this.onTap,
  });

  @override
  State<_CefrCard> createState() => _CefrCardState();
}

class _CefrCardState extends State<_CefrCard> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) {
        setState(() => _pressed = false);
        widget.onTap();
      },
      onTapCancel: () => setState(() => _pressed = false),
      child: AnimatedScale(
        scale: _pressed ? 0.96 : 1.0,
        duration: const Duration(milliseconds: 100),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 250),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: widget.isSelected
                ? _primary.withOpacity(0.08)
                : _surfaceElevated,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: widget.isSelected ? _primary : _border,
              width: widget.isSelected ? 1.5 : 1.0,
            ),
            boxShadow: widget.isSelected
                ? [
                    BoxShadow(
                      color: _primary.withOpacity(0.2),
                      blurRadius: 16,
                      spreadRadius: 1,
                    ),
                    BoxShadow(
                      color: _accent.withOpacity(0.1),
                      blurRadius: 12,
                    ),
                  ]
                : [],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              // Level badge
              ShaderMask(
                shaderCallback: (bounds) => const LinearGradient(
                  colors: [_primary, _accent],
                ).createShader(bounds),
                child: Text(
                  widget.level,
                  style: GoogleFonts.inter(
                    fontSize: 28,
                    fontWeight: FontWeight.w900,
                    color: Colors.white,
                  ),
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    widget.title,
                    style: GoogleFonts.inter(
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: _textPrimary,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    widget.desc,
                    style: GoogleFonts.inter(
                      fontSize: 11,
                      color: _textSecondary,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ─── Step 2: Learning Goal ─────────────────────────────────────────────────

class _StepGoal extends StatelessWidget {
  final String? selected;
  final ValueChanged<String> onSelect;

  const _StepGoal({required this.selected, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _StepHeader(
          emoji: '🎯',
          title: 'What\'s your goal?',
          subtitle: 'Pick your primary reason for learning',
        ),
        const SizedBox(height: 24),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: GridView.builder(
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                childAspectRatio: 1.7,
              ),
              itemCount: _goals.length,
              itemBuilder: (context, index) {
                final item = _goals[index];
                final label = item['label']!;
                final isSelected = selected == label;
                return _GoalCard(
                  icon: item['icon']!,
                  label: label,
                  isSelected: isSelected,
                  onTap: () => onSelect(label),
                )
                    .animate()
                    .fadeIn(delay: (index * 60).ms, duration: 350.ms)
                    .slideY(begin: 0.25, end: 0, duration: 350.ms);
              },
            ),
          ),
        ),
      ],
    );
  }
}

class _GoalCard extends StatefulWidget {
  final String icon;
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const _GoalCard({
    required this.icon,
    required this.label,
    required this.isSelected,
    required this.onTap,
  });

  @override
  State<_GoalCard> createState() => _GoalCardState();
}

class _GoalCardState extends State<_GoalCard> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) {
        setState(() => _pressed = false);
        widget.onTap();
      },
      onTapCancel: () => setState(() => _pressed = false),
      child: AnimatedScale(
        scale: _pressed ? 0.96 : 1.0,
        duration: const Duration(milliseconds: 100),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 250),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            color: widget.isSelected
                ? _primary.withOpacity(0.1)
                : _surfaceElevated,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: widget.isSelected ? _primary : _border,
              width: widget.isSelected ? 1.5 : 1.0,
            ),
            boxShadow: widget.isSelected
                ? [
                    BoxShadow(
                      color: _primary.withOpacity(0.18),
                      blurRadius: 14,
                      spreadRadius: 1,
                    ),
                  ]
                : [],
          ),
          child: Row(
            children: [
              Text(widget.icon, style: const TextStyle(fontSize: 22)),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  widget.label,
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: widget.isSelected
                        ? FontWeight.w700
                        : FontWeight.w500,
                    color: widget.isSelected ? _textPrimary : _textSecondary,
                  ),
                ),
              ),
              if (widget.isSelected)
                Container(
                  width: 20,
                  height: 20,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: const LinearGradient(
                      colors: [_primary, _accent],
                    ),
                  ),
                  child: const Icon(
                    Icons.check,
                    color: Colors.white,
                    size: 12,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

// ─── Step 3: Interests ─────────────────────────────────────────────────────

class _StepInterests extends StatelessWidget {
  final Set<String> selected;
  final List<String> allInterests;
  final TextEditingController controller;
  final ValueChanged<String> onToggle;
  final ValueChanged<String> onAdd;

  const _StepInterests({
    required this.selected,
    required this.allInterests,
    required this.controller,
    required this.onToggle,
    required this.onAdd,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _StepHeader(
          emoji: '✨',
          title: 'Your interests',
          subtitle: 'Pick topics you love — we\'ll tailor your content',
        ),
        const SizedBox(height: 24),
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: allInterests.asMap().entries.map((entry) {
                    final index = entry.key;
                    final interest = entry.value;
                    final isSelected = selected.contains(interest);
                    return _InterestChip(
                      label: interest,
                      isSelected: isSelected,
                      onTap: () => onToggle(interest),
                    )
                        .animate()
                        .fadeIn(
                            delay: (index * 40).ms, duration: 300.ms)
                        .scale(
                            begin: const Offset(0.85, 0.85),
                            duration: 300.ms,
                            curve: Curves.easeOutBack);
                  }).toList(),
                ),
                const SizedBox(height: 24),
                Text(
                  'Add your own',
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: _textSecondary,
                  ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: controller,
                        style: GoogleFonts.inter(
                            color: _textPrimary, fontSize: 14),
                        decoration: InputDecoration(
                          hintText: 'e.g. Cooking, Anime...',
                          hintStyle: GoogleFonts.inter(
                              color: _textMuted, fontSize: 14),
                          filled: true,
                          fillColor: _surfaceElevated,
                          contentPadding: const EdgeInsets.symmetric(
                              horizontal: 16, vertical: 14),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: const BorderSide(color: _border),
                          ),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: const BorderSide(color: _border),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: const BorderSide(
                                color: _primary, width: 1.5),
                          ),
                        ),
                        onSubmitted: onAdd,
                      ),
                    ),
                    const SizedBox(width: 10),
                    GestureDetector(
                      onTap: () => onAdd(controller.text.trim()),
                      child: Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [_primary, _accent],
                          ),
                          borderRadius: BorderRadius.circular(12),
                          boxShadow: [
                            BoxShadow(
                              color: _primary.withOpacity(0.3),
                              blurRadius: 12,
                              offset: const Offset(0, 4),
                            ),
                          ],
                        ),
                        child: const Icon(Icons.add, color: Colors.white, size: 22),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _InterestChip extends StatefulWidget {
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const _InterestChip({
    required this.label,
    required this.isSelected,
    required this.onTap,
  });

  @override
  State<_InterestChip> createState() => _InterestChipState();
}

class _InterestChipState extends State<_InterestChip> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) {
        setState(() => _pressed = false);
        widget.onTap();
      },
      onTapCancel: () => setState(() => _pressed = false),
      child: AnimatedScale(
        scale: _pressed ? 0.94 : 1.0,
        duration: const Duration(milliseconds: 100),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
          decoration: BoxDecoration(
            color: widget.isSelected
                ? _primary.withOpacity(0.12)
                : _surfaceElevated,
            borderRadius: BorderRadius.circular(100),
            border: Border.all(
              color: widget.isSelected ? _primary : _border,
              width: widget.isSelected ? 1.5 : 1.0,
            ),
            boxShadow: widget.isSelected
                ? [
                    BoxShadow(
                      color: _primary.withOpacity(0.15),
                      blurRadius: 10,
                    ),
                  ]
                : [],
          ),
          child: Text(
            widget.isSelected ? '✓  ${widget.label}' : widget.label,
            style: GoogleFonts.inter(
              fontSize: 13,
              fontWeight:
                  widget.isSelected ? FontWeight.w700 : FontWeight.w500,
              color: widget.isSelected ? _primary : _textSecondary,
            ),
          ),
        ),
      ),
    );
  }
}

// ─── Step 4: Mother Tongue ─────────────────────────────────────────────────

class _StepMotherTongue extends StatelessWidget {
  final String? selected;
  final ValueChanged<String?> onSelect;

  const _StepMotherTongue({required this.selected, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _StepHeader(
            emoji: '🌐',
            title: 'Mother tongue',
            subtitle: 'This helps us tailor explanations for you',
          ),
          const SizedBox(height: 32),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Select your native language',
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: _textSecondary,
                  ),
                ),
                const SizedBox(height: 12),
                Container(
                  decoration: BoxDecoration(
                    color: _surfaceElevated,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(
                      color: selected != null ? _primary : _border,
                      width: selected != null ? 1.5 : 1.0,
                    ),
                    boxShadow: selected != null
                        ? [
                            BoxShadow(
                              color: _primary.withOpacity(0.15),
                              blurRadius: 14,
                            ),
                          ]
                        : [],
                  ),
                  child: DropdownButtonFormField<String>(
                    value: selected,
                    dropdownColor: const Color(0xFF151E30),
                    icon: const Icon(
                      Icons.keyboard_arrow_down_rounded,
                      color: _textSecondary,
                    ),
                    style: GoogleFonts.inter(
                      color: _textPrimary,
                      fontSize: 15,
                    ),
                    decoration: InputDecoration(
                      contentPadding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 18),
                      border: InputBorder.none,
                      hintText: 'Choose a language...',
                      hintStyle: GoogleFonts.inter(
                        color: _textMuted,
                        fontSize: 15,
                      ),
                    ),
                    items: _languages.map((lang) {
                      return DropdownMenuItem(
                        value: lang,
                        child: Text(
                          lang,
                          style: GoogleFonts.inter(
                            color: _textPrimary,
                            fontSize: 15,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      );
                    }).toList(),
                    onChanged: onSelect,
                  ),
                )
                    .animate()
                    .fadeIn(delay: 200.ms, duration: 400.ms)
                    .slideY(begin: 0.3, end: 0, duration: 400.ms),
                const SizedBox(height: 32),
                // Info card
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: _primary.withOpacity(0.06),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(
                      color: _primary.withOpacity(0.2),
                    ),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(
                        Icons.info_outline_rounded,
                        color: _primary,
                        size: 20,
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          'We\'ll use your native language to explain grammar rules and new vocabulary in a way that makes sense to you.',
                          style: GoogleFonts.inter(
                            fontSize: 13,
                            color: _textSecondary,
                            height: 1.5,
                          ),
                        ),
                      ),
                    ],
                  ),
                )
                    .animate()
                    .fadeIn(delay: 350.ms, duration: 400.ms)
                    .slideY(begin: 0.3, end: 0, duration: 400.ms),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
