import 'package:flutter/material.dart';
import 'package:speakflow/core/theme/local_fonts.dart';

const _surface = Color(0xFF111827);
const _success = Color(0xFF22C55E);
const _warning = Color(0xFFF59E0B);
const _text = Color(0xFFF1F5FF);
const _muted = Color(0xFF8896B0);

bool hasRoleplayGrammarCorrection({
  required String originalText,
  required String? correctedText,
}) {
  final corrected = correctedText?.trim();
  return corrected != null &&
      corrected.isNotEmpty &&
      corrected.toLowerCase() != originalText.trim().toLowerCase();
}

bool hasRoleplayGrammarAnalysis({
  required String originalText,
  required String? correctedText,
  required String? grammarFeedback,
}) {
  return hasRoleplayGrammarCorrection(
        originalText: originalText,
        correctedText: correctedText,
      ) ||
      grammarFeedback?.trim().isNotEmpty == true;
}

class RoleplayGrammarButton extends StatelessWidget {
  final String originalText;
  final String? correctedText;
  final String? grammarFeedback;

  const RoleplayGrammarButton({
    super.key,
    required this.originalText,
    required this.correctedText,
    required this.grammarFeedback,
  });

  bool get _hasCorrection => hasRoleplayGrammarCorrection(
    originalText: originalText,
    correctedText: correctedText,
  );

  @override
  Widget build(BuildContext context) {
    if (!hasRoleplayGrammarAnalysis(
      originalText: originalText,
      correctedText: correctedText,
      grammarFeedback: grammarFeedback,
    )) {
      return const SizedBox.shrink();
    }
    return TextButton.icon(
      onPressed: () => _showGrammar(context),
      icon: const Icon(Icons.spellcheck_rounded, size: 16),
      label: const Text('Grammar'),
      style: TextButton.styleFrom(
        foregroundColor: _warning,
        textStyle: GoogleFonts.inter(fontSize: 11, fontWeight: FontWeight.w600),
      ),
    );
  }

  void _showGrammar(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: _surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Grammar',
                style: GoogleFonts.inter(
                  color: _text,
                  fontSize: 17,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 16),
              _sectionLabel('Your sentence'),
              const SizedBox(height: 5),
              Text(
                originalText,
                style: GoogleFonts.inter(
                  color: _text,
                  fontSize: 14,
                  height: 1.45,
                ),
              ),
              const SizedBox(height: 16),
              if (_hasCorrection) ...[
                _sectionLabel('Suggested correction'),
                const SizedBox(height: 5),
                Text(
                  correctedText!,
                  style: GoogleFonts.inter(
                    color: _success,
                    fontSize: 14,
                    height: 1.45,
                  ),
                ),
                const SizedBox(height: 16),
                _sectionLabel('Explanation'),
                const SizedBox(height: 5),
                Text(
                  _grammarExplanation,
                  style: GoogleFonts.inter(
                    color: _text,
                    fontSize: 13,
                    height: 1.45,
                  ),
                ),
              ] else
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(
                      Icons.check_circle_rounded,
                      color: _success,
                      size: 20,
                    ),
                    const SizedBox(width: 9),
                    Expanded(
                      child: Text(
                        'No grammar mistakes were detected in this sentence.',
                        style: GoogleFonts.inter(
                          color: _text,
                          fontSize: 13,
                          height: 1.45,
                        ),
                      ),
                    ),
                  ],
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _sectionLabel(String value) {
    return Text(
      value,
      style: GoogleFonts.inter(
        color: _muted,
        fontSize: 11,
        fontWeight: FontWeight.w600,
      ),
    );
  }

  String get _grammarExplanation {
    final feedback = grammarFeedback?.trim() ?? '';
    final correctedMarker = RegExp(r'\s*Corrected:\s*', caseSensitive: false);
    final marker = correctedMarker.firstMatch(feedback);
    final explanation = marker == null
        ? feedback
        : feedback.substring(0, marker.start).trim();
    if (explanation.isNotEmpty && explanation.toLowerCase() != 'correct') {
      return explanation;
    }
    return 'The grammar checker changed the sentence as shown above.';
  }
}
