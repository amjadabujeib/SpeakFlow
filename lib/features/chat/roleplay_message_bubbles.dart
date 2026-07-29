import 'package:flutter/material.dart';
import 'package:speakflow/core/theme/local_fonts.dart';

import 'roleplay_confidence_transcript.dart';
import 'roleplay_grammar_feedback.dart';

const _card = Color(0xFF1A2235);
const _primary = Color(0xFF4F7FFF);
const _accent = Color(0xFF8B5CF6);
const _text = Color(0xFFF1F5FF);
const _border = Color(0xFF263550);

class RoleplayPartnerMessageBubble extends StatelessWidget {
  final String text;
  final bool hasAudio;
  final VoidCallback? onPlay;

  const RoleplayPartnerMessageBubble({
    super.key,
    required this.text,
    this.hasAudio = false,
    this.onPlay,
  });

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.sizeOf(context).width * .82,
        ),
        margin: const EdgeInsets.only(bottom: 14, right: 32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Container(
                  width: 31,
                  height: 31,
                  margin: const EdgeInsets.only(right: 8),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(colors: [_primary, _accent]),
                    borderRadius: BorderRadius.circular(10),
                    boxShadow: [
                      BoxShadow(
                        color: _primary.withValues(alpha: .18),
                        blurRadius: 10,
                        offset: const Offset(0, 3),
                      ),
                    ],
                  ),
                  child: const Icon(
                    Icons.forum_rounded,
                    color: Colors.white,
                    size: 17,
                  ),
                ),
                Expanded(
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 15,
                      vertical: 13,
                    ),
                    decoration: BoxDecoration(
                      color: _card,
                      borderRadius: const BorderRadius.only(
                        topLeft: Radius.circular(17),
                        topRight: Radius.circular(17),
                        bottomRight: Radius.circular(17),
                        bottomLeft: Radius.circular(5),
                      ),
                      border: Border.all(color: _border),
                    ),
                    child: Text(
                      text,
                      style: GoogleFonts.inter(
                        color: _text,
                        fontSize: 14,
                        height: 1.48,
                      ),
                    ),
                  ),
                ),
              ],
            ),
            if (hasAudio && onPlay != null)
              Padding(
                padding: const EdgeInsets.only(left: 39, top: 3),
                child: TextButton.icon(
                  onPressed: onPlay,
                  icon: const Icon(Icons.volume_up_rounded, size: 16),
                  label: const Text('Listen again'),
                  style: TextButton.styleFrom(
                    foregroundColor: _primary,
                    visualDensity: VisualDensity.compact,
                    textStyle: GoogleFonts.inter(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class RoleplayUserMessageBubble extends StatelessWidget {
  final String text;
  final String? correctedText;
  final String? grammarFeedback;
  final List<Map<String, dynamic>> wordConfidence;
  final bool hasReplay;
  final VoidCallback? onReplay;
  final Key? transcriptKey;

  const RoleplayUserMessageBubble({
    super.key,
    required this.text,
    required this.correctedText,
    required this.grammarFeedback,
    required this.wordConfidence,
    this.hasReplay = false,
    this.onReplay,
    this.transcriptKey,
  });

  bool get _hasGrammarAnalysis => hasRoleplayGrammarAnalysis(
    originalText: text,
    correctedText: correctedText,
    grammarFeedback: grammarFeedback,
  );

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerRight,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.sizeOf(context).width * .82,
        ),
        margin: const EdgeInsets.only(bottom: 14, left: 32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 13),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    _primary.withValues(alpha: .42),
                    _accent.withValues(alpha: .38),
                  ],
                ),
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(17),
                  topRight: Radius.circular(17),
                  bottomLeft: Radius.circular(17),
                  bottomRight: Radius.circular(5),
                ),
                border: Border.all(color: _primary.withValues(alpha: .42)),
                boxShadow: [
                  BoxShadow(
                    color: _primary.withValues(alpha: .1),
                    blurRadius: 12,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: RoleplayConfidenceTranscript(
                text: text,
                wordConfidence: wordConfidence,
                transcriptKey: transcriptKey,
                style: GoogleFonts.inter(
                  color: Colors.white,
                  fontSize: 14,
                  height: 1.48,
                ),
              ),
            ),
            if ((hasReplay && onReplay != null) || _hasGrammarAnalysis)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Wrap(
                  spacing: 2,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  alignment: WrapAlignment.end,
                  children: [
                    if (hasReplay && onReplay != null)
                      IconButton(
                        onPressed: onReplay,
                        tooltip: 'Replay recording',
                        iconSize: 19,
                        visualDensity: VisualDensity.compact,
                        color: _primary,
                        icon: const Icon(Icons.replay_rounded),
                      ),
                    if (_hasGrammarAnalysis)
                      RoleplayGrammarButton(
                        originalText: text,
                        correctedText: correctedText,
                        grammarFeedback: grammarFeedback,
                      ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
