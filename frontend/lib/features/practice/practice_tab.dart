import 'package:flutter/material.dart';
import 'package:speakflow/core/theme/local_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:go_router/go_router.dart';
import '../../core/data/phoneme_progress_store.dart';
import '../../core/data/practice_word_store.dart';
import 'pronunciation_screen.dart';

part 'practice_word_queue.dart';
part 'practice_word_cards.dart';
part 'practice_add_word.dart';
part 'practice_phoneme_map.dart';
part 'practice_phoneme_grid.dart';

// ─────────────────────────── Colors ───────────────────────────
const _background = Color(0xFF090E1A);
const _surfaceCard = Color(0xFF1E2D45);
const _primary = Color(0xFF4F7FFF);
const _accent = Color(0xFF8B5CF6);
const _success = Color(0xFF22C55E);
const _warning = Color(0xFFF59E0B);
const _error = Color(0xFFEF4444);
const _textPrimary = Color(0xFFF1F5FF);
const _textSecondary = Color(0xFF8896B0);

// ─────────────────────────── Data ─────────────────────────────

enum _WordFilter { all, needsChecking, roleplay, addedByMe, mastered }

// ──────────────────── Score Color Helper ──────────────────────
Color _scoreColor(int score) {
  if (score < 50) return _error;
  if (score <= 80) return _warning;
  return _success;
}

// ──────────────────── Main Widget ─────────────────────────────
class PracticeTab extends StatefulWidget {
  const PracticeTab({super.key});

  @override
  State<PracticeTab> createState() => _PracticeTabState();
}

class _PracticeTabState extends State<PracticeTab> {
  int _selectedSegment = 0;
  _WordFilter _wordFilter = _WordFilter.all;
  final PracticeWordStore _wordStore = PracticeWordStore.instance;
  final PhonemeProgressStore _phonemeStore = PhonemeProgressStore.instance;
  final TextEditingController _addWordCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _wordStore.addListener(_onWordsChanged);
    _phonemeStore.addListener(_onWordsChanged);
    _wordStore.load();
    _phonemeStore.load();
  }

  @override
  void dispose() {
    _wordStore.removeListener(_onWordsChanged);
    _phonemeStore.removeListener(_onWordsChanged);
    _addWordCtrl.dispose();
    super.dispose();
  }

  void _onWordsChanged() {
    if (mounted) setState(() {});
  }

  List<PracticeWord> get _visibleWords {
    return _wordStore.words
        .where((word) {
          return switch (_wordFilter) {
            _WordFilter.all => true,
            _WordFilter.needsChecking =>
              !word.isMastered && !word.addedManually && word.score < 80,
            _WordFilter.roleplay => !word.isMastered && !word.addedManually,
            _WordFilter.addedByMe => !word.isMastered && word.addedManually,
            _WordFilter.mastered => word.isMastered,
          };
        })
        .toList(growable: false);
  }

  Future<void> _addWord() async {
    final text = _addWordCtrl.text.trim();
    if (text.isEmpty) return;
    await _wordStore.addManualWord(text);
    _addWordCtrl.clear();
  }

  void _practiceWord(PracticeWord word) {
    context.push(
      '/pronunciation',
      extra: PronunciationLaunchArgs(
        target: word.word,
        onPassed: () => _wordStore.markMastered(word),
      ),
    );
  }

  Future<void> _deleteWord(PracticeWord word) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Delete practice word?'),
        content: Text(
          'Remove “${word.word}” from your list? You can add it again later.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Cancel'),
          ),
          FilledButton.icon(
            style: FilledButton.styleFrom(backgroundColor: _error),
            onPressed: () => Navigator.pop(dialogContext, true),
            icon: const Icon(Icons.delete_outline_rounded),
            label: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed == true) await _wordStore.removeWord(word);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _background,
      body: SafeArea(
        child: Column(
          children: [
            _buildSegmentedControl(),
            Expanded(
              child: AnimatedSwitcher(
                duration: const Duration(milliseconds: 300),
                transitionBuilder: (child, animation) =>
                    FadeTransition(opacity: animation, child: child),
                child: _selectedSegment == 0
                    ? _WordPracticeSection(
                        key: const ValueKey('word'),
                        words: _visibleWords,
                        filter: _wordFilter,
                        onFilterChanged: (filter) =>
                            setState(() => _wordFilter = filter),
                        onPractice: _practiceWord,
                        onDelete: _deleteWord,
                        addWordCtrl: _addWordCtrl,
                        onAdd: _addWord,
                      )
                    : _PhonemeMapSection(
                        key: const ValueKey('phoneme'),
                        entries: _phonemeStore.entries,
                        observationCount: _phonemeStore.observationCount,
                        onStartPractice: () => context.push('/pronunciation'),
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSegmentedControl() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
      child: Container(
        height: 48,
        padding: const EdgeInsets.all(4),
        decoration: BoxDecoration(
          color: const Color(0xFF111827),
          borderRadius: BorderRadius.circular(28),
          border: Border.all(color: const Color(0xFF1E2D45), width: 1),
        ),
        child: Row(
          children: [
            _buildSegmentPill(
              0,
              'Word Practice',
              Icons.record_voice_over_rounded,
            ),
            _buildSegmentPill(1, 'Phoneme Map', Icons.grid_view_rounded),
          ],
        ),
      ).animate().fadeIn(duration: 500.ms, delay: 100.ms),
    );
  }

  Widget _buildSegmentPill(int index, String label, IconData icon) {
    final isSelected = _selectedSegment == index;
    return Expanded(
      child: GestureDetector(
        onTap: () {
          setState(() => _selectedSegment = index);
        },
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeInOut,
          decoration: BoxDecoration(
            gradient: isSelected
                ? const LinearGradient(
                    colors: [_primary, _accent],
                    begin: Alignment.centerLeft,
                    end: Alignment.centerRight,
                  )
                : null,
            borderRadius: BorderRadius.circular(24),
            boxShadow: isSelected
                ? [
                    BoxShadow(
                      color: _primary.withAlpha(80),
                      blurRadius: 12,
                      offset: const Offset(0, 4),
                    ),
                  ]
                : null,
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                icon,
                size: 16,
                color: isSelected ? Colors.white : _textSecondary,
              ),
              const SizedBox(width: 6),
              Text(
                label,
                style: GoogleFonts.outfit(
                  fontSize: 13,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                  color: isSelected ? Colors.white : _textSecondary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ─────────────── Word Practice Section ────────────────────────
