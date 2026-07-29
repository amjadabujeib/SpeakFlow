import 'dart:collection';

import 'package:flutter/material.dart';
import 'package:speakflow/core/theme/local_fonts.dart';

class RoleplayConfidenceTranscript extends StatelessWidget {
  final String text;
  final List<Map<String, dynamic>> wordConfidence;
  final TextStyle? style;
  final Key? transcriptKey;

  const RoleplayConfidenceTranscript({
    super.key,
    required this.text,
    required this.wordConfidence,
    this.style,
    this.transcriptKey,
  });

  static const highConfidenceColor = Color(0xFF86EFAC);
  static const mediumConfidenceColor = Color(0xFFFDE68A);
  static const lowConfidenceColor = Color(0xFFFCA5A5);

  @override
  Widget build(BuildContext context) {
    final baseStyle =
        style ??
        GoogleFonts.inter(color: Colors.white, fontSize: 14, height: 1.45);
    if (wordConfidence.isEmpty) {
      return Text(text, key: transcriptKey, style: baseStyle);
    }
    final transcript = Text.rich(
      TextSpan(style: baseStyle, children: _spans(baseStyle)),
      key: transcriptKey,
    );
    return Semantics(
      label: _confidenceSemantics,
      child: ExcludeSemantics(child: transcript),
    );
  }

  List<InlineSpan> _spans(TextStyle baseStyle) {
    final spans = <InlineSpan>[];
    final matches = RegExp(
      r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)?",
    ).allMatches(text);
    final feedbackIndexes = <String, Queue<int>>{};
    for (var index = 0; index < wordConfidence.length; index++) {
      final word = _normalizedWord(
        wordConfidence[index]['word']?.toString() ?? '',
      );
      if (word.isNotEmpty) {
        feedbackIndexes.putIfAbsent(word, Queue<int>.new).add(index);
      }
    }
    var cursor = 0;
    var feedbackCursor = 0;

    for (final match in matches) {
      if (match.start > cursor) {
        spans.add(TextSpan(text: text.substring(cursor, match.start)));
      }
      final token = match.group(0)!;
      final candidates = feedbackIndexes[_normalizedWord(token)];
      while (candidates?.isNotEmpty == true &&
          candidates!.first < feedbackCursor) {
        candidates.removeFirst();
      }
      final feedbackIndex = candidates?.isNotEmpty == true
          ? candidates!.removeFirst()
          : null;
      final score = feedbackIndex == null
          ? null
          : _normalizedScore(wordConfidence[feedbackIndex]['score']);
      if (feedbackIndex != null) feedbackCursor = feedbackIndex + 1;
      spans.add(
        TextSpan(
          text: token,
          style: score == null
              ? null
              : baseStyle.copyWith(
                  color: _colorForScore(score),
                  fontWeight: FontWeight.w700,
                ),
        ),
      );
      cursor = match.end;
    }
    if (cursor < text.length) {
      spans.add(TextSpan(text: text.substring(cursor)));
    }
    return spans;
  }

  String get _confidenceSemantics {
    final scored = <String>[];
    for (final word in wordConfidence) {
      final value = word['word']?.toString().trim() ?? '';
      final score = _normalizedScore(word['score']);
      if (value.isEmpty || score == null) continue;
      final level = score >= .8
          ? 'clear'
          : score >= .5
          ? 'review'
          : 'low confidence';
      scored.add('$value: $level');
    }
    if (scored.isEmpty) return text;
    return '$text Word confidence: ${scored.join(', ')}.';
  }

  static String _normalizedWord(String value) {
    return value
        .toLowerCase()
        .replaceAll('’', "'")
        .replaceAll(RegExp(r"[^a-z0-9']"), '');
  }

  static double? _normalizedScore(dynamic raw) {
    if (raw is! num || !raw.isFinite) return null;
    final value = raw.toDouble();
    if (value >= 0 && value <= 1) return value;
    if (value > 1 && value <= 100) return value / 100;
    return null;
  }

  static Color _colorForScore(double score) {
    if (score >= .8) return highConfidenceColor;
    if (score >= .5) return mediumConfidenceColor;
    return lowConfidenceColor;
  }
}
