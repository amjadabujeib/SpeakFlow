import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:just_talk/core/theme/local_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';

// Color constants
const _background = Color(0xFF090E1A);
const _primary = Color(0xFF4F7FFF);
const _accent = Color(0xFF8B5CF6);
const _textPrimary = Color(0xFFF1F5FF);
const _textSecondary = Color(0xFF8896B0);

class LoadingScreen extends StatefulWidget {
  const LoadingScreen({super.key});

  @override
  State<LoadingScreen> createState() => _LoadingScreenState();
}

class _LoadingScreenState extends State<LoadingScreen>
    with TickerProviderStateMixin {
  final List<String> _messages = [
    'Analyzing your level...',
    'Crafting your lessons...',
    'Building vocabulary lists...',
    'Almost ready!',
  ];

  int _currentMessageIndex = 0;
  late AnimationController _pulseController;
  late AnimationController _glowController;

  @override
  void initState() {
    super.initState();

    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);

    _glowController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2000),
    )..repeat(reverse: true);

    // Cycle messages every 800ms
    _startMessageCycle();

    // Navigate after 3.5 seconds
    Future.delayed(const Duration(milliseconds: 3500), () {
      if (mounted) context.go('/home');
    });
  }

  void _startMessageCycle() {
    Future.delayed(const Duration(milliseconds: 800), () {
      if (!mounted) return;
      setState(() {
        _currentMessageIndex =
            (_currentMessageIndex + 1) % _messages.length;
      });
      if (_currentMessageIndex < _messages.length - 1) {
        _startMessageCycle();
      }
    });
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _glowController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _background,
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF090E1A), Color(0xFF0D1526)],
          ),
        ),
        child: SafeArea(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Spacer(),
              // Glowing pulsing circle
              AnimatedBuilder(
                animation: Listenable.merge([_pulseController, _glowController]),
                builder: (context, child) {
                  final pulseScale = 1.0 + (_pulseController.value * 0.12);
                  final glowOpacity = 0.3 + (_glowController.value * 0.3);
                  return Stack(
                    alignment: Alignment.center,
                    children: [
                      // Outer glow ring 3
                      Container(
                        width: 160 * pulseScale,
                        height: 160 * pulseScale,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: RadialGradient(
                            colors: [
                              _primary.withOpacity(glowOpacity * 0.25),
                              _accent.withOpacity(0),
                            ],
                          ),
                        ),
                      ),
                      // Outer glow ring 2
                      Container(
                        width: 130 * pulseScale,
                        height: 130 * pulseScale,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: RadialGradient(
                            colors: [
                              _primary.withOpacity(glowOpacity * 0.45),
                              _accent.withOpacity(0),
                            ],
                          ),
                        ),
                      ),
                      // Main circle
                      Container(
                        width: 100,
                        height: 100,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: const LinearGradient(
                            colors: [_primary, _accent],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: _primary.withOpacity(glowOpacity + 0.1),
                              blurRadius: 30 + (glowOpacity * 10),
                              spreadRadius: 4,
                            ),
                            BoxShadow(
                              color: _accent.withOpacity(glowOpacity * 0.5),
                              blurRadius: 20,
                              spreadRadius: 2,
                            ),
                          ],
                        ),
                        child: const Icon(
                          Icons.auto_awesome_rounded,
                          color: Colors.white,
                          size: 44,
                        ),
                      ),
                    ],
                  );
                },
              )
                  .animate()
                  .fadeIn(duration: 600.ms)
                  .scale(begin: const Offset(0.7, 0.7), duration: 700.ms, curve: Curves.easeOutBack),
              const SizedBox(height: 52),
              // App name
              Text(
                'JustTalk',
                style: GoogleFonts.inter(
                  fontSize: 26,
                  fontWeight: FontWeight.w800,
                  foreground: Paint()
                    ..shader = const LinearGradient(
                      colors: [_primary, _accent],
                    ).createShader(const Rect.fromLTWH(0, 0, 160, 36)),
                ),
              )
                  .animate()
                  .fadeIn(delay: 300.ms, duration: 500.ms),
              const SizedBox(height: 14),
              // Generating plan label
              Text(
                'Generating your personalized plan',
                style: GoogleFonts.inter(
                  fontSize: 14,
                  color: _textSecondary,
                  fontWeight: FontWeight.w400,
                ),
              )
                  .animate()
                  .fadeIn(delay: 400.ms, duration: 500.ms),
              const SizedBox(height: 36),
              // Cycling animated message
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 350),
                transitionBuilder: (child, animation) {
                  return FadeTransition(
                    opacity: animation,
                    child: SlideTransition(
                      position: Tween<Offset>(
                        begin: const Offset(0, 0.25),
                        end: Offset.zero,
                      ).animate(animation),
                      child: child,
                    ),
                  );
                },
                child: Text(
                  _messages[_currentMessageIndex],
                  key: ValueKey(_currentMessageIndex),
                  style: GoogleFonts.inter(
                    fontSize: 17,
                    color: _textPrimary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              )
                  .animate()
                  .fadeIn(delay: 500.ms, duration: 500.ms),
              const Spacer(),
              // Three animated dots
              _AnimatedDots()
                  .animate()
                  .fadeIn(delay: 600.ms, duration: 500.ms),
              const SizedBox(height: 60),
            ],
          ),
        ),
      ),
    );
  }
}

class _AnimatedDots extends StatefulWidget {
  @override
  State<_AnimatedDots> createState() => _AnimatedDotsState();
}

class _AnimatedDotsState extends State<_AnimatedDots>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: List.generate(3, (index) {
            final delay = index / 3;
            final phase = (_controller.value - delay).clamp(0.0, 1.0);
            final opacity = 0.3 +
                0.7 *
                    (phase < 0.5
                        ? phase * 2
                        : (1 - phase) * 2);
            final translateY = -6.0 *
                (phase < 0.5 ? phase * 2 : (1 - phase) * 2);
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 5),
              child: Transform.translate(
                offset: Offset(0, translateY),
                child: Opacity(
                  opacity: opacity,
                  child: Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: const LinearGradient(
                        colors: [_primary, _accent],
                      ),
                    ),
                  ),
                ),
              ),
            );
          }),
        );
      },
    );
  }
}
