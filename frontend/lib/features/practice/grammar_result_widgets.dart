part of 'grammar_check_screen.dart';

extension _GrammarResultWidgets on _GrammarCheckScreenState {
  Widget _buildStatusCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: _isCorrect
              ? [
                  _success.withValues(alpha: 0.12),
                  _success.withValues(alpha: 0.05),
                ]
              : [
                  _accent.withValues(alpha: 0.12),
                  _primary.withValues(alpha: 0.05),
                ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: _isCorrect
              ? _success.withValues(alpha: 0.3)
              : _accent.withValues(alpha: 0.3),
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              color: _isCorrect
                  ? _success.withValues(alpha: 0.2)
                  : _accent.withValues(alpha: 0.2),
              shape: BoxShape.circle,
            ),
            child: Icon(
              _isCorrect ? Icons.check_circle_rounded : Icons.edit_note_rounded,
              color: _isCorrect ? _success : _accent,
              size: 28,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _isCorrect
                      ? 'Perfect! ✨'
                      : '${_corrections.length} Correction${_corrections.length == 1 ? '' : 's'} Found',
                  style: GoogleFonts.inter(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: _isCorrect ? _success : _textPrimary,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  _isCorrect
                      ? 'Your grammar is correct. Well done!'
                      : 'RoBERTa detected some issues. See below.',
                  style: GoogleFonts.inter(fontSize: 13, color: _textSecondary),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCorrectedTextCard() {
    return Container(
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 8, 0),
            child: Row(
              children: [
                const Icon(
                  Icons.auto_fix_high_rounded,
                  color: _success,
                  size: 18,
                ),
                const SizedBox(width: 8),
                Text(
                  'Corrected Text',
                  style: GoogleFonts.inter(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: _success,
                  ),
                ),
                const Spacer(),
                IconButton(
                  icon: const Icon(
                    Icons.copy_rounded,
                    color: _textSecondary,
                    size: 18,
                  ),
                  tooltip: 'Copy corrected text',
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: _correctedText));
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(
                          'Corrected text copied!',
                          style: GoogleFonts.inter(),
                        ),
                        backgroundColor: _success,
                        behavior: SnackBarBehavior.floating,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10),
                        ),
                      ),
                    );
                  },
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
            child: Text(
              _correctedText,
              style: GoogleFonts.inter(
                fontSize: 15,
                color: _textPrimary,
                height: 1.6,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCorrectionsList() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Text(
            'Details',
            style: GoogleFonts.inter(
              fontSize: 16,
              fontWeight: FontWeight.w700,
              color: _textPrimary,
            ),
          ),
        ),
        ...List.generate(_corrections.length, (i) {
          final c = _corrections[i];
          return _CorrectionCard(
                original: c['original']?.toString() ?? '',
                corrected: c['corrected']?.toString() ?? '',
                explanation: c['explanation']?.toString() ?? '',
                index: i,
              )
              .animate(delay: Duration(milliseconds: 80 * i + 200))
              .fadeIn(duration: 350.ms)
              .slideX(begin: 0.08, end: 0);
        }),
      ],
    );
  }
}

// ── Correction Card ──────────────────────────────────────────
