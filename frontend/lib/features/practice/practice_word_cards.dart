part of 'practice_tab.dart';

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
    final borderColor = entry.isMastered
        ? _success
        : entry.addedManually
        ? _primary
        : _warning;
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
                        mastered: entry.isMastered,
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
  final bool mastered;

  const _ScorePill({
    required this.score,
    this.unscored = false,
    this.recognitionCheck = false,
    this.mastered = false,
  });

  @override
  Widget build(BuildContext context) {
    final color = mastered
        ? _success
        : unscored
        ? _primary
        : _scoreColor(score);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
      decoration: BoxDecoration(
        color: color.withAlpha(40),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withAlpha(100), width: 1),
      ),
      child: Text(
        mastered
            ? 'Mastered'
            : unscored
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
