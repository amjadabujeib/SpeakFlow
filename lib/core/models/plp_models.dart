// lib/core/models/plp_models.dart

class PLPLesson {
  final String id;
  final String title;
  final String level;
  final String topic;
  final PLPPresentation presentation;
  final PLPPractice practice;
  final PLPProduction production;

  const PLPLesson({
    required this.id,
    required this.title,
    required this.level,
    required this.topic,
    required this.presentation,
    required this.practice,
    required this.production,
  });

  factory PLPLesson.fromJson(Map<String, dynamic> json) {
    return PLPLesson(
      id: json['id']?.toString() ?? '',
      title: json['title']?.toString() ?? 'Untitled Lesson',
      level: json['level']?.toString() ?? 'A1',
      topic: json['topic']?.toString() ?? '',
      presentation: PLPPresentation.fromJson(
          json['presentation'] as Map<String, dynamic>? ?? {}),
      practice:
          PLPPractice.fromJson(json['practice'] as Map<String, dynamic>? ?? {}),
      production: PLPProduction.fromJson(
          json['production'] as Map<String, dynamic>? ?? {}),
    );
  }
}

class PLPPresentation {
  final List<PLPVocabulary> vocabulary;
  final List<PLPGrammarPoint> grammarPoints;
  final List<String> exampleSentences;
  final String? culturalNotes;

  const PLPPresentation({
    required this.vocabulary,
    required this.grammarPoints,
    required this.exampleSentences,
    this.culturalNotes,
  });

  factory PLPPresentation.fromJson(Map<String, dynamic> json) {
    return PLPPresentation(
      vocabulary: (json['vocabulary'] as List?)
              ?.map((e) =>
                  PLPVocabulary.fromJson(e as Map<String, dynamic>? ?? {}))
              .toList() ??
          [],
      grammarPoints: (json['grammar_points'] as List?)
              ?.map((e) =>
                  PLPGrammarPoint.fromJson(e as Map<String, dynamic>? ?? {}))
              .toList() ??
          [],
      exampleSentences: (json['example_sentences'] as List?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      culturalNotes: json['cultural_notes']?.toString(),
    );
  }
}

class PLPVocabulary {
  final String word;
  final String definition;
  final String? arabicTranslation;
  final String? exampleSentence;
  final String? partOfSpeech;
  final String? audioUrl;

  const PLPVocabulary({
    required this.word,
    required this.definition,
    this.arabicTranslation,
    this.exampleSentence,
    this.partOfSpeech,
    this.audioUrl,
  });

  factory PLPVocabulary.fromJson(Map<String, dynamic> json) {
    return PLPVocabulary(
      word: json['word']?.toString() ?? '',
      definition: json['definition']?.toString() ?? '',
      arabicTranslation: json['arabic_translation']?.toString(),
      exampleSentence: json['example_sentence']?.toString(),
      partOfSpeech: json['part_of_speech']?.toString(),
      audioUrl: json['audio_url']?.toString(),
    );
  }
}

class PLPGrammarPoint {
  final String title;
  final String explanation;
  final String? formula;
  final List<String> examples;
  final List<String> commonMistakes;

  const PLPGrammarPoint({
    required this.title,
    required this.explanation,
    this.formula,
    required this.examples,
    required this.commonMistakes,
  });

  factory PLPGrammarPoint.fromJson(Map<String, dynamic> json) {
    return PLPGrammarPoint(
      title: json['title']?.toString() ?? '',
      explanation: json['explanation']?.toString() ?? '',
      formula: json['formula']?.toString(),
      examples: (json['examples'] as List?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      commonMistakes: (json['common_mistakes'] as List?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
    );
  }
}

class PLPPractice {
  final List<PLPExercise> exercises;

  const PLPPractice({required this.exercises});

  factory PLPPractice.fromJson(Map<String, dynamic> json) {
    return PLPPractice(
      exercises: (json['exercises'] as List?)
              ?.map((e) =>
                  PLPExercise.fromJson(e as Map<String, dynamic>? ?? {}))
              .toList() ??
          [],
    );
  }
}

class PLPExercise {
  final String id;
  final String type; // fill_blank, multiple_choice, reorder, match, correct_error
  final String instruction;
  final String question;
  final List<String>? options;
  final String correctAnswer;
  final String? hint;
  final String? explanation;

  const PLPExercise({
    required this.id,
    required this.type,
    required this.instruction,
    required this.question,
    this.options,
    required this.correctAnswer,
    this.hint,
    this.explanation,
  });

  factory PLPExercise.fromJson(Map<String, dynamic> json) {
    return PLPExercise(
      id: json['id']?.toString() ?? '',
      type: json['type']?.toString() ?? 'fill_blank',
      instruction: json['instruction']?.toString() ?? '',
      question: json['question']?.toString() ?? '',
      options: (json['options'] as List?)?.map((e) => e.toString()).toList(),
      correctAnswer: json['correct_answer']?.toString() ?? '',
      hint: json['hint']?.toString(),
      explanation: json['explanation']?.toString(),
    );
  }
}

class PLPProduction {
  final List<PLPProductionTask> tasks;

  const PLPProduction({required this.tasks});

  factory PLPProduction.fromJson(Map<String, dynamic> json) {
    return PLPProduction(
      tasks: (json['tasks'] as List?)
              ?.map((e) =>
                  PLPProductionTask.fromJson(e as Map<String, dynamic>? ?? {}))
              .toList() ??
          [],
    );
  }
}

class PLPProductionTask {
  final String id;
  final String type; // speaking, writing, discussion, role_play
  final String title;
  final String description;
  final List<String> prompts;
  final List<String> evaluationCriteria;
  final int? timeLimitMinutes;

  const PLPProductionTask({
    required this.id,
    required this.type,
    required this.title,
    required this.description,
    required this.prompts,
    required this.evaluationCriteria,
    this.timeLimitMinutes,
  });

  factory PLPProductionTask.fromJson(Map<String, dynamic> json) {
    return PLPProductionTask(
      id: json['id']?.toString() ?? '',
      type: json['type']?.toString() ?? 'writing',
      title: json['title']?.toString() ?? '',
      description: json['description']?.toString() ?? '',
      prompts: (json['prompts'] as List?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      evaluationCriteria: (json['evaluation_criteria'] as List?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      timeLimitMinutes: json['time_limit_minutes'] as int?,
    );
  }
}
