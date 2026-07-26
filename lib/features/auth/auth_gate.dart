import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/auth_session_store.dart';
import '../../core/theme/app_colors.dart';
import 'auth_screen.dart';

class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  bool _checking = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _resolve();
  }

  Future<void> _resolve() async {
    final store = AuthSessionStore.instance;
    if (!store.hasSession) {
      setState(() {
        _checking = false;
        _error = null;
      });
      return;
    }
    setState(() {
      _checking = true;
      _error = null;
    });
    try {
      final valid = await store.validate();
      if (!mounted) return;
      if (valid) {
        context.go('/start');
      } else {
        setState(() => _checking = false);
      }
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _checking = false;
        _error =
            'Could not verify your account. Check the backend connection and try again.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_checking) {
      return const Scaffold(
        backgroundColor: AppColors.background,
        body: Center(child: CircularProgressIndicator()),
      );
    }
    if (_error == null) return const AuthScreen();
    return Scaffold(
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
                  color: AppColors.textSecondary,
                  size: 48,
                ),
                const SizedBox(height: 14),
                Text(
                  _error!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: AppColors.textSecondary),
                ),
                const SizedBox(height: 18),
                FilledButton(
                  onPressed: _resolve,
                  child: const Text('Try again'),
                ),
                TextButton(
                  onPressed: () async {
                    await AuthSessionStore.instance.clear();
                    if (mounted) {
                      setState(() {
                        _checking = false;
                        _error = null;
                      });
                    }
                  },
                  child: const Text('Use another account'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
