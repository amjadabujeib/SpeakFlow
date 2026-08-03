part of 'grammar_check_screen.dart';

extension _GrammarInputWidgets on _GrammarCheckScreenState {
  Widget _buildInputCard() {
    final charCount = _textCtrl.text.length;
    return Container(
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: _border, width: 1),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.25),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        children: [
          TextField(
            controller: _textCtrl,
            maxLines: 6,
            maxLength: _GrammarCheckScreenState._maxChars,
            style: GoogleFonts.inter(
              color: _textPrimary,
              fontSize: 15,
              height: 1.6,
            ),
            onChanged: (_) {
              _requestSerial++;
              _update(() {
                _isLoading = false;
                _hasResult = false;
                _errorMsg = null;
              });
            },
            decoration: InputDecoration(
              hintText: 'Type or paste your English text here…',
              hintStyle: GoogleFonts.inter(color: _textSecondary, fontSize: 15),
              filled: true,
              fillColor: Colors.transparent,
              counterText: '',
              contentPadding: const EdgeInsets.all(18),
              border: InputBorder.none,
            ),
          ),
          Container(height: 1, color: _border.withValues(alpha: 0.5)),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            child: Row(
              children: [
                // Character count
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: charCount > _GrammarCheckScreenState._maxChars * 0.9
                        ? _error.withValues(alpha: 0.15)
                        : _primary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    '$charCount/$_GrammarCheckScreenState._maxChars',
                    style: GoogleFonts.inter(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color:
                          charCount > _GrammarCheckScreenState._maxChars * 0.9
                          ? _error
                          : _primary,
                    ),
                  ),
                ),
                const Spacer(),
                // Clear button
                if (_textCtrl.text.isNotEmpty)
                  GestureDetector(
                    onTap: _clearText,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 6,
                      ),
                      decoration: BoxDecoration(
                        border: Border.all(
                          color: _textSecondary.withValues(alpha: 0.4),
                        ),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        'Clear',
                        style: GoogleFonts.inter(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: _textSecondary,
                        ),
                      ),
                    ),
                  ),
                const SizedBox(width: 8),
                // Try example
                GestureDetector(
                  onTap: _tryExample,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: _accent.withValues(alpha: 0.12),
                      border: Border.all(color: _accent.withValues(alpha: 0.3)),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      '💡 Try Example',
                      style: GoogleFonts.inter(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: _accent,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    ).animate().fadeIn(duration: 400.ms).slideY(begin: -0.05, end: 0);
  }

  Widget _buildCheckButton() {
    final isEnabled = _textCtrl.text.trim().isNotEmpty && !_isLoading;
    return GestureDetector(
      onTap: isEnabled ? _checkGrammar : null,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        height: 56,
        decoration: BoxDecoration(
          gradient: isEnabled
              ? const LinearGradient(
                  colors: [_primary, _accent],
                  begin: Alignment.centerLeft,
                  end: Alignment.centerRight,
                )
              : null,
          color: isEnabled ? null : _surfaceCard,
          borderRadius: BorderRadius.circular(16),
          boxShadow: isEnabled
              ? [
                  BoxShadow(
                    color: _primary.withValues(alpha: 0.35),
                    blurRadius: 16,
                    offset: const Offset(0, 6),
                  ),
                ]
              : null,
        ),
        child: Center(
          child: _isLoading
              ? const SizedBox(
                  width: 24,
                  height: 24,
                  child: CircularProgressIndicator(
                    color: Colors.white,
                    strokeWidth: 2.5,
                  ),
                )
              : Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.spellcheck_rounded,
                      color: isEnabled ? Colors.white : _textSecondary,
                      size: 20,
                    ),
                    const SizedBox(width: 10),
                    Text(
                      'Check Grammar ✨',
                      style: GoogleFonts.inter(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: isEnabled ? Colors.white : _textSecondary,
                      ),
                    ),
                  ],
                ),
        ),
      ),
    );
  }

  Widget _buildErrorCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _error.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: _error.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline_rounded, color: _error, size: 22),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              _errorMsg ?? 'An error occurred',
              style: GoogleFonts.inter(
                color: _error,
                fontSize: 13,
                height: 1.4,
              ),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.refresh_rounded, color: _error, size: 20),
            onPressed: _checkGrammar,
          ),
        ],
      ),
    ).animate().fadeIn(duration: 300.ms).shake(hz: 2, duration: 400.ms);
  }
}
