// lib/features/practice/plp_lessons_screen.dart
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:go_router/go_router.dart';
import '../../core/services/api_service.dart';

// ─────────────────────── Colors ──────────────────────────────
const _background = Color(0xFF090E1A);
const _surface = Color(0xFF111827);
const _surfaceCard = Color(0xFF1E2D45);
const _primary = Color(0xFF4F7FFF);
const _accent = Color(0xFF8B5CF6);
const _success = Color(0xFF22C55E);
const _textPrimary = Color(0xFFF1F5FF);
const _textSecondary = Color(0xFF8896B0);
const _border = Color(0xFF1E2D45);

class PLPLessonsScreen extends StatefulWidget {
  const PLPLessonsScreen({super.key});

  @override
  State<PLPLessonsScreen> createState() => _PLPLessonsScreenState();
}

class _PLPLessonsScreenState extends State<PLPLessonsScreen> {
  List<Map<String, dynamic>> _lessons = [];
  bool _isLoadingList = true;
  bool _isGenerating = false;

  @override
  void initState() {
    super.initState();
    _loadLessons();
  }

  Future<void> _loadLessons() async {
    setState(() => _isLoadingList = true);
    final results = await ApiService.getPLPLessons();
    if (!mounted) return;
    setState(() {
      _lessons = results
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      _isLoadingList = false;
    });
  }

  void _showGenerateDialog() {
    final topicCtrl = TextEditingController();
    String selectedLevel = 'B1';
    final levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: _surfaceCard,
          shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(20)),
          title: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                      colors: [_primary, _accent]),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.auto_awesome_rounded,
                    color: Colors.white, size: 18),
              ),
              const SizedBox(width: 10),
              Text(
                'Generate Lesson',
                style: GoogleFonts.inter(
                    color: _textPrimary,
                    fontWeight: FontWeight.w700,
                    fontSize: 17),
              ),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'AI will create a complete PLP lesson with vocabulary, grammar, exercises, and production tasks.',
                style: GoogleFonts.inter(
                    color: _textSecondary,
                    fontSize: 12,
                    height: 1.4),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: topicCtrl,
                style: GoogleFonts.inter(color: _textPrimary),
                decoration: InputDecoration(
                  hintText: 'Topic (e.g., Travel, Food, Business)',
                  hintStyle: GoogleFonts.inter(
                      color: _textSecondary, fontSize: 13),
                  filled: true,
                  fillColor: _surface,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: _border),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: _border),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide:
                        const BorderSide(color: _primary),
                  ),
                  prefixIcon: const Icon(Icons.topic_rounded,
                      color: _textSecondary, size: 20),
                ),
              ),
              const SizedBox(height: 14),
              DropdownButtonFormField<String>(
                value: selectedLevel,
                items: levels
                    .map((l) => DropdownMenuItem(
                          value: l,
                          child: Text(l,
                              style: GoogleFonts.inter(
                                  color: _textPrimary)),
                        ))
                    .toList(),
                onChanged: (v) =>
                    setDialogState(() => selectedLevel = v!),
                decoration: InputDecoration(
                  labelText: 'CEFR Level',
                  labelStyle: GoogleFonts.inter(
                      color: _textSecondary, fontSize: 13),
                  filled: true,
                  fillColor: _surface,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: _border),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: _border),
                  ),
                  prefixIcon: const Icon(Icons.school_rounded,
                      color: _textSecondary, size: 20),
                ),
                dropdownColor: _surfaceCard,
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: Text('Cancel',
                  style:
                      GoogleFonts.inter(color: _textSecondary)),
            ),
            GestureDetector(
              onTap: () {
                final topic = topicCtrl.text.trim();
                if (topic.isEmpty) return;
                Navigator.pop(ctx);
                _generateLesson(topic, selectedLevel);
              },
              child: Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 20, vertical: 10),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                      colors: [_primary, _accent]),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  'Generate ✨',
                  style: GoogleFonts.inter(
                      color: Colors.white,
                      fontWeight: FontWeight.w700),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _generateLesson(String topic, String level) async {
    setState(() => _isGenerating = true);

    final result =
        await ApiService.generatePLPLesson(topic, level);

    if (!mounted) return;

    setState(() => _isGenerating = false);

    if (result.containsKey('error')) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(result['error'],
              style: GoogleFonts.inter()),
          backgroundColor: const Color(0xFFEF4444),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10)),
        ),
      );
    } else {
      // Navigate to the detail screen with the lesson data
      if (mounted) {
        context.push('/plp/lesson', extra: result);
      }
      // Refresh the list
      _loadLessons();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _background,
      appBar: _buildAppBar(),
      body: Stack(
        children: [
          RefreshIndicator(
            color: _primary,
            backgroundColor: _surfaceCard,
            onRefresh: _loadLessons,
            child: _isLoadingList
                ? _buildLoadingState()
                : _lessons.isEmpty
                    ? _buildEmptyState()
                    : _buildLessonsList(),
          ),
          if (_isGenerating) _buildGeneratingOverlay(),
        ],
      ),
      floatingActionButton: _buildFAB(),
    );
  }

  AppBar _buildAppBar() {
    return AppBar(
      backgroundColor: _surface,
      elevation: 0,
      leading: IconButton(
        icon: const Icon(Icons.arrow_back_ios_new_rounded,
            color: _textPrimary, size: 20),
        onPressed: () {
          if (context.canPop()) {
            context.pop();
          } else {
            context.go('/practice');
          }
        },
      ),
      title: ShaderMask(
        shaderCallback: (b) => const LinearGradient(
          colors: [_primary, _accent],
        ).createShader(b),
        child: Text(
          'AI Lessons',
          style: GoogleFonts.inter(
            fontWeight: FontWeight.w700,
            fontSize: 18,
            color: Colors.white,
          ),
        ),
      ),
      bottom: PreferredSize(
        preferredSize: const Size.fromHeight(1),
        child: Container(height: 1, color: _border),
      ),
    );
  }

  Widget _buildLoadingState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const CircularProgressIndicator(color: _primary),
          const SizedBox(height: 16),
          Text(
            'Loading lessons…',
            style: GoogleFonts.inter(
                color: _textSecondary, fontSize: 14),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return ListView(
      children: [
        SizedBox(height: MediaQuery.of(context).size.height * 0.2),
        Center(
          child: Column(
            children: [
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      _primary.withOpacity(0.15),
                      _accent.withOpacity(0.15)
                    ],
                  ),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.school_rounded,
                    color: _primary, size: 36),
              )
                  .animate(onPlay: (c) => c.repeat(reverse: true))
                  .scale(
                    begin: const Offset(1, 1),
                    end: const Offset(1.1, 1.1),
                    duration: 1200.ms,
                  ),
              const SizedBox(height: 20),
              Text(
                'No lessons yet',
                style: GoogleFonts.inter(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: _textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Tap the ✨ button to generate\nyour first AI-powered lesson!',
                textAlign: TextAlign.center,
                style: GoogleFonts.inter(
                  fontSize: 14,
                  color: _textSecondary,
                  height: 1.5,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildLessonsList() {
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 100),
      itemCount: _lessons.length,
      itemBuilder: (context, index) {
        final lesson = _lessons[index];
        return _LessonCard(
          lesson: lesson,
          onTap: () =>
              context.push('/plp/lesson', extra: lesson),
        )
            .animate(delay: Duration(milliseconds: 60 * index))
            .fadeIn(duration: 350.ms)
            .slideY(begin: 0.08, end: 0);
      },
    );
  }

  Widget _buildGeneratingOverlay() {
    return Container(
      color: Colors.black.withOpacity(0.6),
      child: Center(
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 40),
          padding: const EdgeInsets.all(32),
          decoration: BoxDecoration(
            color: _surfaceCard,
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: _primary.withOpacity(0.3)),
            boxShadow: [
              BoxShadow(
                color: _primary.withOpacity(0.15),
                blurRadius: 30,
                spreadRadius: 5,
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox(
                width: 48,
                height: 48,
                child: CircularProgressIndicator(
                  color: _primary,
                  strokeWidth: 3,
                ),
              )
                  .animate(onPlay: (c) => c.repeat())
                  .shimmer(
                      duration: 1500.ms,
                      color: _accent.withOpacity(0.3)),
              const SizedBox(height: 20),
              Text(
                'Generating Lesson…',
                style: GoogleFonts.inter(
                  fontSize: 17,
                  fontWeight: FontWeight.w700,
                  color: _textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'AI is crafting vocabulary, grammar,\nexercises, and tasks for you.',
                textAlign: TextAlign.center,
                style: GoogleFonts.inter(
                  fontSize: 13,
                  color: _textSecondary,
                  height: 1.4,
                ),
              ),
            ],
          ),
        ).animate().fadeIn(duration: 300.ms).scale(
              begin: const Offset(0.9, 0.9),
              end: const Offset(1, 1),
            ),
      ),
    );
  }

  Widget _buildFAB() {
    return GestureDetector(
      onTap: _showGenerateDialog,
      child: Container(
        width: 60,
        height: 60,
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [_primary, _accent],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(18),
          boxShadow: [
            BoxShadow(
              color: _primary.withOpacity(0.4),
              blurRadius: 16,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: const Icon(Icons.auto_awesome_rounded,
            color: Colors.white, size: 28),
      ),
    );
  }
}

// ── Lesson Card ──────────────────────────────────────────────
class _LessonCard extends StatelessWidget {
  final Map<String, dynamic> lesson;
  final VoidCallback onTap;

  const _LessonCard({required this.lesson, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final title =
        lesson['title']?.toString() ?? 'Untitled Lesson';
    final topic = lesson['topic']?.toString() ?? '';
    final level = lesson['level']?.toString() ?? 'A1';
    final vocabCount = (lesson['presentation']
                ?['vocabulary'] as List?)
            ?.length ??
        0;
    final exerciseCount =
        (lesson['practice']?['exercises'] as List?)?.length ??
            0;

    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: _surfaceCard,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: _border),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.2),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Column(
          children: [
            // Gradient top accent
            Container(
              height: 3,
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  colors: [_primary, _accent],
                ),
                borderRadius: BorderRadius.vertical(
                    top: Radius.circular(18)),
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Title
                  Text(
                    title,
                    style: GoogleFonts.inter(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: _textPrimary,
                    ),
                  ),
                  const SizedBox(height: 8),
                  // Badges row
                  Row(
                    children: [
                      if (topic.isNotEmpty)
                        _Badge(
                            text: topic,
                            color: _accent,
                            icon: Icons.topic_rounded),
                      if (topic.isNotEmpty)
                        const SizedBox(width: 8),
                      _Badge(
                          text: level,
                          color: _primary,
                          icon: Icons.school_rounded),
                      const SizedBox(width: 8),
                      if (vocabCount > 0)
                        _Badge(
                            text: '$vocabCount words',
                            color: _success,
                            icon: Icons.abc_rounded),
                      const Spacer(),
                      const Icon(Icons.arrow_forward_ios_rounded,
                          color: _textSecondary, size: 16),
                    ],
                  ),
                  if (exerciseCount > 0) ...[
                    const SizedBox(height: 8),
                    Text(
                      '$exerciseCount exercises available',
                      style: GoogleFonts.inter(
                        fontSize: 12,
                        color: _textSecondary,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  final String text;
  final Color color;
  final IconData icon;

  const _Badge(
      {required this.text,
      required this.color,
      required this.icon});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
          horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 12),
          const SizedBox(width: 4),
          Text(
            text,
            style: GoogleFonts.inter(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}
