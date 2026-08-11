part of 'practice_tab.dart';

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
                  'map. It averages acoustic quality from transcript-verified '
                  'recordings; it is not a correctness or mastery verdict.',
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
          '$observationCount transcript-verified acoustic phone '
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
        _LegendDot(color: _error, label: 'Acoustic <50%'),
        const SizedBox(width: 18),
        _LegendDot(color: _warning, label: 'Acoustic 50–80%'),
        const SizedBox(width: 18),
        _LegendDot(color: _success, label: 'Acoustic >80%'),
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
