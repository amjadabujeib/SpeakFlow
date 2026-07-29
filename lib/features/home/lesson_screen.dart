import 'package:flutter/material.dart';
import 'package:speakflow/core/theme/local_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:go_router/go_router.dart';

class LessonScreen extends StatefulWidget {
  final String lessonName;
  const LessonScreen({super.key, required this.lessonName});

  @override
  State<LessonScreen> createState() => _LessonScreenState();
}

class _LessonScreenState extends State<LessonScreen> {
  bool _isFlipped = false;

  @override
  Widget build(BuildContext context) {
    const background = Color(0xFF090E1A);
    const surface = Color(0xFF1E2D45);
    const primary = Color(0xFF4F7FFF);
    const textPrimary = Color(0xFFF1F5FF);
    const textSecondary = Color(0xFF8896B0);

    return Scaffold(
      backgroundColor: background,
      appBar: AppBar(
        backgroundColor: background,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.close_rounded, color: textPrimary),
          onPressed: () => context.pop(),
        ),
        title: LinearProgressIndicator(
          value: 0.3,
          backgroundColor: surface,
          valueColor: const AlwaysStoppedAnimation<Color>(primary),
          borderRadius: BorderRadius.circular(10),
          minHeight: 8,
        ),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Vocabulary Practice',
                style: GoogleFonts.inter(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: primary,
                ),
                textAlign: TextAlign.center,
              ).animate().fadeIn(duration: 400.ms),
              const SizedBox(height: 8),
              Text(
                widget.lessonName,
                style: GoogleFonts.inter(
                  fontSize: 24,
                  fontWeight: FontWeight.w800,
                  color: textPrimary,
                ),
                textAlign: TextAlign.center,
              ).animate().fadeIn(delay: 100.ms, duration: 400.ms),
              const Spacer(),
              
              // Flashcard
              GestureDetector(
                onTap: () {
                  setState(() => _isFlipped = !_isFlipped);
                },
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 300),
                  height: 300,
                  decoration: BoxDecoration(
                    color: _isFlipped ? primary.withOpacity(0.15) : surface,
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(
                      color: _isFlipped ? primary : surface,
                      width: 2,
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.2),
                        blurRadius: 15,
                        offset: const Offset(0, 8),
                      ),
                    ],
                  ),
                  alignment: Alignment.center,
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        _isFlipped ? 'Welcome' : 'Bienvenido',
                        style: GoogleFonts.outfit(
                          fontSize: 42,
                          fontWeight: FontWeight.w700,
                          color: textPrimary,
                        ),
                      ),
                      const SizedBox(height: 16),
                      Text(
                        _isFlipped ? '(Tap to hide translation)' : '(Tap to reveal translation)',
                        style: GoogleFonts.inter(
                          fontSize: 14,
                          fontWeight: FontWeight.w500,
                          color: textSecondary,
                        ),
                      ),
                      if (!_isFlipped) ...[
                        const SizedBox(height: 24),
                        IconButton(
                          icon: const Icon(Icons.volume_up_rounded, color: primary, size: 32),
                          onPressed: () {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('Playing pronunciation...')),
                            );
                          },
                        ),
                      ]
                    ],
                  ),
                ),
              ).animate().scaleXY(begin: 0.9, end: 1.0, duration: 400.ms, curve: Curves.easeOutBack),
              
              const Spacer(),
              ElevatedButton(
                onPressed: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Moving to next exercise...')),
                  );
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: primary,
                  padding: const EdgeInsets.symmetric(vertical: 18),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                child: Text(
                  'Continue',
                  style: GoogleFonts.inter(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
              ).animate().slideY(begin: 0.5, end: 0, duration: 400.ms, delay: 200.ms),
            ],
          ),
        ),
      ),
    );
  }
}
