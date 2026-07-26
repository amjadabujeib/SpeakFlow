import 'package:flutter/material.dart';
import 'package:just_talk/core/theme/local_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:go_router/go_router.dart';
import '../../core/data/phoneme_progress_store.dart';
import '../../core/data/practice_word_store.dart';
import 'pronunciation_screen.dart';

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

enum _WordFilter { all, needsChecking, roleplay, addedByMe }

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
            _WordFilter.needsChecking => !word.addedManually && word.score < 80,
            _WordFilter.roleplay => !word.addedManually,
            _WordFilter.addedByMe => word.addedManually,
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
        onPassed: () => _wordStore.removeWord(word),
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
class _WordPracticeSection extends StatelessWidget {
  final List<PracticeWord> words;
  final _WordFilter filter;
  final ValueChanged<_WordFilter> onFilterChanged;
  final ValueChanged<PracticeWord> onPractice;
  final ValueChanged<PracticeWord> onDelete;
  final TextEditingController addWordCtrl;
  final VoidCallback onAdd;

  const _WordPracticeSection({
    super.key,
    required this.words,
    required this.filter,
    required this.onFilterChanged,
    required this.onPractice,
    required this.onDelete,
    required this.addWordCtrl,
    required this.onAdd,
  });

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
      children: [
        _WordFilters(
          selected: filter,
          onSelected: onFilterChanged,
        ).animate().fadeIn(duration: 300.ms),
        const SizedBox(height: 14),
        if (words.isEmpty)
          _EmptyWordQueue(filter: filter)
        else
          ...List.generate(words.length, (i) {
            return _WordCard(
                  entry: words[i],
                  onPractice: () => onPractice(words[i]),
                  onDelete: () => onDelete(words[i]),
                )
                .animate(delay: Duration(milliseconds: 60 * i))
                .fadeIn(duration: 350.ms)
                .slideY(begin: 0.15, end: 0);
          }),
        const SizedBox(height: 20),
        _AddWordSection(
          ctrl: addWordCtrl,
          onAdd: onAdd,
        ).animate(delay: 300.ms).fadeIn(duration: 400.ms),
      ],
    );
  }
}

class _WordFilters extends StatelessWidget {
  final _WordFilter selected;
  final ValueChanged<_WordFilter> onSelected;

  const _WordFilters({required this.selected, required this.onSelected});

  static const _labels = {
    _WordFilter.all: 'All',
    _WordFilter.needsChecking: 'Needs checking',
    _WordFilter.roleplay: 'Roleplay',
    _WordFilter.addedByMe: 'Added by me',
  };

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: _WordFilter.values
            .map((filter) {
              final active = filter == selected;
              return Padding(
                padding: const EdgeInsets.only(right: 8),
                child: ChoiceChip(
                  selected: active,
                  showCheckmark: false,
                  label: Text(_labels[filter]!),
                  onSelected: (_) => onSelected(filter),
                  selectedColor: _primary.withValues(alpha: 0.2),
                  backgroundColor: const Color(0xFF111827),
                  side: BorderSide(
                    color: active ? _primary : const Color(0xFF2A3E5A),
                  ),
                  labelStyle: GoogleFonts.outfit(
                    color: active ? _textPrimary : _textSecondary,
                    fontSize: 12,
                    fontWeight: active ? FontWeight.w600 : FontWeight.w400,
                  ),
                ),
              );
            })
            .toList(growable: false),
      ),
    );
  }
}

class _EmptyWordQueue extends StatelessWidget {
  final _WordFilter filter;

  const _EmptyWordQueue({required this.filter});

  @override
  Widget build(BuildContext context) {
    final filtered = filter != _WordFilter.all;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 28),
      decoration: BoxDecoration(
        color: const Color(0xFF111827),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF1E2D45)),
      ),
      child: Column(
        children: [
          Icon(
            filtered ? Icons.filter_alt_off_rounded : Icons.task_alt_rounded,
            color: _textSecondary,
            size: 28,
          ),
          const SizedBox(height: 10),
          Text(
            filtered ? 'No words match this filter' : 'Your queue is clear',
            textAlign: TextAlign.center,
            style: GoogleFonts.outfit(
              color: _textPrimary,
              fontSize: 15,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 5),
          Text(
            filtered
                ? 'Choose another filter to see the rest of your words.'
                : 'Words the roleplay recognizer was unsure about will appear here for verification.',
            textAlign: TextAlign.center,
            style: GoogleFonts.outfit(
              color: _textSecondary,
              fontSize: 12,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────── Word Card ────────────────────────────────────
class _WordCard extends StatelessWidget {
  final PracticeWord entry;
  final VoidCallback onPractice;
  final VoidCallback onDelete;

  const _WordCard({
    required this.entry,
    required this.onPractice,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final borderColor = entry.addedManually ? _primary : _warning;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(14),
        border: Border(left: BorderSide(color: borderColor, width: 3)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withAlpha(50),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    entry.word,
                    style: GoogleFonts.outfit(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      color: _textPrimary,
                    ),
                  ),
                  if (entry.ipa.isNotEmpty) ...[
                    const SizedBox(height: 3),
                    Text(
                      entry.ipa,
                      style: GoogleFonts.outfit(
                        fontSize: 13,
                        fontWeight: FontWeight.w400,
                        color: _accent,
                      ),
                    ),
                  ],
                  if (entry.addedManually) ...[
                    const SizedBox(height: 3),
                    Text(
                      'Added by you',
                      style: GoogleFonts.outfit(
                        fontSize: 12,
                        fontWeight: FontWeight.w400,
                        color: _textSecondary,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                  ],
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      _ScorePill(
                        score: entry.score,
                        unscored: entry.addedManually,
                        recognitionCheck: !entry.addedManually,
                      ),
                      const SizedBox(width: 10),
                      if (entry.source.isNotEmpty)
                        Expanded(
                          child: Text(
                            entry.occurrences > 1
                                ? '${entry.source} · seen ${entry.occurrences}×'
                                : entry.source,
                            overflow: TextOverflow.ellipsis,
                            style: GoogleFonts.outfit(
                              fontSize: 11,
                              color: _textSecondary,
                            ),
                          ),
                        ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            Column(
              children: [
                _ActionBtn(
                  key: ValueKey('practice-${entry.word}'),
                  icon: Icons.mic_rounded,
                  color: _primary,
                  onTap: onPractice,
                  tooltip: 'Practice',
                ),
                const SizedBox(height: 8),
                _ActionBtn(
                  key: ValueKey('delete-${entry.word}'),
                  icon: Icons.delete_outline_rounded,
                  color: _error,
                  onTap: onDelete,
                  tooltip: 'Delete word',
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────── Score Pill ───────────────────────────────────
class _ScorePill extends StatelessWidget {
  final int score;
  final bool unscored;
  final bool recognitionCheck;

  const _ScorePill({
    required this.score,
    this.unscored = false,
    this.recognitionCheck = false,
  });

  @override
  Widget build(BuildContext context) {
    final color = unscored ? _primary : _scoreColor(score);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
      decoration: BoxDecoration(
        color: color.withAlpha(40),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withAlpha(100), width: 1),
      ),
      child: Text(
        unscored
            ? 'New'
            : recognitionCheck
            ? 'Check · $score%'
            : '$score%',
        style: GoogleFonts.outfit(
          fontSize: 12,
          fontWeight: FontWeight.w600,
          color: color,
        ),
      ),
    );
  }
}

// ─────────────── Action Button ────────────────────────────────
class _ActionBtn extends StatelessWidget {
  final IconData icon;
  final Color color;
  final VoidCallback onTap;
  final String tooltip;

  const _ActionBtn({
    super.key,
    required this.icon,
    required this.color,
    required this.onTap,
    required this.tooltip,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          width: 38,
          height: 38,
          decoration: BoxDecoration(
            color: color.withAlpha(25),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: color.withAlpha(70), width: 1),
          ),
          child: Icon(icon, color: color, size: 18),
        ),
      ),
    );
  }
}

// ─────────────── Add Word Section ─────────────────────────────
class _AddWordSection extends StatelessWidget {
  final TextEditingController ctrl;
  final VoidCallback onAdd;

  const _AddWordSection({required this.ctrl, required this.onAdd});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Add your own word',
          style: GoogleFonts.outfit(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            color: _textSecondary,
            letterSpacing: 0.3,
          ),
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: TextField(
                controller: ctrl,
                style: GoogleFonts.outfit(color: _textPrimary, fontSize: 15),
                decoration: InputDecoration(
                  hintText: 'e.g. pronunciation',
                  hintStyle: GoogleFonts.outfit(
                    color: _textSecondary,
                    fontSize: 15,
                  ),
                  filled: true,
                  fillColor: _surfaceCard,
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 14,
                  ),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide.none,
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(
                      color: Color(0xFF2A3E5A),
                      width: 1,
                    ),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: _primary, width: 1.5),
                  ),
                ),
                onSubmitted: (_) => onAdd(),
              ),
            ),
            const SizedBox(width: 10),
            GestureDetector(
              onTap: onAdd,
              child: Container(
                height: 50,
                width: 50,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [_primary, _accent],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(12),
                  boxShadow: [
                    BoxShadow(
                      color: _primary.withAlpha(80),
                      blurRadius: 12,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: const Icon(
                  Icons.add_rounded,
                  color: Colors.white,
                  size: 24,
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

// ─────────────── Phoneme Map Section ──────────────────────────
class _PhonemeMapSection extends StatelessWidget {
  final List<PhonemeProgress> entries;
  final int observationCount;
  final VoidCallback onStartPractice;

  const _PhonemeMapSection({
    super.key,
    required this.entries,
    required this.observationCount,
    required this.onStartPractice,
  });

  @override
  Widget build(BuildContext context) {
    if (entries.isEmpty) {
      return ListView(
        padding: const EdgeInsets.fromLTRB(20, 28, 20, 32),
        children: [
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: _surfaceCard,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: _primary.withValues(alpha: 0.22)),
            ),
            child: Column(
              children: [
                Container(
                  padding: const EdgeInsets.all(13),
                  decoration: BoxDecoration(
                    color: _primary.withValues(alpha: 0.14),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(
                    Icons.graphic_eq_rounded,
                    color: _primary,
                    size: 28,
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  'No measured phonemes yet',
                  textAlign: TextAlign.center,
                  style: GoogleFonts.outfit(
                    color: _textPrimary,
                    fontSize: 19,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  'Complete a scripted pronunciation recording to start your '
                  'map. Only phones with acoustic evidence receive a score.',
                  textAlign: TextAlign.center,
                  style: GoogleFonts.outfit(
                    color: _textSecondary,
                    fontSize: 13,
                    height: 1.45,
                  ),
                ),
                const SizedBox(height: 18),
                FilledButton.icon(
                  onPressed: onStartPractice,
                  icon: const Icon(Icons.record_voice_over_rounded),
                  label: const Text('Start pronunciation practice'),
                ),
              ],
            ),
          ),
        ],
      );
    }
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
      children: [
        _LegendRow().animate().fadeIn(duration: 400.ms),
        const SizedBox(height: 12),
        Text(
          '$observationCount acoustically scored phone '
          '${observationCount == 1 ? 'observation' : 'observations'}',
          textAlign: TextAlign.center,
          style: GoogleFonts.outfit(fontSize: 12, color: _textSecondary),
        ),
        const SizedBox(height: 24),
        _PhonemeGroupSection(title: 'Measured phonemes', phonemes: entries)
            .animate(delay: 450.ms)
            .fadeIn(duration: 400.ms)
            .slideY(begin: 0.1, end: 0),
      ],
    );
  }
}

// ─────────────── Legend ───────────────────────────────────────
class _LegendRow extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        _LegendDot(color: _error, label: 'Needs Work (<50%)'),
        const SizedBox(width: 18),
        _LegendDot(color: _warning, label: 'Fair (50–80%)'),
        const SizedBox(width: 18),
        _LegendDot(color: _success, label: 'Good (>80%)'),
      ],
    );
  }
}

class _LegendDot extends StatelessWidget {
  final Color color;
  final String label;

  const _LegendDot({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 5),
        Text(
          label,
          style: GoogleFonts.outfit(fontSize: 11, color: _textSecondary),
        ),
      ],
    );
  }
}

// ─────────────── Phoneme Group ────────────────────────────────
class _PhonemeGroupSection extends StatelessWidget {
  final String title;
  final List<PhonemeProgress> phonemes;

  const _PhonemeGroupSection({required this.title, required this.phonemes});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              width: 3,
              height: 18,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [_primary, _accent],
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                ),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(width: 8),
            Text(
              title,
              style: GoogleFonts.outfit(
                fontSize: 15,
                fontWeight: FontWeight.w700,
                color: _textPrimary,
              ),
            ),
            const Spacer(),
            Text(
              '${phonemes.length} phonemes',
              style: GoogleFonts.outfit(fontSize: 12, color: _textSecondary),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          children: phonemes.map((p) => _PhonemeCell(entry: p)).toList(),
        ),
      ],
    );
  }
}

// ─────────────── Phoneme Cell ─────────────────────────────────
class _PhonemeCell extends StatefulWidget {
  final PhonemeProgress entry;
  const _PhonemeCell({required this.entry});

  @override
  State<_PhonemeCell> createState() => _PhonemeCellState();
}

class _PhonemeCellState extends State<_PhonemeCell> {
  bool _pressed = false;

  Color get _cellColor {
    final s = widget.entry.score;
    if (s < 50) return _error;
    if (s <= 80) return _warning;
    return _success;
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) => setState(() => _pressed = false),
      onTapCancel: () => setState(() => _pressed = false),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 120),
        width: 48,
        height: 48,
        decoration: BoxDecoration(
          color: _pressed
              ? _cellColor.withAlpha(230)
              : _cellColor.withAlpha(200),
          borderRadius: BorderRadius.circular(10),
          boxShadow: [
            BoxShadow(
              color: _cellColor.withAlpha(_pressed ? 80 : 40),
              blurRadius: _pressed ? 8 : 4,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        transform: _pressed
            ? (Matrix4.identity()..scaleByDouble(0.93, 0.93, 1, 1))
            : Matrix4.identity(),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              widget.entry.symbol,
              style: GoogleFonts.outfit(
                fontSize: 14,
                fontWeight: FontWeight.w700,
                color: Colors.white,
                height: 1.1,
              ),
            ),
            Text(
              widget.entry.observations == 1
                  ? '${widget.entry.score}%'
                  : '${widget.entry.score}% · ${widget.entry.observations}',
              style: const TextStyle(
                fontSize: 8,
                fontWeight: FontWeight.w500,
                color: Colors.white70,
                height: 1.2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
