// lib/core/providers/app_state.dart
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

class AppState extends ChangeNotifier {
  static final AppState _instance = AppState._internal();
  factory AppState() => _instance;
  AppState._internal();
  Future<void> _preferenceWrite = Future<void>.value();

  // Font size (settings slider)
  double _fontSize = 1.0; // scale factor
  double get fontSize => _fontSize;
  void setFontSize(double value) {
    final normalized = value.clamp(0.85, 1.3).toDouble();
    if (_fontSize == normalized) return;
    _fontSize = normalized;
    notifyListeners();
    _schedulePreferenceWrite();
  }

  // Mother tongue
  String _motherTongue = 'Arabic';
  String get motherTongue => _motherTongue;
  void setMotherTongue(String lang) {
    if (_motherTongue == lang) return;
    _motherTongue = lang;
    notifyListeners();
  }

  // CEFR level
  String _cefrLevel = 'B1';
  String get cefrLevel => _cefrLevel;
  void setCefrLevel(String level) {
    if (_cefrLevel == level) return;
    _cefrLevel = level;
    notifyListeners();
  }

  // Interests
  List<String> _interests = ['Travel', 'Technology', 'Food & Cooking'];
  List<String> get interests => List.unmodifiable(_interests);
  void setInterests(List<String> items) {
    if (listEquals(_interests, items)) return;
    _interests = List.unmodifiable(items);
    notifyListeners();
  }

  int _planRefreshToken = 0;
  int get planRefreshToken => _planRefreshToken;
  String? _pendingGenerationJobId;
  String? get pendingGenerationJobId => _pendingGenerationJobId;

  void trackPlanGeneration(String jobId) {
    if (_pendingGenerationJobId == jobId) return;
    _pendingGenerationJobId = jobId;
    notifyListeners();
  }

  void clearTrackedPlanGeneration([String? jobId]) {
    if (jobId != null && _pendingGenerationJobId != jobId) return;
    if (_pendingGenerationJobId == null) return;
    _pendingGenerationJobId = null;
    notifyListeners();
  }

  void requestPlanRefresh() {
    _planRefreshToken++;
    notifyListeners();
  }

  void resetLearnerState() {
    _motherTongue = 'Arabic';
    _cefrLevel = 'B1';
    _interests = ['Travel', 'Technology', 'Food & Cooking'];
    _pendingGenerationJobId = null;
    _planRefreshToken++;
    notifyListeners();
  }

  Future<void> restorePreferences() async {
    try {
      final file = await _preferencesFile();
      if (!await file.exists()) return;
      final decoded = jsonDecode(await file.readAsString());
      if (decoded is! Map) return;
      final fontSize = decoded['font_size'];
      if (fontSize is num && fontSize >= 0.85 && fontSize <= 1.3) {
        _fontSize = fontSize.toDouble();
      }
    } catch (_) {
      // Defaults remain usable if device preference storage is unavailable.
    }
  }

  Future<void> _persistPreferences() async {
    try {
      final file = await _preferencesFile();
      final temporary = File('${file.path}.tmp');
      await temporary.writeAsString(
        jsonEncode({'font_size': _fontSize}),
        flush: true,
      );
      await temporary.rename(file.path);
    } catch (_) {
      // UI preference persistence is best effort.
    }
  }

  void _schedulePreferenceWrite() {
    _preferenceWrite = _preferenceWrite.then((_) => _persistPreferences());
    unawaited(_preferenceWrite);
  }

  Future<File> _preferencesFile() async {
    final directory = await getApplicationDocumentsDirectory();
    return File('${directory.path}/app_preferences.json');
  }
}
