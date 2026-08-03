part of 'plp_models.dart';

void _validateActivity(PlpActivityType type, JsonMap data, String path) {
  switch (type) {
    case PlpActivityType.vocabularyCard:
      _requiredString(data, 'word', path);
      _requiredString(data, 'part_of_speech', path);
      _requiredString(data, 'ipa', path);
      _requiredString(data, 'definition', path);
      _requiredStringList(data, 'examples', path);
      _requiredStringList(data, 'collocations', path, allowEmpty: true);
    case PlpActivityType.concept:
      _optionalString(data, 'title', path);
      _requiredString(data, 'explanation', path);
      _requiredStringList(data, 'key_points', path);
      _requiredStringList(data, 'examples', path);
    case PlpActivityType.pronunciationDrill:
      if (data['title'] == null && data['sound_label'] == null) {
        throw PlpFormatException('$path needs title or sound_label');
      }
      if (data['target_ipa'] == null && data['ipa'] == null) {
        throw PlpFormatException('$path needs target_ipa or ipa');
      }
      _requiredString(data, 'instructions', path);
      _requiredStringList(data, 'tips', path);
      final rawItems = data['practice_items'];
      if (rawItems is! List || rawItems.length < 2) {
        throw PlpFormatException(
          '$path.practice_items must have 2 or more items',
        );
      }
    case PlpActivityType.multipleChoice:
      _requiredString(data, 'prompt', path);
      final options = _requiredMapList(data, 'options', path);
      if (options.length < 2) {
        throw PlpFormatException('$path.options must contain at least 2 items');
      }
      final optionIds = <String>{};
      for (final option in options) {
        final optionId = _requiredString(option, 'id', '$path.options');
        _requiredString(option, 'text', '$path.options');
        if (!optionIds.add(optionId)) {
          throw PlpFormatException(
            '$path contains duplicate option id $optionId',
          );
        }
      }
      final correctId = _optionalString(data, 'correct_option_id', path);
      if (correctId != null && !optionIds.contains(correctId)) {
        throw PlpFormatException('$path.correct_option_id is not an option');
      }
      _requiredString(data, 'explanation', path);
    case PlpActivityType.fillBlank:
      _requiredString(data, 'prompt', path);
      if (data.containsKey('accepted_answers')) {
        _requiredStringList(data, 'accepted_answers', path);
      }
      _requiredString(data, 'explanation', path);
    case PlpActivityType.readingComprehension:
      _requiredString(data, 'title', path);
      _requiredString(data, 'passage', path);
      _validateNestedQuestion(data, path);
    case PlpActivityType.listeningComprehension:
      _requiredString(data, 'title', path);
      _validateNestedQuestion(data, path);
    case PlpActivityType.sentenceOrder:
      _requiredString(data, 'prompt', path);
      final tokens = _requiredMapList(data, 'tokens', path);
      if (tokens.length < 2) {
        throw PlpFormatException('$path.tokens must contain at least 2 items');
      }
      for (final token in tokens) {
        _requiredString(token, 'id', '$path.tokens');
        _requiredString(token, 'text', '$path.tokens');
      }
      _requiredString(data, 'explanation', path);
    case PlpActivityType.guidedSpeaking:
      _requiredString(data, 'prompt', path);
      _requiredStringList(data, 'target_expressions', path);
      _requiredString(data, 'preparation_tip', path);
      _requiredInt(data, 'minimum_seconds', path);
  }
}

void _validateNestedQuestion(JsonMap data, String path) {
  final question = _requiredMap(data, 'question', path);
  _requiredString(question, 'prompt', '$path.question');
  final options = _requiredMapList(question, 'options', '$path.question');
  if (options.length < 2) {
    throw PlpFormatException('$path.question.options needs at least 2 items');
  }
  for (final option in options) {
    _requiredString(option, 'id', '$path.question.options');
    _requiredString(option, 'text', '$path.question.options');
  }
  _requiredString(question, 'explanation', '$path.question');
}

void _addUniqueId(Set<String> ids, String id, String kind) {
  if (!ids.add(id)) {
    throw PlpFormatException('duplicate $kind id $id');
  }
}

String _requiredString(JsonMap json, String key, String path) {
  final value = json[key];
  if (value is! String || value.trim().isEmpty) {
    throw PlpFormatException('$path.$key must be a non-empty string');
  }
  return value.trim();
}

String? _optionalString(JsonMap json, String key, String path) {
  final value = json[key];
  if (value == null) return null;
  if (value is! String || value.trim().isEmpty) {
    throw PlpFormatException('$path.$key must be null or a non-empty string');
  }
  return value.trim();
}

int _requiredInt(JsonMap json, String key, String path) {
  final value = json[key];
  if (value is! int) {
    throw PlpFormatException('$path.$key must be an integer');
  }
  return value;
}

int? _optionalInt(JsonMap json, String key, String path) {
  final value = json[key];
  if (value == null) return null;
  if (value is! int) {
    throw PlpFormatException('$path.$key must be null or an integer');
  }
  return value;
}

bool _requiredBool(JsonMap json, String key, String path) {
  final value = json[key];
  if (value is! bool) {
    throw PlpFormatException('$path.$key must be a boolean');
  }
  return value;
}

num _requiredNumber(JsonMap json, String key, String path) {
  final value = json[key];
  if (value is! num) {
    throw PlpFormatException('$path.$key must be numeric');
  }
  return value;
}

JsonMap _requiredMap(JsonMap json, String key, String path) {
  final value = json[key];
  if (value is! Map<String, dynamic>) {
    throw PlpFormatException('$path.$key must be an object');
  }
  return value;
}

List<JsonMap> _requiredMapList(JsonMap json, String key, String path) {
  final value = json[key];
  if (value is! List) {
    throw PlpFormatException('$path.$key must be an array');
  }
  final result = <JsonMap>[];
  for (final item in value) {
    if (item is! Map<String, dynamic>) {
      throw PlpFormatException('$path.$key must contain only objects');
    }
    result.add(item);
  }
  return result;
}

List<String> _requiredStringList(
  JsonMap json,
  String key,
  String path, {
  bool allowEmpty = false,
}) {
  final value = json[key];
  if (value is! List || value.any((item) => item is! String)) {
    throw PlpFormatException('$path.$key must be an array of strings');
  }
  final result = value
      .cast<String>()
      .map((item) => item.trim())
      .toList(growable: false);
  if (result.any((item) => item.isEmpty) || (!allowEmpty && result.isEmpty)) {
    throw PlpFormatException('$path.$key contains no usable values');
  }
  return result;
}

List<String> _optionalStringList(JsonMap json, String key, String path) {
  if (!json.containsKey(key)) return const [];
  return _requiredStringList(json, key, path, allowEmpty: true);
}
