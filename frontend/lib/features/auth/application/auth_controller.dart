import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/providers.dart';

class AuthController extends AsyncNotifier<void> {
  @override
  FutureOr<void> build() {}

  Future<bool> signUp({
    required String displayName,
    required String email,
    required String password,
  }) => _run(
    () => ref
        .read(authApiProvider)
        .signUp(displayName: displayName, email: email, password: password),
  );

  Future<bool> signIn({required String email, required String password}) =>
      _run(
        () =>
            ref.read(authApiProvider).signIn(email: email, password: password),
      );

  Future<bool> continueAsGuest() =>
      _run(() => ref.read(authApiProvider).continueAsGuest());

  void reset() => state = const AsyncData(null);

  Future<bool> _run(Future<Object?> Function() operation) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await operation();
    });
    return !state.hasError;
  }
}

final authControllerProvider = AsyncNotifierProvider<AuthController, void>(
  AuthController.new,
);
