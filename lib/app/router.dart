// lib/app/router.dart
import 'package:go_router/go_router.dart';
import '../features/auth/onboarding_screen.dart';
import '../features/auth/loading_screen.dart';
import '../features/auth/auth_gate.dart';
import '../features/shell/main_shell.dart';
import '../features/home/home_tab.dart';
import '../features/practice/practice_tab.dart';
import '../features/chat/chat_tab.dart';
import '../features/chat/chat_screen.dart';
import '../features/chat/session_feedback_screen.dart';
import '../features/chat/roleplay_history_screen.dart';
import '../features/chat/roleplay_feedback_data.dart';
import '../features/chat/roleplay_models.dart';
import '../features/news/news_tab.dart';
import '../features/home/lesson_screen.dart';
import '../features/home/dictionary_screen.dart';
import '../features/practice/grammar_check_screen.dart';
import '../features/practice/plp_lesson_detail_screen.dart';
import '../features/practice/pronunciation_screen.dart';
import '../plp/learning_plan_screen.dart';
import '../plp/onboarding_screen.dart' as plp_onboarding;
import '../plp/plp_repository.dart';
import '../plp/first_run_gate.dart';

final GoRouter appRouter = GoRouter(
  initialLocation: '/auth',
  routes: [
    GoRoute(path: '/auth', builder: (_, __) => const AuthGate()),
    GoRoute(path: '/start', builder: (_, __) => const FirstRunGate()),
    GoRoute(path: '/onboarding', builder: (_, __) => const OnboardingScreen()),
    GoRoute(path: '/loading', builder: (_, __) => const LoadingScreen()),

    // Main app shell with bottom nav
    ShellRoute(
      builder: (context, state, child) => MainShell(child: child),
      routes: [
        GoRoute(path: '/home', builder: (_, __) => const HomeTab()),
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
            state.extra as RoleplayFeedbackData? ?? RoleplayFeedbackData.empty,
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
    GoRoute(
      path: '/lesson',
      builder: (context, state) =>
          LessonScreen(lessonName: (state.extra as String?) ?? 'Lesson'),
    ),

    // Grammar Check (full screen)
    GoRoute(
      path: '/grammar-check',
      builder: (_, __) => const GrammarCheckScreen(),
    ),
    GoRoute(path: '/dictionary', builder: (_, __) => const DictionaryScreen()),

    // PLP Lessons (full screen)
    GoRoute(
      path: '/plp/lessons',
      builder: (_, __) => const LearningPlanScreen(),
    ),
    GoRoute(
      path: '/plp/onboarding',
      builder: (_, __) =>
          plp_onboarding.PlpOnboardingScreen(repository: HttpPlpRepository()),
    ),
    GoRoute(
      path: '/plp/lesson',
      builder: (context, state) => PLPLessonDetailScreen(
        lessonData: (state.extra as Map<String, dynamic>?) ?? {},
      ),
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
