import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

import '../auth/auth_session_store.dart';

const _unchangedPracticeWordValue = Object();

class PracticeWordCandidate {
  final String word;
  final int score;

  const PracticeWordCandidate({required this.word, required this.score});
}

class PracticeWord {
  final String word;
  final String ipa;
  final int score;
  final String source;
  final DateTime addedAt;
  final DateTime? masteredAt;
  final int occurrences;
  final bool addedManually;

  const PracticeWord({
    required this.word,
    required this.ipa,
    required this.score,
    required this.source,
    required this.addedAt,
    this.masteredAt,
    required this.occurrences,
    required this.addedManually,
  });

  bool get isMastered => masteredAt != null;

  PracticeWord copyWith({
    int? score,
    String? source,
    DateTime? addedAt,
    Object? masteredAt = _unchangedPracticeWordValue,
    int? occurrences,
    bool? addedManually,
  }) {
    return PracticeWord(
      word: word,
      ipa: ipa,
      score: score ?? this.score,
      source: source ?? this.source,
      addedAt: addedAt ?? this.addedAt,
      masteredAt: identical(masteredAt, _unchangedPracticeWordValue)
          ? this.masteredAt
          : masteredAt as DateTime?,
      occurrences: occurrences ?? this.occurrences,
      addedManually: addedManually ?? this.addedManually,
    );
  }

  Map<String, dynamic> toJson() => {
    'word': word,
    'ipa': ipa,
    'score': score,
    'source': source,
    'added_at': addedAt.toIso8601String(),
    'mastered_at': masteredAt?.toIso8601String(),
    'occurrences': occurrences,
    'added_manually': addedManually,
  };

  factory PracticeWord.fromJson(Map<String, dynamic> json) {
    return PracticeWord(
      word: json['word']?.toString() ?? '',
      ipa: json['ipa']?.toString() ?? '',
      score: (json['score'] as num?)?.round().clamp(0, 100) ?? 0,
      source: json['source']?.toString() ?? 'Practice',
      addedAt:
          DateTime.tryParse(json['added_at']?.toString() ?? '') ??
          DateTime.now(),
      masteredAt: DateTime.tryParse(json['mastered_at']?.toString() ?? ''),
      occurrences: (json['occurrences'] as num?)?.round().clamp(1, 999) ?? 1,
      addedManually: json['added_manually'] == true,
    );
  }
}

class PracticeWordStore extends ChangeNotifier {
  PracticeWordStore._();

  static final PracticeWordStore instance = PracticeWordStore._();

  final List<PracticeWord> _words = [];
  Future<void>? _loadFuture;
  String? _loadedUserId;

  List<PracticeWord> get words {
    _activateCurrentUser();
    final result = List<PracticeWord>.from(_words);
    result.sort((a, b) {
      if (a.isMastered != b.isMastered) return a.isMastered ? 1 : -1;
      if (a.isMastered && b.isMastered) {
        final byMasteredAt = b.masteredAt!.compareTo(a.masteredAt!);
        if (byMasteredAt != 0) return byMasteredAt;
      }
      if (a.addedManually != b.addedManually) {
        return a.addedManually ? 1 : -1;
      }
      final byScore = a.score.compareTo(b.score);
      if (byScore != 0) return byScore;
      final byOccurrences = b.occurrences.compareTo(a.occurrences);
      if (byOccurrences != 0) return byOccurrences;
      return b.addedAt.compareTo(a.addedAt);
    });
    return List.unmodifiable(result);
  }

  Future<void> load() {
    _activateCurrentUser();
    return _loadFuture ??= _loadFromDisk();
  }

  void _activateCurrentUser() {
    final current = AuthSessionStore.instance.userId ?? 'anonymous';
    if (_loadedUserId == current) return;
    _loadedUserId = current;
    _words.clear();
    _loadFuture = null;
  }

  Future<void> _loadFromDisk() async {
    try {
      final file = await _storageFile();
      if (!await file.exists()) return;
      final decoded = jsonDecode(await file.readAsString());
      if (decoded is! List) return;
      _words
        ..clear()
        ..addAll(
          decoded
              .whereType<Map>()
              .map(
                (item) =>
                    PracticeWord.fromJson(Map<String, dynamic>.from(item)),
              )
              .where((item) => item.word.trim().isNotEmpty),
        );
      notifyListeners();
    } catch (_) {
      // The queue remains usable in memory if local storage is unavailable.
    }
  }

  Future<int> addRoleplayWords({
    required String scenario,
    required Iterable<PracticeWordCandidate> candidates,
  }) async {
    await load();
    final now = DateTime.now();
    var changed = 0;

    for (final candidate in candidates) {
      final word = _cleanWord(candidate.word);
      final score = candidate.score.clamp(0, 100);
      if (word.isEmpty || score >= 80) continue;

      final index = _words.indexWhere((item) => _key(item.word) == _key(word));
      if (index == -1) {
        _words.add(
          PracticeWord(
            word: word,
            ipa: '',
            score: score,
            source: '$scenario · recognition check',
            addedAt: now,
            occurrences: 1,
            addedManually: false,
          ),
        );
      } else {
        final existing = _words[index];
        _words[index] = existing.copyWith(
          score: score < existing.score ? score : existing.score,
          source: '$scenario · recognition check',
          addedAt: now,
          masteredAt: null,
          occurrences: existing.occurrences + 1,
          addedManually: false,
        );
      }
      changed += 1;
    }

    if (changed > 0) {
      notifyListeners();
      await _persist();
    }
    return changed;
  }

  Future<void> addManualWord(String value) async {
    await load();
    final word = _cleanWord(value);
    if (word.isEmpty) return;

    final index = _words.indexWhere((item) => _key(item.word) == _key(word));
    if (index == -1) {
      _words.add(
        PracticeWord(
          word: word,
          ipa: '',
          score: 0,
          source: 'Added by you',
          addedAt: DateTime.now(),
          occurrences: 1,
          addedManually: true,
        ),
      );
    }
    notifyListeners();
    await _persist();
  }

  Future<void> markMastered(PracticeWord word) async {
    await load();
    final index = _words.indexWhere(
      (item) => _key(item.word) == _key(word.word),
    );
    if (index == -1) return;
    _words[index] = _words[index].copyWith(masteredAt: DateTime.now());
    notifyListeners();
    await _persist();
  }

  Future<void> removeWord(PracticeWord word) async {
    await load();
    _words.removeWhere((item) => _key(item.word) == _key(word.word));
    notifyListeners();
    await _persist();
  }

  Future<void> clear() async {
    _activateCurrentUser();
    _words.clear();
    _loadFuture = Future<void>.value();
    notifyListeners();
    try {
      final file = await _storageFile().timeout(const Duration(seconds: 2));
      if (await file.exists()) await file.delete();
    } catch (_) {
      // The in-memory queue has still been cleared.
    }
  }

  Future<File> _storageFile() async {
    final directory = await getApplicationDocumentsDirectory();
    final owner = (_loadedUserId ?? 'anonymous').replaceAll(
      RegExp(r'[^a-zA-Z0-9_-]'),
      '_',
    );
    return File('${directory.path}/practice_words_$owner.json');
  }

  Future<void> _persist() async {
    try {
      final file = await _storageFile();
      await file.writeAsString(
        jsonEncode(_words.map((item) => item.toJson()).toList()),
        flush: true,
      );
    } catch (_) {
      // Keep the in-memory queue working if persistence fails.
    }
  }

  static String _cleanWord(String value) {
    return value.trim().replaceAll(RegExp(r"^[^A-Za-z']+|[^A-Za-z']+$"), '');
  }

  static String _key(String value) => value.trim().toLowerCase();
}
