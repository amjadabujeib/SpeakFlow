part of 'pronunciation_screen.dart';

extension _PronunciationResultWidgets on _PronunciationScreenState {
  Widget _buildErrorCard() {
    return Container(
          margin: const EdgeInsets.only(bottom: 16),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: _error.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: _error.withValues(alpha: 0.3)),
          ),
          child: Row(
            children: [
              const Icon(Icons.error_outline_rounded, color: _error, size: 20),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  _errorMessage!,
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    color: _error,
                    height: 1.3,
                  ),
                ),
              ),
            ],
          ),
        )
        .animate()
        .fadeIn(duration: 300.ms)
        .shakeX(hz: 3, amount: 3, duration: 400.ms);
  }

  Widget _buildScoreCard() {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _scoreColor.withValues(alpha: 0.3)),
      ),
      child: Column(
        children: [
          Text(
            'Pronunciation Score',
            style: GoogleFonts.inter(fontSize: 13, color: _textSecondary),
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '$_score',
                style: GoogleFonts.inter(
                  fontSize: 56,
                  fontWeight: FontWeight.w800,
                  color: _scoreColor,
                  height: 1,
                ),
              ),
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  '/100',
                  style: GoogleFonts.inter(
                    fontSize: 20,
                    fontWeight: FontWeight.w500,
                    color: _textSecondary,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          // Overall score bar
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(
              value: _score / 100.0,
              backgroundColor: _surface,
              color: _scoreColor,
              minHeight: 8,
            ),
          ),
          // Multi-aspect breakdown (when backend scores available)
          if (_scores != null) ...[
            const SizedBox(height: 20),
            const Divider(color: Color(0xFF1E2D45), height: 1),
            const SizedBox(height: 16),
            _buildScoreBar('Accuracy', _scores!['accuracy'] as num?),
            const SizedBox(height: 10),
            _buildScoreBar('Fluency', _scores!['fluency'] as num?),
            const SizedBox(height: 10),
            _buildScoreBar('Prosody', _scores!['prosody'] as num?),
            const SizedBox(height: 10),
            _buildScoreBar('Completeness', _scores!['completeness'] as num?),
          ],
          const SizedBox(height: 12),
          if (_spokenResult != null)
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  'You said: ',
                  style: GoogleFonts.inter(fontSize: 13, color: _textSecondary),
                ),
                Text(
                  '"$_spokenResult"',
                  style: GoogleFonts.inter(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color:
                        _spokenResult!.trim().toLowerCase() ==
                            _wordCtrl.text.trim().toLowerCase()
                        ? _success
                        : _textPrimary,
                  ),
                ),
                if (_spokenResult!.trim().toLowerCase() ==
                    _wordCtrl.text.trim().toLowerCase()) ...[
                  const SizedBox(width: 6),
                  const Icon(
                    Icons.stars_rounded,
                    color: Color(0xFFF59E0B),
                    size: 18,
                  ),
                ],
              ],
            ),
        ],
      ),
    ).animate().fadeIn(duration: 400.ms).slideY(begin: 0.05, end: 0);
  }

  Widget _buildPhonemeCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _primary.withValues(alpha: 0.15)),
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.graphic_eq_rounded, color: _accent, size: 18),
              const SizedBox(width: 8),
              Text(
                'Phone analysis (IPA)',
                style: GoogleFonts.inter(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: _textSecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Wrap(
            alignment: WrapAlignment.center,
            spacing: 4,
            runSpacing: 6,
            children: _analysis!.asMap().entries.map((entry) {
              final idx = entry.key;
              final charData = entry.value as Map<String, dynamic>;
              final String char = charData['char'] ?? '?';
              final status = charData['status']?.toString() ?? 'warning';
              final color = switch (status) {
                'correct' => _success,
                'incorrect' => _error,
                'omitted' => _textSecondary,
                _ => _warning,
              };
              final quality = charData['score'];
              final likelyIpa = charData['likely_ipa']?.toString();
              final closestIpa = charData['closest_ipa']?.toString();
              final errorType = charData['error_type']?.toString();
              final tooltip = quality is! num
                  ? 'Omitted / not acoustically scored'
                  : status == 'incorrect' &&
                        errorType == 'substitution' &&
                        likelyIpa != null &&
                        likelyIpa.isNotEmpty
                  ? 'Target /$char/ • sounded closer to /$likelyIpa/ • quality ${quality.round()}%'
                  : status == 'incorrect' && errorType == 'deletion'
                  ? 'Target /$char/ may have been omitted • quality ${quality.round()}%'
                  : status == 'warning' &&
                        closestIpa != null &&
                        closestIpa.isNotEmpty
                  ? 'Target /$char/ needs attention • closest acoustic guess /$closestIpa/ • quality ${quality.round()}%'
                  : '${status == 'warning' ? 'Needs attention' : status} • quality ${quality.round()}%';

              return Tooltip(
                    message: tooltip,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 6,
                      ),
                      decoration: BoxDecoration(
                        color: color.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: color.withValues(alpha: 0.4),
                          width: 1.5,
                        ),
                      ),
                      child: Text(
                        char,
                        style: GoogleFonts.inter(
                          fontSize: 24,
                          fontWeight: FontWeight.w700,
                          color: color,
                        ),
                      ),
                    ),
                  )
                  .animate(delay: Duration(milliseconds: 40 * idx))
                  .fadeIn(duration: 250.ms)
                  .scale(
                    begin: const Offset(0.8, 0.8),
                    end: const Offset(1, 1),
                    duration: 250.ms,
                  );
            }).toList(),
          ),
        ],
      ),
    ).animate().fadeIn(duration: 400.ms, delay: 100.ms).slideY(begin: 0.05, end: 0);
  }

  Widget _buildFeedbackCard() {
    return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                _accent.withValues(alpha: 0.1),
                _primary.withValues(alpha: 0.06),
              ],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: _accent.withValues(alpha: 0.25)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [_accent, _primary],
                      ),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(
                      Icons.psychology_rounded,
                      color: Colors.white,
                      size: 16,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    'How to improve',
                    style: GoogleFonts.inter(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: _textPrimary,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                _feedback!,
                style: GoogleFonts.inter(
                  fontSize: 13,
                  color: _textSecondary,
                  height: 1.5,
                ),
              ),
            ],
          ),
        )
        .animate()
        .fadeIn(duration: 400.ms, delay: 200.ms)
        .slideY(begin: 0.05, end: 0);
  }

  Widget _buildScoreBar(String label, num? rawScore) {
    final score = rawScore?.round();
    if (score == null) {
      return Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: GoogleFonts.inter(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: _textSecondary,
            ),
          ),
          Text(
            'Not enough evidence',
            style: GoogleFonts.inter(fontSize: 11, color: _textSecondary),
          ),
        ],
      );
    }
    Color barColor;
    if (score >= 90) {
      barColor = _success;
    } else if (score >= 70) {
      barColor = _primary;
    } else if (score >= 50) {
      barColor = _warning;
    } else {
      barColor = _error;
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              label,
              style: GoogleFonts.inter(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: _textSecondary,
              ),
            ),
            Text(
              '$score%',
              style: GoogleFonts.inter(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: barColor,
              ),
            ),
          ],
        ),
        const SizedBox(height: 5),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: score / 100.0,
            backgroundColor: _surface,
            color: barColor,
            minHeight: 6,
          ),
        ),
      ],
    );
  }
}
