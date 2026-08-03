import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:speakflow/core/theme/local_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../app/providers.dart';

part 'onboarding_chrome.dart';
part 'onboarding_cefr_step.dart';
part 'onboarding_goal_step.dart';
part 'onboarding_interests_step.dart';
part 'onboarding_language_step.dart';

// Color constants
const _background = Color(0xFF090E1A);
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
  {
    'level': 'A2',
    'title': 'Elementary',
    'desc': 'I handle simple conversations',
  },
  {'level': 'B1', 'title': 'Intermediate', 'desc': 'I manage most situations'},
  {
    'level': 'B2',
    'title': 'Upper Intermediate',
    'desc': 'I discuss complex topics',
  },
];

const _goals = [
  {'icon': '💬', 'label': 'Speak confidently'},
  {'icon': '✈️', 'label': 'Travel independently'},
  {'icon': '💼', 'label': 'Communicate at work'},
  {'icon': '🎓', 'label': 'Study in English'},
  {'icon': '📝', 'label': 'Prepare for exams'},
];

const _interests = [
  'Travel',
  'Business',
  'Technology',
  'Sports',
  'Science',
  'Education',
  'Culture',
  'Daily life',
];

const _languages = ['Arabic', 'Kurdish', 'Turkish', 'French', 'Spanish'];

// ─── Main Screen ───────────────────────────────────────────────────────────

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
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
  bool _submitting = false;

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

  Future<void> _next() async {
    if (!_canProceed || _submitting) return;
    if (_step < _totalSteps - 1) {
      setState(() => _step++);
    } else {
      setState(() => _submitting = true);
      try {
        final learningPlan = ref.read(learningPlanApiProvider);
        await learningPlan.saveProfile({
          'cefr_level': _selectedLevel,
          'native_language': _selectedLanguage,
          'learning_goals': [_selectedGoal],
          'interests': _selectedInterests.take(3).toList(),
        });
        await learningPlan.generate();
        if (mounted) context.go('/loading');
      } catch (error) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Could not start your learning plan: $error'),
            backgroundColor: const Color(0xFFEF4444),
          ),
        );
      } finally {
        if (mounted) setState(() => _submitting = false);
      }
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
                        position:
                            Tween<Offset>(
                              begin: const Offset(0.08, 0),
                              end: Offset.zero,
                            ).animate(
                              CurvedAnimation(
                                parent: animation,
                                curve: Curves.easeOutCubic,
                              ),
                            ),
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
            } else if (_selectedInterests.length < 3) {
              _selectedInterests.add(v);
            }
          }),
          onAdd: (v) {
            if (v.isNotEmpty &&
                _selectedInterests.length < 3 &&
                !_allInterests.contains(v)) {
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
