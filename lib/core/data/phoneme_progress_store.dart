import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

import '../auth/auth_session_store.dart';

class PhonemeProgress {
  final String symbol;
  final int score;
  final int observations;
  final DateTime lastPracticedAt;

  const PhonemeProgress({
    required this.symbol,
    required this.score,
    required this.observations,
    required this.lastPracticedAt,
  });

  Map<String, dynamic> toJson() => {
    'symbol': symbol,
    'score': score,
    'observations': observations,
    'last_practiced_at': lastPracticedAt.toIso8601String(),
  };

  factory PhonemeProgress.fromJson(Map<String, dynamic> json) {
    return PhonemeProgress(
      symbol: json['symbol']?.toString().trim() ?? '',
      score: (json['score'] as num?)?.round().clamp(0, 100) ?? 0,
      observations:
          (json['observations'] as num?)?.round().clamp(1, 100000) ?? 1,
      lastPracticedAt:
          DateTime.tryParse(json['last_practiced_at']?.toString() ?? '') ??
          DateTime.now(),
    );
  }
}

class PhonemeProgressStore extends ChangeNotifier {
  PhonemeProgressStore._();

  static final PhonemeProgressStore instance = PhonemeProgressStore._();

  final Map<String, PhonemeProgress> _entries = {};
  Future<void>? _loadFuture;
  String? _loadedUserId;

  List<PhonemeProgress> get entries {
    _activateCurrentUser();
    final result = _entries.values.toList()
      ..sort((a, b) {
        final byScore = a.score.compareTo(b.score);
        return byScore != 0 ? byScore : a.symbol.compareTo(b.symbol);
      });
    return List.unmodifiable(result);
  }

  int get observationCount {
    _activateCurrentUser();
    return _entries.values.fold(0, (total, item) => total + item.observations);
  }

  Future<void> load() {
    _activateCurrentUser();
    return _loadFuture ??= _loadFromDisk();
  }

  void _activateCurrentUser() {
    final current = AuthSessionStore.instance.userId ?? 'anonymous';
    if (_loadedUserId == current) return;
    _loadedUserId = current;
    _entries.clear();
    _loadFuture = null;
  }

  Future<int> recordAnalysis(List<dynamic> analysis) async {
    await load();
    var recorded = 0;
    final now = DateTime.now();
    for (final raw in analysis.whereType<Map>()) {
      final item = Map<String, dynamic>.from(raw);
      final status = item['status']?.toString();
      final rawScore = item['score'];
      final score = rawScore is num ? rawScore.toDouble() : null;
      final symbol = _normalizeSymbol(item['char']?.toString() ?? '');
      if (status == 'omitted' ||
          symbol.isEmpty ||
          score == null ||
          !score.isFinite ||
          score < 0 ||
          score > 100) {
        continue;
      }
      final rounded = score.round();
      final previous = _entries[symbol];
      final observations = (previous?.observations ?? 0) + 1;
      final average = previous == null
          ? rounded
          : ((previous.score * previous.observations + rounded) / observations)
                .round();
      _entries[symbol] = PhonemeProgress(
        symbol: symbol,
        score: average,
        observations: observations,
        lastPracticedAt: now,
      );
      recorded += 1;
    }
    if (recorded > 0) {
      notifyListeners();
      await _persist();
    }
    return recorded;
  }

  Future<void> clear() async {
    _activateCurrentUser();
    _entries.clear();
    _loadFuture = Future<void>.value();
    notifyListeners();
    try {
      final file = await _storageFile().timeout(const Duration(seconds: 2));
      if (await file.exists()) await file.delete();
    } catch (_) {
      // The in-memory map has still been cleared.
    }
  }

  Future<void> _loadFromDisk() async {
    try {
      final file = await _storageFile();
      if (!await file.exists()) return;
      final decoded = jsonDecode(await file.readAsString());
      if (decoded is! List) return;
      _entries
        ..clear()
        ..addEntries(
          decoded
              .whereType<Map>()
              .map(
                (item) =>
                    PhonemeProgress.fromJson(Map<String, dynamic>.from(item)),
              )
              .where((item) => item.symbol.isNotEmpty)
              .map((item) => MapEntry(item.symbol, item)),
        );
      notifyListeners();
    } catch (_) {
      // The feature remains usable in memory if device storage is unavailable.
    }
  }

  Future<void> _persist() async {
    try {
      final file = await _storageFile();
      await file.writeAsString(
        jsonEncode(_entries.values.map((item) => item.toJson()).toList()),
        flush: true,
      );
    } catch (_) {
      // A storage failure must not invalidate a pronunciation result.
    }
  }

  Future<File> _storageFile() async {
    final directory = await getApplicationDocumentsDirectory();
    final owner = (_loadedUserId ?? 'anonymous').replaceAll(
      RegExp(r'[^a-zA-Z0-9_-]'),
      '_',
    );
    return File('${directory.path}/phoneme_progress_$owner.json');
  }

  String _normalizeSymbol(String value) {
    return value.trim().replaceAll('ˈ', '').replaceAll('ˌ', '');
  }
}
