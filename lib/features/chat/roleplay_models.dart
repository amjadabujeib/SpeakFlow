class RoleplayObjective {
  final String id;
  final String label;
  final int weight;
  final bool required;

  const RoleplayObjective({
    required this.id,
    required this.label,
    required this.weight,
    required this.required,
  });

  factory RoleplayObjective.fromJson(Map<String, dynamic> json) {
    return RoleplayObjective(
      id: json['id']?.toString() ?? '',
      label: json['label']?.toString() ?? '',
      weight: (json['weight'] as num?)?.round() ?? 1,
      required: json['required'] != false,
    );
  }
}

class RoleplayRubric {
  final String id;
  final String label;
  final String description;
  final int weight;

  const RoleplayRubric({
    required this.id,
    required this.label,
    required this.description,
    required this.weight,
  });

  factory RoleplayRubric.fromJson(Map<String, dynamic> json) {
    return RoleplayRubric(
      id: json['id']?.toString() ?? '',
      label: json['label']?.toString() ?? '',
      description: json['description']?.toString() ?? '',
      weight: (json['weight'] as num?)?.round() ?? 1,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'label': label,
    'description': description,
    'weight': weight,
  };
}

class RoleplayScenario {
  final String id;
  final int version;
  final String category;
  final String icon;
  final String title;
  final String description;
  final String aiRole;
  final String learnerRole;
  final String opening;
  final List<RoleplayObjective> objectives;
  final List<String> targetLanguage;
  final List<RoleplayRubric> evaluationRubric;
  final String? designedCefrLevel;
  final bool custom;

  const RoleplayScenario({
    required this.id,
    required this.version,
    required this.category,
    required this.icon,
    required this.title,
    required this.description,
    required this.aiRole,
    required this.learnerRole,
    required this.opening,
    required this.objectives,
    required this.targetLanguage,
    required this.evaluationRubric,
    required this.designedCefrLevel,
    required this.custom,
  });

  factory RoleplayScenario.fromJson(Map<String, dynamic> json) {
    final rawObjectives = json['objectives'];
    final rawLanguage = json['target_language'];
    final rawRubric = json['evaluation_rubric'];
    return RoleplayScenario(
      id: json['id']?.toString() ?? '',
      version: (json['version'] as num?)?.round() ?? 1,
      category: json['category']?.toString() ?? 'Other',
      icon: json['icon']?.toString() ?? '🎭',
      title: json['title']?.toString() ?? 'Roleplay',
      description: json['description']?.toString() ?? '',
      aiRole: json['ai_role']?.toString() ?? 'conversation partner',
      learnerRole: json['learner_role']?.toString() ?? 'learner',
      opening: json['opening']?.toString() ?? 'Hello. Shall we begin?',
      objectives: rawObjectives is List
          ? rawObjectives
                .whereType<Map>()
                .map(
                  (item) => RoleplayObjective.fromJson(
                    Map<String, dynamic>.from(item),
                  ),
                )
                .toList(growable: false)
          : const [],
      targetLanguage: rawLanguage is List
          ? rawLanguage.map((item) => item.toString()).toList(growable: false)
          : const [],
      evaluationRubric: rawRubric is List
          ? rawRubric
                .whereType<Map>()
                .map(
                  (item) =>
                      RoleplayRubric.fromJson(Map<String, dynamic>.from(item)),
                )
                .toList(growable: false)
          : const [],
      designedCefrLevel: json['designed_cefr_level']?.toString(),
      custom: json['custom'] == true,
    );
  }
}

class RoleplayLaunchArgs {
  final RoleplayScenario scenario;

  const RoleplayLaunchArgs(this.scenario);
}

class RoleplayEscapeOption {
  final String style;
  final String label;
  final String text;

  const RoleplayEscapeOption({
    required this.style,
    required this.label,
    required this.text,
  });

  factory RoleplayEscapeOption.fromJson(Map<String, dynamic> json) {
    return RoleplayEscapeOption(
      style: json['style']?.toString() ?? '',
      label: json['label']?.toString() ?? '',
      text: json['text']?.toString() ?? '',
    );
  }
}

class RoleplayTranscriptTurn {
  final String turnId;
  final int sequence;
  final String inputMode;
  final String userText;
  final String assistantText;
  final DateTime? createdAt;

  const RoleplayTranscriptTurn({
    required this.turnId,
    required this.sequence,
    required this.inputMode,
    required this.userText,
    required this.assistantText,
    required this.createdAt,
  });

  factory RoleplayTranscriptTurn.fromJson(Map<String, dynamic> json) {
    return RoleplayTranscriptTurn(
      turnId: json['turn_id']?.toString() ?? '',
      sequence: (json['sequence'] as num?)?.round() ?? 0,
      inputMode: json['input_mode']?.toString() ?? 'text',
      userText: json['user_text']?.toString() ?? '',
      assistantText: json['assistant_text']?.toString() ?? '',
      createdAt: DateTime.tryParse(json['created_at']?.toString() ?? ''),
    );
  }
}

class RoleplayTranscript {
  final bool readOnly;
  final RoleplayScenario scenario;
  final Map<String, dynamic> session;
  final List<RoleplayTranscriptTurn> turns;

  const RoleplayTranscript({
    required this.readOnly,
    required this.scenario,
    required this.session,
    required this.turns,
  });

  factory RoleplayTranscript.fromJson(Map<String, dynamic> json) {
    final rawTurns = json['turns'];
    return RoleplayTranscript(
      readOnly: json['read_only'] == true,
      scenario: RoleplayScenario.fromJson(
        Map<String, dynamic>.from(json['scenario'] as Map? ?? {}),
      ),
      session: Map<String, dynamic>.from(json['session'] as Map? ?? {}),
      turns: rawTurns is List
          ? rawTurns
                .whereType<Map>()
                .map(
                  (item) => RoleplayTranscriptTurn.fromJson(
                    Map<String, dynamic>.from(item),
                  ),
                )
                .toList(growable: false)
          : const [],
    );
  }
}

class RoleplayHistoryArgs {
  final String clientSessionId;
  final String title;

  const RoleplayHistoryArgs({
    required this.clientSessionId,
    required this.title,
  });
}
