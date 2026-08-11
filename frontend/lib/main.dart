// lib/main.dart
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/services.dart';
import 'core/theme/app_theme.dart';
import 'core/theme/app_colors.dart';
import 'core/network/api_config.dart';
import 'app/router.dart';
import 'app/providers.dart';

double effectiveTextScale(double systemScale, double preferenceScale) =>
    (systemScale * preferenceScale).clamp(0.85, 2.0).toDouble();

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
  final container = ProviderContainer();
  final authStore = container.read(authSessionStoreProvider);
  final appState = container.read(appStateProvider);
  await authStore.restore();
  await appState.restorePreferences();
  var hadSession = authStore.hasSession;
  authStore.addListener(() {
    final hasSession = authStore.hasSession;
    if (hadSession && !hasSession) appState.resetLearnerState();
    hadSession = hasSession;
  });
  await SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);
  runApp(
    UncontrolledProviderScope(
      container: container,
      child: const SpeakFlowApp(),
    ),
  );
}

class SpeakFlowApp extends ConsumerWidget {
  const SpeakFlowApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final appState = ref.watch(appStateProvider);
    final router = ref.watch(appRouterProvider);
    return MaterialApp.router(
      title: 'SpeakFlow',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      routerConfig: router,
      builder: (context, child) => AnnotatedRegion<SystemUiOverlayStyle>(
        value: const SystemUiOverlayStyle(
          statusBarColor: Colors.transparent,
          statusBarIconBrightness: Brightness.light,
          systemNavigationBarColor: AppColors.background,
          systemNavigationBarDividerColor: Colors.transparent,
          systemNavigationBarIconBrightness: Brightness.light,
          systemStatusBarContrastEnforced: false,
          systemNavigationBarContrastEnforced: false,
        ),
        child: MediaQuery(
          data: MediaQuery.of(context).copyWith(
            textScaler: TextScaler.linear(
              effectiveTextScale(
                MediaQuery.textScalerOf(context).scale(1),
                appState.fontSize,
              ),
            ),
          ),
          child: child ?? const SizedBox.shrink(),
        ),
      ),
    );
  }
}
