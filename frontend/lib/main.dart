// lib/main.dart
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/services.dart';
import 'core/theme/app_theme.dart';
import 'core/theme/app_colors.dart';
import 'core/auth/auth_session_store.dart';
import 'core/network/api_config.dart';
import 'core/providers/app_state.dart';
import 'app/router.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  if (kReleaseMode) {
    final api = Uri.parse(ApiConfig.origin);
    final websocket = Uri.parse(ApiConfig.websocketOrigin);
    if (api.scheme != 'https' || websocket.scheme != 'wss') {
      throw StateError(
        'Release builds require SPEAKFLOW_API_URL=https://... and '
        'SPEAKFLOW_WS_URL=wss://... dart defines.',
      );
    }
  }
  await AuthSessionStore.instance.restore();
  final appState = AppState();
  await appState.restorePreferences();
  var hadSession = AuthSessionStore.instance.hasSession;
  AuthSessionStore.instance.addListener(() {
    final hasSession = AuthSessionStore.instance.hasSession;
    if (hadSession && !hasSession) appState.resetLearnerState();
    hadSession = hasSession;
  });
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);
  runApp(const ProviderScope(child: SpeakFlowApp()));
}

class SpeakFlowApp extends StatelessWidget {
  const SpeakFlowApp({super.key});

  @override
  Widget build(BuildContext context) {
    final appState = AppState();
    return MaterialApp.router(
      title: 'SpeakFlow',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      routerConfig: appRouter,
      builder: (context, child) => AnimatedBuilder(
        animation: appState,
        builder: (context, _) => AnnotatedRegion<SystemUiOverlayStyle>(
          value: const SystemUiOverlayStyle(
            statusBarColor: Colors.transparent,
            statusBarIconBrightness: Brightness.light,
            systemNavigationBarColor: AppColors.background,
            systemNavigationBarIconBrightness: Brightness.light,
          ),
          child: MediaQuery(
            data: MediaQuery.of(
              context,
            ).copyWith(textScaler: TextScaler.linear(appState.fontSize)),
            child: child ?? const SizedBox.shrink(),
          ),
        ),
      ),
    );
  }
}
