part of 'practice_tab.dart';

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
    final activeWords = words
        .where((word) => !word.isMastered)
        .toList(growable: false);
    final masteredWords = words
        .where((word) => word.isMastered)
        .toList(growable: false);
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
        else ...[
          if (filter == _WordFilter.all && activeWords.isNotEmpty) ...[
            const _WordSectionTitle(
              title: 'To practice',
              icon: Icons.pending_actions_rounded,
              color: _warning,
            ),
            const SizedBox(height: 8),
          ],
          ...List.generate(activeWords.length, (i) {
            final word = activeWords[i];
            return _WordCard(
                  entry: word,
                  onPractice: () => onPractice(word),
                  onDelete: () => onDelete(word),
                )
                .animate(delay: Duration(milliseconds: 60 * i))
                .fadeIn(duration: 350.ms)
                .slideY(begin: 0.15, end: 0);
          }),
          if (filter == _WordFilter.all && masteredWords.isNotEmpty) ...[
            if (activeWords.isNotEmpty) const SizedBox(height: 14),
            const _WordSectionTitle(
              title: 'Mastered',
              icon: Icons.verified_rounded,
              color: _success,
            ),
            const SizedBox(height: 8),
          ],
          ...List.generate(masteredWords.length, (i) {
            final word = masteredWords[i];
            return _WordCard(
                  entry: word,
                  onPractice: () => onPractice(word),
                  onDelete: () => onDelete(word),
                )
                .animate(
                  delay: Duration(milliseconds: 60 * (activeWords.length + i)),
                )
                .fadeIn(duration: 350.ms)
                .slideY(begin: 0.15, end: 0);
          }),
        ],
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
    _WordFilter.mastered: 'Mastered',
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
            filter == _WordFilter.mastered
                ? 'No mastered words yet'
                : filtered
                ? 'No words match this filter'
                : 'Your queue is clear',
            textAlign: TextAlign.center,
            style: GoogleFonts.outfit(
              color: _textPrimary,
              fontSize: 15,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 5),
          Text(
            filter == _WordFilter.mastered
                ? 'Words move here after you pronounce them correctly.'
                : filtered
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

class _WordSectionTitle extends StatelessWidget {
  final String title;
  final IconData icon;
  final Color color;

  const _WordSectionTitle({
    required this.title,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, color: color, size: 17),
        const SizedBox(width: 7),
        Text(
          title,
          style: GoogleFonts.outfit(
            color: _textPrimary,
            fontSize: 14,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }
}

// ─────────────── Word Card ────────────────────────────────────
