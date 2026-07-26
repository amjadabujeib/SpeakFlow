import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../core/theme/app_colors.dart';
import 'onboarding_screen.dart';
import 'plp_repository.dart';

class FirstRunGate extends StatefulWidget {
  final PlpRepository? repository;

  const FirstRunGate({super.key, this.repository});

  @override
  State<FirstRunGate> createState() => _FirstRunGateState();
}

class _FirstRunGateState extends State<FirstRunGate> {
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
      _enterApp();
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
        await _repository.latestGeneration();
        if (!mounted) return;
        _enterApp();
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
