import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/app_colors.dart';
import '../../../app/providers.dart';
import '../data/plp_repository.dart';
import 'onboarding_screen.dart';

class FirstRunGate extends ConsumerStatefulWidget {
  final PlpRepository? repository;

  const FirstRunGate({super.key, this.repository});

  @override
  ConsumerState<FirstRunGate> createState() => _FirstRunGateState();
}

class _FirstRunGateState extends ConsumerState<FirstRunGate> {
  late final PlpRepository _repository;
  _GateState _state = _GateState.checking;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? HttpPlpRepository();
    _resolve();
  }

  Future<void> _resolve() async {
    setState(() {
      _state = _GateState.checking;
      _error = null;
    });
    try {
      await _repository.loadPlan();
      if (!mounted) return;
      await _enterAppWithProfile();
    } on PlpApiException catch (error) {
      if (!mounted) return;
      if (error.statusCode != 404) {
        setState(() {
          _state = _GateState.failed;
          _error = error;
        });
        return;
      }
      try {
        final generation = await _repository.latestGeneration();
        if (!mounted) return;
        final status = generation['status']?.toString();
        const activeStatuses = {
          'queued',
          'generating_week_one',
          'generating_future_weeks',
          'waiting_for_model',
          'generating_initial',
          'generating_next',
          'idle',
        };
        if (!activeStatuses.contains(status)) {
          setState(() {
            _state = _GateState.failed;
            _error = 'The latest plan generation ended with status "$status".';
          });
          return;
        }
        await _enterAppWithProfile();
      } on PlpApiException catch (latestError) {
        if (!mounted) return;
        if (latestError.statusCode == 404) {
          setState(() => _state = _GateState.onboarding);
        } else {
          setState(() {
            _state = _GateState.failed;
            _error = latestError;
          });
        }
      } catch (latestError) {
        if (!mounted) return;
        setState(() {
          _state = _GateState.failed;
          _error = latestError;
        });
      }
    } catch (error) {
      if (error is UnsupportedError) {
        _enterApp();
        return;
      }
      if (!mounted) return;
      setState(() {
        _state = _GateState.failed;
        _error = error;
      });
    }
  }

  void _enterApp() {
    if (!mounted) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) context.go('/home');
    });
  }

  Future<void> _enterAppWithProfile() async {
    try {
      final profile = await _repository.loadProfile();
      final state = ref.read(appStateProvider);
      final language = profile['native_language']?.toString();
      final level = profile['cefr_level']?.toString();
      final interests = (profile['interests'] as List<dynamic>? ?? const [])
          .map((item) => item.toString())
          .where((item) => item.isNotEmpty)
          .toList(growable: false);
      if (language != null) state.setMotherTongue(language);
      if (level != null) state.setCefrLevel(level);
      if (interests.isNotEmpty) state.setInterests(interests);
    } catch (error) {
      if (error is UnsupportedError) {
        _enterApp();
        return;
      }
      if (!mounted) return;
      setState(() {
        _state = _GateState.failed;
        _error = error;
      });
      return;
    }
    _enterApp();
  }

  @override
  Widget build(BuildContext context) {
    return switch (_state) {
      _GateState.checking => const Scaffold(
        backgroundColor: AppColors.background,
        body: Center(child: CircularProgressIndicator()),
      ),
      _GateState.onboarding => PlpOnboardingScreen(
        repository: _repository,
        allowBack: false,
        onGenerationStarted: (_) => _enterApp(),
      ),
      _GateState.failed => Scaffold(
        backgroundColor: AppColors.background,
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(28),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(
                    Icons.cloud_off_rounded,
                    color: AppColors.error,
                    size: 52,
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    'Could not check your learning plan',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 21, fontWeight: FontWeight.w900),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '$_error',
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: AppColors.textSecondary),
                  ),
                  const SizedBox(height: 20),
                  FilledButton.icon(
                    onPressed: _resolve,
                    icon: const Icon(Icons.refresh_rounded),
                    label: const Text('Try again'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    };
  }
}

enum _GateState { checking, onboarding, failed }
