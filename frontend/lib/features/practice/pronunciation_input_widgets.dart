part of 'pronunciation_screen.dart';

extension _PronunciationInputWidgets on _PronunciationScreenState {
  Widget _buildInstructionCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            _primary.withValues(alpha: 0.12),
            _accent.withValues(alpha: 0.08),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _primary.withValues(alpha: 0.2)),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              gradient: const LinearGradient(colors: [_primary, _accent]),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(
              Icons.tips_and_updates_rounded,
              color: Colors.white,
              size: 20,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Text(
              widget.onPassed != null
                  ? 'Say the selected target exactly as shown. A correct '
                        'result moves it to your Mastered words.'
                  : 'Enter a word or sentence, then speak the exact target. '
                        'Unclear or mismatched audio is rejected instead of '
                        'guessed.',
              style: GoogleFonts.inter(
                fontSize: 13,
                color: _textSecondary,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    ).animate().fadeIn(duration: 400.ms).slideY(begin: -0.1, end: 0);
  }

  Widget _buildTargetInput() {
    return Container(
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _primary.withValues(alpha: 0.3)),
      ),
      child: TextField(
        controller: _wordCtrl,
        readOnly: widget.onPassed != null || _isRecording || _isProcessing,
        onChanged: _handleTargetChanged,
        onSubmitted: (_) => _loadPronunciationGuide(),
        textInputAction: TextInputAction.done,
        minLines: 1,
        maxLines: 3,
        maxLength: 120,
        style: GoogleFonts.inter(
          fontSize: 20,
          fontWeight: FontWeight.w600,
          color: _textPrimary,
        ),
        textAlign: TextAlign.center,
        decoration: InputDecoration(
          hintText: 'Enter a word or sentence...',
          counterText: widget.onPassed != null ? '' : null,
          hintStyle: GoogleFonts.inter(
            color: _textSecondary.withValues(alpha: 0.5),
          ),
          border: InputBorder.none,
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 20,
            vertical: 16,
          ),
          prefixIcon: Icon(
            widget.onPassed != null
                ? Icons.lock_outline_rounded
                : Icons.edit_note_rounded,
            color: _primary,
          ),
        ),
      ),
    ).animate().fadeIn(duration: 400.ms, delay: 50.ms);
  }

  Widget _buildPracticeChips() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Or try a practice target:',
          style: GoogleFonts.inter(fontSize: 12, color: _textSecondary),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: _practiceTargets.map((target) {
            final isSelected = _wordCtrl.text == target;
            return GestureDetector(
              onTap: () => _selectTarget(target),
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: isSelected
                      ? _primary.withValues(alpha: 0.2)
                      : _surfaceCard,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: isSelected ? _primary : _surfaceCard,
                    width: 1.5,
                  ),
                ),
                child: Text(
                  target,
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color: isSelected ? _primary : _textSecondary,
                  ),
                ),
              ),
            );
          }).toList(),
        ),
      ],
    ).animate().fadeIn(duration: 400.ms, delay: 100.ms);
  }

  Widget _buildPronunciationGuide() {
    if (!_hasTarget) {
      return Container(
        key: const ValueKey('pronunciation-guide-empty'),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: _surfaceCard,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: _primary.withValues(alpha: 0.18)),
        ),
        child: Row(
          children: [
            const Icon(Icons.hearing_rounded, color: _primary),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                'Enter a word or sentence above, or choose a practice target.',
                style: GoogleFonts.inter(
                  color: _textSecondary,
                  fontSize: 13,
                  height: 1.35,
                ),
              ),
            ),
          ],
        ),
      );
    }
    if (_isGuideLoading) {
      return Container(
        key: const ValueKey('pronunciation-guide-loading'),
        height: 116,
        decoration: BoxDecoration(
          color: _surfaceCard,
          borderRadius: BorderRadius.circular(16),
        ),
        child: const Center(child: CircularProgressIndicator(strokeWidth: 2)),
      );
    }
    if (_guideError case final error?) {
      return Container(
        key: const ValueKey('pronunciation-guide-error'),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: _error.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: _error.withValues(alpha: 0.25)),
        ),
        child: Row(
          children: [
            const Icon(Icons.info_outline_rounded, color: _error),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                error,
                style: GoogleFonts.inter(color: _textSecondary, fontSize: 12),
              ),
            ),
            IconButton(
              tooltip: 'Try again',
              onPressed: _loadPronunciationGuide,
              icon: const Icon(Icons.refresh_rounded),
            ),
          ],
        ),
      );
    }

    final ipa = _guide?['ipa']?.toString() ?? '';
    return Container(
      key: const ValueKey('pronunciation-guide'),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _primary.withValues(alpha: 0.28)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'IPA',
                      style: GoogleFonts.inter(
                        color: _textSecondary,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.7,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      ipa.isEmpty ? 'Unavailable' : '/$ipa/',
                      style: GoogleFonts.inter(
                        color: _accent,
                        fontSize: 22,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
              FilledButton.tonalIcon(
                key: const ValueKey('listen-to-pronunciation'),
                onPressed: _playExample,
                icon: Icon(
                  _isExamplePlaying
                      ? Icons.stop_rounded
                      : Icons.volume_up_rounded,
                ),
                label: Text(_isExamplePlaying ? 'Stop' : 'Listen'),
              ),
            ],
          ),
        ],
      ),
    ).animate().fadeIn(duration: 300.ms);
  }

  Widget _buildMicButton() {
    return Center(
      child: Column(
        children: [
          GestureDetector(
            key: const ValueKey('pronunciation-record-button'),
            onTap: _hasTarget ? _toggleRecording : null,
            child: AnimatedBuilder(
              animation: _pulseController,
              builder: (context, child) {
                final scale = _isRecording
                    ? 1.0 + (_pulseController.value * 0.08)
                    : 1.0;
                return Transform.scale(
                  scale: scale,
                  child: Container(
                    width: 88,
                    height: 88,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: LinearGradient(
                        colors: !_hasTarget || _isProcessing
                            ? [Colors.grey.shade700, Colors.grey.shade600]
                            : _isRecording
                            ? [_error, const Color(0xFFDC2626)]
                            : [_primary, _accent],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color:
                              (!_hasTarget
                                      ? Colors.grey
                                      : _isRecording
                                      ? _error
                                      : _primary)
                                  .withValues(alpha: 0.3),
                          blurRadius: _isRecording ? 28 : 16,
                          spreadRadius: _isRecording ? 4 : 0,
                        ),
                      ],
                    ),
                    child: _isProcessing
                        ? const Center(
                            child: SizedBox(
                              width: 30,
                              height: 30,
                              child: CircularProgressIndicator(
                                color: Colors.white,
                                strokeWidth: 2.5,
                              ),
                            ),
                          )
                        : Icon(
                            _isRecording
                                ? Icons.stop_rounded
                                : Icons.mic_rounded,
                            color: Colors.white,
                            size: 38,
                          ),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 14),
          Text(
            _isRecording
                ? 'Tap to stop'
                : _isProcessing
                ? 'Analyzing your pronunciation...'
                : !_hasTarget
                ? 'Enter or select a target first'
                : 'Tap to start speaking',
            style: GoogleFonts.inter(
              fontSize: 14,
              fontWeight: FontWeight.w500,
              color: _textSecondary,
            ),
          ),
        ],
      ),
    ).animate().fadeIn(duration: 400.ms, delay: 150.ms);
  }
}
