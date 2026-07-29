// lib/main.dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'core/theme/app_theme.dart';
import 'core/auth/auth_session_store.dart';
import 'app/router.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await AuthSessionStore.instance.restore();
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: Color(0xFF0D1526),
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );
  runApp(const SpeakFlowApp());
}

class SpeakFlowApp extends StatefulWidget {
  const SpeakFlowApp({super.key});

  @override
  State<SpeakFlowApp> createState() => _SpeakFlowAppState();
}

class _SpeakFlowAppState extends State<SpeakFlowApp> {
  bool _isDark = true;

  void _toggleTheme() {
    setState(() => _isDark = !_isDark);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'SpeakFlow',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: _isDark ? ThemeMode.dark : ThemeMode.light,
      routerConfig: appRouter,
    );
  }
}
