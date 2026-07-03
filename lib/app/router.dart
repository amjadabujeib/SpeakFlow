// lib/app/router.dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../features/auth/sign_in_screen.dart';
import '../features/auth/sign_up_screen.dart';
import '../features/auth/onboarding_screen.dart';
import '../features/auth/loading_screen.dart';
import '../features/shell/main_shell.dart';
import '../features/home/home_tab.dart';
import '../features/practice/practice_tab.dart';
import '../features/chat/chat_tab.dart';
import '../features/chat/chat_screen.dart';
import '../features/chat/session_feedback_screen.dart';
import '../features/news/news_tab.dart';
import '../features/home/lesson_screen.dart';
import '../features/practice/grammar_check_screen.dart';
import '../features/practice/plp_lessons_screen.dart';
import '../features/practice/plp_lesson_detail_screen.dart';

final GoRouter appRouter = GoRouter(
  initialLocation: '/signin',
  routes: [
    // Auth flow
    GoRoute(
      path: '/signin',
      builder: (_, __) => const SignInScreen(),
    ),
    GoRoute(
      path: '/signup',
      builder: (_, __) => const SignUpScreen(),
    ),
    GoRoute(
      path: '/onboarding',
      builder: (_, __) => const OnboardingScreen(),
    ),
    GoRoute(
      path: '/loading',
      builder: (_, __) => const LoadingScreen(),
    ),

    // Main app shell with bottom nav
    ShellRoute(
      builder: (context, state, child) => MainShell(child: child),
      routes: [
        GoRoute(
          path: '/home',
          builder: (_, __) => const HomeTab(),
        ),
        GoRoute(
          path: '/practice',
          builder: (_, __) => const PracticeTab(),
        ),
        GoRoute(
          path: '/chat',
          builder: (_, __) => const ChatTab(),
        ),
        GoRoute(
          path: '/news',
          builder: (_, __) => const NewsTab(),
        ),
      ],
    ),

    // Chat detail screens (outside shell = full screen)
    GoRoute(
      path: '/chat/roleplay',
      builder: (context, state) => ChatScreen(
        roleplaysTitle: (state.extra as String?) ?? 'Roleplay',
      ),
    ),
    GoRoute(
      path: '/chat/feedback',
      builder: (_, __) => const SessionFeedbackScreen(),
    ),
    GoRoute(
      path: '/lesson',
      builder: (context, state) => LessonScreen(
        lessonName: (state.extra as String?) ?? 'Lesson',
      ),
    ),

    // Grammar Check (full screen)
    GoRoute(
      path: '/grammar-check',
      builder: (_, __) => const GrammarCheckScreen(),
    ),

    // PLP Lessons (full screen)
    GoRoute(
      path: '/plp/lessons',
      builder: (_, __) => const PLPLessonsScreen(),
    ),
    GoRoute(
      path: '/plp/lesson',
      builder: (context, state) => PLPLessonDetailScreen(
        lessonData: (state.extra as Map<String, dynamic>?) ?? {},
      ),
    ),
  ],
);
