// lib/app/router.dart
import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'providers.dart';
import '../features/auth/onboarding_screen.dart';
import '../features/auth/loading_screen.dart';
import '../features/auth/auth_gate.dart';
import '../features/shell/main_shell.dart';
import '../features/home/home_tab.dart';
import '../features/practice/practice_tab.dart';
import '../features/chat/chat_tab.dart';
import '../features/chat/chat_screen.dart';
import '../features/chat/roleplay_session_summary_screen.dart';
import '../features/chat/roleplay_history_screen.dart';
import '../features/chat/roleplay_feedback_data.dart';
import '../features/chat/roleplay_models.dart';
import '../features/news/news_tab.dart';
import '../features/practice/dictionary_screen.dart';
import '../features/practice/grammar_check_screen.dart';
import '../features/practice/pronunciation_screen.dart';
import '../features/learning_plan/presentation/first_run_gate.dart';
import '../features/learning_plan/presentation/learning_plan_screen.dart';
import '../features/learning_plan/presentation/onboarding_screen.dart'
    as plp_onboarding;

final appRouterProvider = Provider<GoRouter>((ref) {
  final authStore = ref.read(authSessionStoreProvider);
  final plpRepository = ref.watch(plpRepositoryProvider);
  final router = GoRouter(
    initialLocation: '/auth',
    refreshListenable: authStore,
    redirect: (context, state) {
      final hasSession = authStore.hasSession;
      final onAuth = state.matchedLocation == '/auth';
      if (!hasSession && !onAuth) return '/auth';
      return null;
    },
    routes: [
      GoRoute(path: '/auth', builder: (_, __) => const AuthGate()),
      GoRoute(
        path: '/start',
        builder: (_, __) => FirstRunGate(repository: plpRepository),
      ),
      GoRoute(
        path: '/onboarding',
        builder: (_, __) => const OnboardingScreen(),
      ),
      GoRoute(path: '/loading', builder: (_, __) => const LoadingScreen()),

      // Main app shell with bottom nav
      ShellRoute(
        builder: (context, state, child) =>
            MainShell(location: state.uri.path, child: child),
        routes: [
          GoRoute(
            path: '/home',
            builder: (_, __) => HomeTab(repository: plpRepository),
          ),
          GoRoute(path: '/practice', builder: (_, __) => const PracticeTab()),
          GoRoute(path: '/chat', builder: (_, __) => const ChatTab()),
          GoRoute(path: '/news', builder: (_, __) => const NewsTab()),
        ],
      ),

      // Chat detail screens (outside shell = full screen)
      GoRoute(
        path: '/chat/roleplay',
        builder: (context, state) {
          final args = state.extra as RoleplayLaunchArgs?;
          if (args == null) return const ChatTab();
          return ChatScreen(scenario: args.scenario);
        },
      ),
      GoRoute(
        path: '/chat/feedback',
        builder: (_, state) => SessionFeedbackScreen(
          feedback:
              state.extra as RoleplayFeedbackData? ??
              RoleplayFeedbackData.empty,
        ),
      ),
      GoRoute(
        path: '/chat/history',
        builder: (_, state) {
          final args = state.extra as RoleplayHistoryArgs?;
          if (args == null) return const ChatTab();
          return RoleplayHistoryScreen(args: args);
        },
      ),
      // Grammar Check (full screen)
      GoRoute(
        path: '/grammar-check',
        builder: (_, __) => const GrammarCheckScreen(),
      ),
      GoRoute(
        path: '/dictionary',
        builder: (_, __) => const DictionaryScreen(),
      ),

      // PLP Lessons (full screen)
      GoRoute(
        path: '/plp/lessons',
        builder: (_, __) => LearningPlanScreen(repository: plpRepository),
      ),
      GoRoute(
        path: '/plp/onboarding',
        builder: (_, __) =>
            plp_onboarding.PlpOnboardingScreen(repository: plpRepository),
      ),
      // Pronunciation Practice (full screen)
      GoRoute(
        path: '/pronunciation',
        builder: (_, state) {
          final args = state.extra as PronunciationLaunchArgs?;
          return PronunciationScreen(
            initialTarget: args?.target,
            onPassed: args?.onPassed,
          );
        },
      ),
    ],
  );
  ref.onDispose(router.dispose);
  return router;
});
