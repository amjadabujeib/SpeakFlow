// lib/shared/widgets/settings_drawer.dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:speakflow/core/theme/local_fonts.dart';
import '../../core/auth/auth_session_store.dart';
import '../../core/data/phoneme_progress_store.dart';
import '../../core/data/practice_word_store.dart';
import '../../app/providers.dart';
import '../../core/theme/app_colors.dart';
import '../../core/providers/app_state.dart';
import '../../plp/plp_repository.dart';

class SettingsDrawer extends StatefulWidget {
  final AppState appState;
  final PlpRepository? repository;

  const SettingsDrawer({super.key, required this.appState, this.repository});

  @override
  State<SettingsDrawer> createState() => _SettingsDrawerState();
}

class _SettingsDrawerState extends State<SettingsDrawer> {
  late final PlpRepository _repository;
  late String _selectedMotherTongue;
  late String _selectedCefrLevel;
  late Set<String> _selectedInterests;
  late double _fontSize;
  List<String> _learningGoals = const ['Speak confidently'];
  bool _loadingProfile = true;
  bool _regenerating = false;
  bool _signingOut = false;

  static const _languages = [
    'Arabic',
    'Kurdish',
    'Turkish',
    'French',
    'Spanish',
  ];
  static const _levels = ['A1', 'A2', 'B1', 'B2'];
  static const _interests = [
    'Technology',
    'Travel',
    'Business',
    'Education',
    'Culture',
    'Science',
    'Sports',
    'Daily life',
    'Music',
    'History',
  ];

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? HttpPlpRepository();
    _selectedMotherTongue = widget.appState.motherTongue;
    _selectedCefrLevel = widget.appState.cefrLevel;
    _selectedInterests = widget.appState.interests.toSet();
    _fontSize = widget.appState.fontSize;
    _loadProfile();
  }

  Future<void> _loadProfile() async {
    try {
      final profile = await _repository.loadProfile();
      if (!mounted) return;
      final goals = (profile['learning_goals'] as List<dynamic>? ?? const [])
          .map((item) => item.toString())
          .where((item) => item.isNotEmpty)
          .toList(growable: false);
      final interests = (profile['interests'] as List<dynamic>? ?? const [])
          .map((item) => item.toString())
          .where((item) => item.isNotEmpty)
          .toSet();
      setState(() {
        _selectedMotherTongue =
            profile['native_language']?.toString() ?? _selectedMotherTongue;
        _selectedCefrLevel =
            profile['cefr_level']?.toString() ?? _selectedCefrLevel;
        if (goals.isNotEmpty) _learningGoals = goals;
        if (interests.isNotEmpty) _selectedInterests = interests;
        _loadingProfile = false;
      });
      widget.appState.setMotherTongue(_selectedMotherTongue);
      widget.appState.setCefrLevel(_selectedCefrLevel);
      widget.appState.setInterests(_selectedInterests.toList());
    } catch (error) {
      if (!mounted) return;
      setState(() => _loadingProfile = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not load your learning profile: $error')),
      );
    }
  }

  Future<void> _regeneratePlan() async {
    if (_loadingProfile || _regenerating) return;
    if (_selectedInterests.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Choose at least one interest.')),
      );
      return;
    }
    setState(() => _regenerating = true);
    try {
      await _repository.saveProfile({
        'cefr_level': _selectedCefrLevel,
        'native_language': _selectedMotherTongue,
        'learning_goals': _learningGoals,
        'interests': _selectedInterests.toList(),
      });
      await _repository.generatePlan();
      if (!mounted) return;
      widget.appState.setMotherTongue(_selectedMotherTongue);
      widget.appState.setCefrLevel(_selectedCefrLevel);
      widget.appState.setInterests(_selectedInterests.toList());
      widget.appState.requestPlanRefresh();
      widget.appState.setTab(0);
      final messenger = ScaffoldMessenger.of(context);
      final router = GoRouter.maybeOf(context);
      Navigator.pop(context);
      router?.go('/home');
      messenger.showSnackBar(
        const SnackBar(
          content: Text('Your new plan is now being built on Home.'),
          backgroundColor: AppColors.primary,
          behavior: SnackBarBehavior.floating,
        ),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not regenerate your plan: $error')),
      );
    } finally {
      if (mounted) setState(() => _regenerating = false);
    }
  }

  Future<void> _signOut() async {
    if (_signingOut) return;
    final auth = AuthSessionStore.instance;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(auth.isGuest ? 'Leave guest session?' : 'Sign out?'),
        content: Text(
          auth.isGuest
              ? 'This guest cannot be recovered after you sign out. You can create an account if you want progress that you can return to later.'
              : 'You can sign back in with your email and password. Your plan, progress, and conversations will stay with your account.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: Text(auth.isGuest ? 'Leave guest' : 'Sign out'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() => _signingOut = true);
    final router = GoRouter.of(context);
    try {
      if (auth.isGuest) {
        await PracticeWordStore.instance.clear();
        await PhonemeProgressStore.instance.clear();
      }
      await AppDependencies.instance.auth.signOut();
    } catch (_) {
      // AuthApi still removes the local session when the backend is
      // unreachable, so the learner is never left stuck in an account.
    }
    if (!mounted) return;
    Navigator.pop(context);
    router.go('/auth');
  }

  @override
  Widget build(BuildContext context) {
    final isDark = widget.appState.isDarkMode;
    final bg = isDark ? AppColors.surface : AppColors.lightSurface;
    final textPrimary = isDark
        ? AppColors.textPrimary
        : AppColors.lightTextPrimary;
    final textSecondary = isDark
        ? AppColors.textSecondary
        : AppColors.lightTextSecondary;
    final cardBg = isDark
        ? AppColors.surfaceElevated
        : AppColors.lightSurfaceElevated;
    final border = isDark ? AppColors.border : AppColors.lightBorder;

    return Drawer(
      width: MediaQuery.of(context).size.width * 0.85,
      backgroundColor: bg,
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
              child: Row(
                children: [
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      gradient: AppColors.primaryGradient,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Icon(
                      Icons.tune_rounded,
                      color: Colors.white,
                      size: 18,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text(
                    'Settings',
                    style: GoogleFonts.inter(
                      fontSize: 22,
                      fontWeight: FontWeight.w700,
                      color: textPrimary,
                    ),
                  ),
                  const Spacer(),
                  IconButton(
                    onPressed: () => Navigator.pop(context),
                    icon: Icon(Icons.close_rounded, color: textSecondary),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 24),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                children: [
                  _SectionLabel(label: 'Appearance', textColor: textSecondary),
                  const SizedBox(height: 8),
                  // Font size
                  _SettingsCard(
                    bg: cardBg,
                    border: border,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Icon(
                              Icons.text_fields_rounded,
                              color: AppColors.primary,
                              size: 20,
                            ),
                            const SizedBox(width: 12),
                            Text(
                              'Font Size',
                              style: GoogleFonts.inter(
                                fontSize: 14,
                                fontWeight: FontWeight.w500,
                                color: textPrimary,
                              ),
                            ),
                            const Spacer(),
                            Text(
                              _fontSize == 0.85
                                  ? 'Small'
                                  : _fontSize == 1.0
                                  ? 'Medium'
                                  : _fontSize == 1.15
                                  ? 'Large'
                                  : 'X-Large',
                              style: GoogleFonts.inter(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: AppColors.primary,
                              ),
                            ),
                          ],
                        ),
                        Slider(
                          value: _fontSize,
                          min: 0.85,
                          max: 1.3,
                          divisions: 3,
                          activeColor: AppColors.primary,
                          inactiveColor: AppColors.border,
                          onChanged: (v) {
                            setState(() => _fontSize = v);
                            widget.appState.setFontSize(v);
                          },
                        ),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              'A',
                              style: GoogleFonts.inter(
                                fontSize: 11,
                                color: textSecondary,
                              ),
                            ),
                            Text(
                              'A',
                              style: GoogleFonts.inter(
                                fontSize: 14,
                                color: textSecondary,
                              ),
                            ),
                            Text(
                              'A',
                              style: GoogleFonts.inter(
                                fontSize: 17,
                                color: textSecondary,
                              ),
                            ),
                            Text(
                              'A',
                              style: GoogleFonts.inter(
                                fontSize: 20,
                                color: textSecondary,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 24),
                  _SectionLabel(label: 'Learning', textColor: textSecondary),

                  // Mother tongue
                  _SettingsCard(
                    bg: cardBg,
                    border: border,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Icon(
                              Icons.translate_rounded,
                              color: AppColors.accent,
                              size: 20,
                            ),
                            const SizedBox(width: 12),
                            Text(
                              'Mother Tongue',
                              style: GoogleFonts.inter(
                                fontSize: 14,
                                fontWeight: FontWeight.w500,
                                color: textPrimary,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        DropdownButtonFormField<String>(
                          initialValue: _selectedMotherTongue,
                          dropdownColor: cardBg,
                          style: GoogleFonts.inter(
                            fontSize: 14,
                            color: textPrimary,
                          ),
                          decoration: InputDecoration(
                            contentPadding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 10,
                            ),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(10),
                              borderSide: BorderSide(color: border),
                            ),
                            enabledBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(10),
                              borderSide: BorderSide(color: border),
                            ),
                            filled: true,
                            fillColor: isDark
                                ? AppColors.surface
                                : AppColors.lightBackground,
                          ),
                          items: _languages
                              .map(
                                (l) =>
                                    DropdownMenuItem(value: l, child: Text(l)),
                              )
                              .toList(),
                          onChanged: (v) {
                            if (v != null) {
                              setState(() => _selectedMotherTongue = v);
                              widget.appState.setMotherTongue(v);
                            }
                          },
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),

                  // CEFR Level
                  _SettingsCard(
                    bg: cardBg,
                    border: border,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Icon(
                              Icons.bar_chart_rounded,
                              color: AppColors.accent,
                              size: 20,
                            ),
                            const SizedBox(width: 12),
                            Text(
                              'CEFR Level',
                              style: GoogleFonts.inter(
                                fontSize: 14,
                                fontWeight: FontWeight.w500,
                                color: textPrimary,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: _levels.map((level) {
                            final isSelected = _selectedCefrLevel == level;
                            return GestureDetector(
                              onTap: () {
                                setState(() => _selectedCefrLevel = level);
                              },
                              child: AnimatedContainer(
                                duration: const Duration(milliseconds: 200),
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 16,
                                  vertical: 8,
                                ),
                                decoration: BoxDecoration(
                                  gradient: isSelected
                                      ? AppColors.primaryGradient
                                      : null,
                                  color: isSelected
                                      ? null
                                      : (isDark
                                            ? AppColors.surface
                                            : AppColors.lightBackground),
                                  borderRadius: BorderRadius.circular(8),
                                  border: Border.all(
                                    color: isSelected
                                        ? Colors.transparent
                                        : border,
                                  ),
                                ),
                                child: Text(
                                  level,
                                  style: GoogleFonts.inter(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w600,
                                    color: isSelected
                                        ? Colors.white
                                        : textSecondary,
                                  ),
                                ),
                              ),
                            );
                          }).toList(),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),

                  // Interests
                  _SettingsCard(
                    bg: cardBg,
                    border: border,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Icon(
                              Icons.interests_rounded,
                              color: AppColors.accent,
                              size: 20,
                            ),
                            const SizedBox(width: 12),
                            Text(
                              'Interests',
                              style: GoogleFonts.inter(
                                fontSize: 14,
                                fontWeight: FontWeight.w500,
                                color: textPrimary,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: _interests.map((interest) {
                            final isSelected = _selectedInterests.contains(
                              interest,
                            );
                            return GestureDetector(
                              onTap: () {
                                setState(() {
                                  if (isSelected) {
                                    _selectedInterests.remove(interest);
                                  } else if (_selectedInterests.length < 3) {
                                    _selectedInterests.add(interest);
                                  }
                                });
                              },
                              child: AnimatedContainer(
                                duration: const Duration(milliseconds: 200),
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 12,
                                  vertical: 6,
                                ),
                                decoration: BoxDecoration(
                                  gradient: isSelected
                                      ? AppColors.primaryGradient
                                      : null,
                                  color: isSelected
                                      ? null
                                      : (isDark
                                            ? AppColors.surface
                                            : AppColors.lightBackground),
                                  borderRadius: BorderRadius.circular(20),
                                  border: Border.all(
                                    color: isSelected
                                        ? Colors.transparent
                                        : border,
                                  ),
                                ),
                                child: Text(
                                  interest,
                                  style: GoogleFonts.inter(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w500,
                                    color: isSelected
                                        ? Colors.white
                                        : textSecondary,
                                  ),
                                ),
                              ),
                            );
                          }).toList(),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 24),

                  // Regenerate plan button
                  GestureDetector(
                    onTap: _loadingProfile || _regenerating
                        ? null
                        : _regeneratePlan,
                    child: Opacity(
                      opacity: _loadingProfile || _regenerating ? 0.65 : 1,
                      child: Container(
                        width: double.infinity,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        decoration: BoxDecoration(
                          gradient: AppColors.primaryGradient,
                          borderRadius: BorderRadius.circular(12),
                          boxShadow: [
                            BoxShadow(
                              color: AppColors.primary.withValues(alpha: 0.35),
                              blurRadius: 16,
                              offset: const Offset(0, 6),
                            ),
                          ],
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            if (_regenerating)
                              const SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.white,
                                ),
                              )
                            else
                              const Icon(
                                Icons.auto_awesome_rounded,
                                color: Colors.white,
                                size: 18,
                              ),
                            const SizedBox(width: 8),
                            Text(
                              _regenerating
                                  ? 'Creating your roadmap...'
                                  : 'Apply changes & build plan',
                              style: GoogleFonts.inter(
                                fontSize: 14,
                                fontWeight: FontWeight.w600,
                                color: Colors.white,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),
                  _SectionLabel(label: 'Account', textColor: textSecondary),
                  const SizedBox(height: 8),
                  _SettingsCard(
                    bg: cardBg,
                    border: border,
                    child: Row(
                      children: [
                        CircleAvatar(
                          backgroundColor: AppColors.primary.withValues(
                            alpha: 0.16,
                          ),
                          foregroundColor: AppColors.primary,
                          child: Icon(
                            AuthSessionStore.instance.isGuest
                                ? Icons.bolt_rounded
                                : Icons.person_rounded,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                AuthSessionStore.instance.user?['display_name']
                                        ?.toString() ??
                                    'Learner',
                                style: GoogleFonts.inter(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w700,
                                  color: textPrimary,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                AuthSessionStore.instance.isGuest
                                    ? 'Temporary guest'
                                    : AuthSessionStore.instance.user?['email']
                                              ?.toString() ??
                                          'Registered account',
                                overflow: TextOverflow.ellipsis,
                                style: GoogleFonts.inter(
                                  fontSize: 11,
                                  color: textSecondary,
                                ),
                              ),
                            ],
                          ),
                        ),
                        TextButton(
                          onPressed: _signingOut ? null : _signOut,
                          child: _signingOut
                              ? const SizedBox.square(
                                  dimension: 16,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : const Text('Sign out'),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  final String label;
  final Color textColor;
  const _SectionLabel({required this.label, required this.textColor});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Text(
        label.toUpperCase(),
        style: GoogleFonts.inter(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          color: textColor,
          letterSpacing: 1.2,
        ),
      ),
    );
  }
}

class _SettingsCard extends StatelessWidget {
  final Widget child;
  final Color bg;
  final Color border;
  const _SettingsCard({
    required this.child,
    required this.bg,
    required this.border,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: border),
      ),
      child: child,
    );
  }
}
