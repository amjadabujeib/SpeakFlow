// lib/core/providers/app_state.dart
import 'package:flutter/material.dart';

class AppState extends ChangeNotifier {
  static final AppState _instance = AppState._internal();
  factory AppState() => _instance;
  AppState._internal();

  // Theme
  bool _isDarkMode = true;
  bool get isDarkMode => _isDarkMode;
  void toggleTheme() {
    _isDarkMode = !_isDarkMode;
    notifyListeners();
  }

  // Font size (settings slider)
  double _fontSize = 1.0; // scale factor
  double get fontSize => _fontSize;
  void setFontSize(double value) {
    _fontSize = value;
    notifyListeners();
  }

  // Mother tongue
  String _motherTongue = 'Arabic';
  String get motherTongue => _motherTongue;
  void setMotherTongue(String lang) {
    _motherTongue = lang;
    notifyListeners();
  }

  // CEFR level
  String _cefrLevel = 'B1';
  String get cefrLevel => _cefrLevel;
  void setCefrLevel(String level) {
    _cefrLevel = level;
    notifyListeners();
  }

  // Interests
  List<String> _interests = ['Travel', 'Technology', 'Food & Cooking'];
  List<String> get interests => _interests;
  void setInterests(List<String> items) {
    _interests = items;
    notifyListeners();
  }

  int _planRefreshToken = 0;
  int get planRefreshToken => _planRefreshToken;
  void requestPlanRefresh() {
    _planRefreshToken++;
    notifyListeners();
  }

  // Onboarding
  bool _onboardingComplete = false;
  bool get onboardingComplete => _onboardingComplete;
  void completeOnboarding() {
    _onboardingComplete = true;
    notifyListeners();
  }

  // Nav tab
  int _currentTab = 0;
  int get currentTab => _currentTab;
  void setTab(int index) {
    _currentTab = index;
    notifyListeners();
  }

  // Playing news article
  String? _playingArticleId;
  String? get playingArticleId => _playingArticleId;
  void playArticle(String id) {
    _playingArticleId = id;
    notifyListeners();
  }

  void stopArticle() {
    _playingArticleId = null;
    notifyListeners();
  }

  // Translations toggled per message
  final Set<String> _translatedMessages = {};
  bool isTranslated(String id) => _translatedMessages.contains(id);
  void toggleTranslation(String id) {
    if (_translatedMessages.contains(id)) {
      _translatedMessages.remove(id);
    } else {
      _translatedMessages.add(id);
    }
    notifyListeners();
  }
}
