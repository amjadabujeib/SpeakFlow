// lib/features/shell/settings/settings_drawer.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:speakflow/core/theme/local_fonts.dart';
import '../../../app/providers.dart';
import '../../../core/data/phoneme_progress_store.dart';
import '../../../core/data/practice_word_store.dart';
import '../../../core/providers/app_state.dart';
import '../../../core/theme/app_colors.dart';
import '../../learning_plan/data/plp_repository.dart';

part 'settings_drawer_body.dart';
part 'settings_drawer_components.dart';

class SettingsDrawer extends ConsumerStatefulWidget {
  final AppState appState;
  final PlpRepository? repository;

  const SettingsDrawer({super.key, required this.appState, this.repository});

  @override
  ConsumerState<SettingsDrawer> createState() => _SettingsDrawerState();
}

class _SettingsDrawerState extends ConsumerState<SettingsDrawer> {
  void _update(VoidCallback change) => setState(change);

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
    _repository = widget.repository ?? ref.read(plpRepositoryProvider);
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
        'timezone_offset_minutes': DateTime.now().timeZoneOffset.inMinutes,
      });
      final jobId = await _repository.generatePlan(regenerate: true);
      if (!mounted) return;
      widget.appState.setMotherTongue(_selectedMotherTongue);
      widget.appState.setCefrLevel(_selectedCefrLevel);
      widget.appState.setInterests(_selectedInterests.toList());
      widget.appState.trackPlanGeneration(jobId);
      widget.appState.requestPlanRefresh();
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
    final auth = ref.read(authSessionStoreProvider);
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
    final wasGuest = auth.isGuest;
    var serverSignOutFailed = false;
    try {
      await ref.read(authApiProvider).signOut();
    } catch (_) {
      serverSignOutFailed = true;
      await ref.read(authApiProvider).forgetSession();
    }
    if (wasGuest) {
      await PracticeWordStore.instance.clear();
      await PhonemeProgressStore.instance.clear();
    }
    if (!mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    widget.appState.resetLearnerState();
    Navigator.pop(context);
    router.go('/auth');
    if (serverSignOutFailed) {
      messenger.showSnackBar(
        const SnackBar(
          content: Text(
            'Signed out on this device. The server could not be reached to revoke the session.',
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) => _buildDrawer(context);
}
