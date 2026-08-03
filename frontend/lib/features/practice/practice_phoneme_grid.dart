part of 'practice_tab.dart';

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
              style: GoogleFonts.inter(
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
