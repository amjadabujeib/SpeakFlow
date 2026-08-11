class RoleplayRecognitionCheck {
  final String word;
  final int confidence;
  final String reason;

  const RoleplayRecognitionCheck({
    required this.word,
    required this.confidence,
    required this.reason,
  });

  factory RoleplayRecognitionCheck.fromJson(Map<String, dynamic> json) {
    return RoleplayRecognitionCheck(
      word: json['word']?.toString() ?? '',
      confidence: ((json['confidence'] as num?)?.round() ?? 0).clamp(0, 100),
      reason: json['reason']?.toString() ?? 'recognizer_uncertain',
    );
  }
}

class RoleplayCorrection {
  final String turnId;
  final String original;
  final String corrected;
  final String? feedback;

  const RoleplayCorrection({
    required this.turnId,
    required this.original,
    required this.corrected,
    this.feedback,
  });

  factory RoleplayCorrection.fromJson(Map<String, dynamic> json) {
    return RoleplayCorrection(
      turnId: json['turn_id']?.toString() ?? '',
      original: json['original']?.toString() ?? '',
      corrected: json['corrected']?.toString() ?? '',
      feedback: json['feedback']?.toString(),
    );
  }
}

class RoleplayFeedbackData {
  final String scenario;
  final String icon;
  final int messageCount;
  final int durationSeconds;
  final bool eligible;
  final bool objectiveCompleted;
  final String evidenceNote;
  final Map<String, int?> scores;
  final Map<String, dynamic> evidence;
  final List<RoleplayRecognitionCheck> recognitionChecks;
  final List<RoleplayCorrection> corrections;
  final int practiceWordsAdded;
  final bool historySaved;

  const RoleplayFeedbackData({
    required this.scenario,
    required this.icon,
    required this.messageCount,
    required this.durationSeconds,
    required this.eligible,
    required this.objectiveCompleted,
    required this.evidenceNote,
    required this.scores,
    required this.evidence,
    required this.recognitionChecks,
    required this.corrections,
    this.practiceWordsAdded = 0,
    this.historySaved = true,
  });

  RoleplayFeedbackData withPracticeWordsAdded(int count) {
    return RoleplayFeedbackData(
      scenario: scenario,
      icon: icon,
      messageCount: messageCount,
      durationSeconds: durationSeconds,
      eligible: eligible,
      objectiveCompleted: objectiveCompleted,
      evidenceNote: evidenceNote,
      scores: scores,
      evidence: evidence,
      recognitionChecks: recognitionChecks,
      corrections: corrections,
      practiceWordsAdded: count < 0 ? 0 : count,
      historySaved: historySaved,
    );
  }

  List<Map<String, dynamic>> get scenarioEvidence {
    if (!eligible) return const [];
    final raw = evidence['scenario_evidence'];
    return raw is List
        ? raw
              .whereType<Map>()
              .map((item) => Map<String, dynamic>.from(item))
              .toList(growable: false)
        : const [];
  }

  factory RoleplayFeedbackData.fromFinalizeJson(Map<String, dynamic> json) {
    final session = Map<String, dynamic>.from(json['session'] as Map? ?? {});
    final evaluation = Map<String, dynamic>.from(
      session['evaluation'] as Map? ?? {},
    );
    final rawScores = Map<String, dynamic>.from(
      evaluation['scores'] as Map? ?? {},
    );
    final rawScenario = Map<String, dynamic>.from(
      evaluation['scenario'] as Map? ?? {},
    );
    final rawRecognition = evaluation['recognition_checks'];
    final rawCorrections = json['corrections'];
    final eligible = evaluation['eligible'] == true;
    return RoleplayFeedbackData(
      scenario:
          rawScenario['title']?.toString() ??
          session['scenario']?.toString() ??
          'Roleplay',
      icon: rawScenario['icon']?.toString() ?? '🎭',
      messageCount: ((session['message_count'] as num?)?.round() ?? 0).clamp(
        0,
        500,
      ),
      durationSeconds: ((session['duration_seconds'] as num?)?.round() ?? 0)
          .clamp(0, 21600),
      eligible: eligible,
      objectiveCompleted: evaluation['scenario_completed'] == true,
      evidenceNote:
          evaluation['eligibility_note']?.toString() ??
          'Keep practicing to build a reliable evaluation.',
      scores: {
        for (final entry in rawScores.entries)
          entry.key:
              entry.value is num &&
                  (eligible || entry.key == 'task_achievement')
              ? (entry.value as num).round().clamp(0, 100)
              : null,
      },
      evidence: Map<String, dynamic>.from(evaluation['evidence'] as Map? ?? {}),
      recognitionChecks: rawRecognition is List
          ? rawRecognition
                .whereType<Map>()
                .map(
                  (item) => RoleplayRecognitionCheck.fromJson(
                    Map<String, dynamic>.from(item),
                  ),
                )
                .where((item) => item.word.isNotEmpty)
                .toList(growable: false)
          : const [],
      corrections: rawCorrections is List
          ? rawCorrections
                .whereType<Map>()
                .map(
                  (item) => RoleplayCorrection.fromJson(
                    Map<String, dynamic>.from(item),
                  ),
                )
                .where(
                  (item) =>
                      item.original.isNotEmpty &&
                      item.corrected.isNotEmpty &&
                      item.original != item.corrected,
                )
                .toList(growable: false)
          : const [],
      historySaved: true,
    );
  }

  static const empty = RoleplayFeedbackData(
    scenario: 'Roleplay',
    icon: '🎭',
    messageCount: 0,
    durationSeconds: 0,
    eligible: false,
    objectiveCompleted: false,
    evidenceNote: 'No session evidence is available.',
    scores: {},
    evidence: {},
    recognitionChecks: [],
    corrections: [],
    practiceWordsAdded: 0,
    historySaved: false,
  );
}
