// lib/core/services/api_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../auth/auth_session_store.dart';

class ApiService {
  static const String baseUrl = 'http://localhost:8000';
  static const String wsUrl = 'ws://localhost:8000';
  static const Duration _timeout = Duration(seconds: 30);
  static const Duration _longTimeout = Duration(seconds: 60);
  static const Duration _historyTimeout = Duration(seconds: 8);
  static final http.Client _client = AuthenticatedHttpClient();

  static Future<Map<String, dynamic>> signUp({
    required String displayName,
    required String email,
    required String password,
  }) async {
    final response = await _client
        .post(
          Uri.parse('$baseUrl/api/auth/signup'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'display_name': displayName,
            'email': email,
            'password': password,
          }),
        )
        .timeout(_timeout);
    if (response.statusCode != 201) {
      throw StateError(_errorDetail(response));
    }
    final payload = Map<String, dynamic>.from(jsonDecode(response.body) as Map);
    await AuthSessionStore.instance.setSession(payload);
    return payload;
  }

  static Future<Map<String, dynamic>> signIn({
    required String email,
    required String password,
  }) async {
    final response = await _client
        .post(
          Uri.parse('$baseUrl/api/auth/signin'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'email': email, 'password': password}),
        )
        .timeout(_timeout);
    if (response.statusCode != 200) {
      throw StateError(_errorDetail(response));
    }
    final payload = Map<String, dynamic>.from(jsonDecode(response.body) as Map);
    await AuthSessionStore.instance.setSession(payload);
    return payload;
  }

  static Future<Map<String, dynamic>> continueAsGuest() async {
    final response = await _client
        .post(
          Uri.parse('$baseUrl/api/auth/guest'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'display_name': 'Guest'}),
        )
        .timeout(_timeout);
    if (response.statusCode != 201) {
      throw StateError(_errorDetail(response));
    }
    final payload = Map<String, dynamic>.from(jsonDecode(response.body) as Map);
    await AuthSessionStore.instance.setSession(payload);
    return payload;
  }

  static Future<void> signOut() async {
    try {
      await _client
          .post(Uri.parse('$baseUrl/api/auth/signout'))
          .timeout(_timeout);
    } finally {
      await AuthSessionStore.instance.clear();
    }
  }

  static Future<List<Map<String, dynamic>>> getRoleplayScenarios() async {
    final response = await _client
        .get(Uri.parse('$baseUrl/api/roleplay/scenarios'))
        .timeout(_timeout);
    if (response.statusCode != 200) {
      throw StateError(_errorDetail(response));
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! List) {
      throw StateError('The roleplay catalog returned an invalid response.');
    }
    return decoded
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList(growable: false);
  }

  static Future<Map<String, dynamic>> createRoleplayScenario({
    required String category,
    required String icon,
    required String title,
    required String description,
    required String aiRole,
    required String learnerRole,
    required String opening,
    required List<Map<String, dynamic>> objectives,
    required List<String> targetLanguage,
    required List<Map<String, dynamic>> evaluationRubric,
    required String designedCefrLevel,
  }) async {
    final response = await _client
        .post(
          Uri.parse('$baseUrl/api/roleplay/scenarios'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'category': category,
            'icon': icon,
            'title': title,
            'description': description,
            'ai_role': aiRole,
            'learner_role': learnerRole,
            'opening': opening,
            'objectives': objectives,
            'target_language': targetLanguage,
            'evaluation_rubric': evaluationRubric,
            'designed_cefr_level': designedCefrLevel,
          }),
        )
        .timeout(_timeout);
    if (response.statusCode != 201 && response.statusCode != 200) {
      throw StateError(_errorDetail(response));
    }
    return Map<String, dynamic>.from(jsonDecode(response.body) as Map);
  }

  static Future<Map<String, dynamic>> generateRoleplayScenarioDraft({
    required String category,
    required String title,
    required String description,
  }) async {
    final response = await _client
        .post(
          Uri.parse('$baseUrl/api/roleplay/scenarios/draft'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'category': category,
            'title': title,
            'description': description,
          }),
        )
        .timeout(_longTimeout);
    if (response.statusCode != 200) {
      throw StateError(_errorDetail(response));
    }
    return Map<String, dynamic>.from(jsonDecode(response.body) as Map);
  }

  static Future<Map<String, dynamic>> startRoleplaySession({
    required String clientSessionId,
    required String scenarioId,
  }) async {
    final response = await _client
        .post(
          Uri.parse('$baseUrl/api/roleplay/sessions/start'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'client_session_id': clientSessionId,
            'scenario_id': scenarioId,
          }),
        )
        .timeout(_timeout);
    if (response.statusCode != 201 && response.statusCode != 200) {
      throw StateError(_errorDetail(response));
    }
    return Map<String, dynamic>.from(jsonDecode(response.body) as Map);
  }

  static Future<Map<String, dynamic>> finalizeRoleplaySession({
    required String clientSessionId,
    required String endedReason,
  }) async {
    final response = await _client
        .post(
          Uri.parse('$baseUrl/api/roleplay/sessions/$clientSessionId/finalize'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'ended_reason': endedReason}),
        )
        .timeout(_longTimeout);
    if (response.statusCode != 200) {
      throw StateError(_errorDetail(response));
    }
    return Map<String, dynamic>.from(jsonDecode(response.body) as Map);
  }

  static Future<Map<String, dynamic>> getArabicTranslationOptions({
    required String arabicText,
  }) async {
    final response = await _client
        .post(
          Uri.parse('$baseUrl/api/translation/arabic'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'text': arabicText}),
        )
        .timeout(_timeout);
    if (response.statusCode != 200) {
      throw StateError(_errorDetail(response));
    }
    return Map<String, dynamic>.from(jsonDecode(response.body) as Map);
  }

  static Future<List<Map<String, dynamic>>> getRoleplayHistory() async {
    final response = await _client
        .get(Uri.parse('$baseUrl/api/roleplay/sessions?limit=100'))
        .timeout(_historyTimeout);
    if (response.statusCode != 200) {
      throw StateError(_errorDetail(response));
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! List) return const [];
    return decoded
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList(growable: false);
  }

  static Future<Map<String, dynamic>> getRoleplayTranscript(
    String clientSessionId,
  ) async {
    final response = await _client
        .get(
          Uri.parse(
            '$baseUrl/api/roleplay/sessions/$clientSessionId/transcript',
          ),
        )
        .timeout(_historyTimeout);
    if (response.statusCode != 200) {
      throw StateError(_errorDetail(response));
    }
    return Map<String, dynamic>.from(jsonDecode(response.body) as Map);
  }

  // ── Grammar Check ─────────────────────────────────────────────
  /// POST /api/grammar/check
  /// Body: {"text": string}
  /// Returns: corrected_text, corrections list, is_correct
  static Future<Map<String, dynamic>> checkGrammar(String text) async {
    try {
      final response = await _client
          .post(
            Uri.parse('$baseUrl/api/grammar/check'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'text': text}),
          )
          .timeout(_timeout);
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      return {'error': 'Server error: ${response.statusCode}'};
    } catch (e) {
      return {'error': 'Connection failed. Is the backend running?\n$e'};
    }
  }

  // ── PLP: Generate Lesson ──────────────────────────────────────
  /// POST /api/plp/generate
  /// Body: {"topic": string, "level": string}
  static Future<Map<String, dynamic>> generatePLPLesson(
    String topic,
    String level,
  ) async {
    try {
      final response = await _client
          .post(
            Uri.parse('$baseUrl/api/plp/generate'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'topic': topic, 'level': level}),
          )
          .timeout(_longTimeout);
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      return {'error': 'Server error: ${response.statusCode}'};
    } catch (e) {
      return {'error': 'Connection failed: $e'};
    }
  }

  static Future<Map<String, dynamic>> saveLearnerProfile(
    Map<String, dynamic> profile,
  ) async {
    final response = await _client
        .put(
          Uri.parse('$baseUrl/api/learners/local/profile'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(profile),
        )
        .timeout(_timeout);
    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw StateError(_errorDetail(response));
  }

  static Future<Map<String, dynamic>> generateLearningPlan() async {
    final response = await _client
        .post(Uri.parse('$baseUrl/api/plp/generations'))
        .timeout(_timeout);
    if (response.statusCode == 200 || response.statusCode == 202) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw StateError(_errorDetail(response));
  }

  static String _errorDetail(http.Response response) {
    try {
      final payload = jsonDecode(response.body) as Map<String, dynamic>;
      return payload['detail']?.toString() ??
          'Server error: ${response.statusCode}';
    } catch (_) {
      return 'Server error: ${response.statusCode}';
    }
  }

  static Future<Map<String, dynamic>> getNews({
    required String category,
    required String level,
    int page = 1,
  }) async {
    final uri = Uri.parse('$baseUrl/api/news').replace(
      queryParameters: {'category': category, 'level': level, 'page': '$page'},
    );
    final response = await _client.get(uri).timeout(_longTimeout);
    if (response.statusCode == 200) {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) return decoded;
      throw StateError('The news service returned an invalid response.');
    }
    throw StateError(_errorDetail(response));
  }

  // ── PLP: List Lessons ─────────────────────────────────────────
  /// GET /api/plp/lessons
  static Future<List<dynamic>> getPLPLessons() async {
    try {
      final response = await _client
          .get(Uri.parse('$baseUrl/api/plp/lessons'))
          .timeout(_timeout);
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return (data['lessons'] as List?) ?? [];
      }
      return [];
    } catch (_) {
      return [];
    }
  }

  // ── PLP: Get Single Lesson ────────────────────────────────────
  /// GET /api/plp/lessons/{id}
  static Future<Map<String, dynamic>> getPLPLesson(String id) async {
    try {
      final response = await _client
          .get(Uri.parse('$baseUrl/api/plp/lessons/$id'))
          .timeout(_timeout);
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      return {'error': 'Server error: ${response.statusCode}'};
    } catch (e) {
      return {'error': 'Connection failed: $e'};
    }
  }

  // ── PLP: Check Exercise Answer ────────────────────────────────
  /// GET /api/plp/lessons/{lessonId}/exercise/{exerciseId}/check?answer=...
  static Future<Map<String, dynamic>> checkExerciseAnswer(
    String lessonId,
    String exerciseId,
    String answer,
  ) async {
    try {
      final uri = Uri.parse(
        '$baseUrl/api/plp/lessons/$lessonId/exercise/$exerciseId/check',
      ).replace(queryParameters: {'answer': answer});
      final response = await _client.get(uri).timeout(_timeout);
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      return {'error': 'Server error: ${response.statusCode}'};
    } catch (e) {
      return {'error': 'Connection failed: $e'};
    }
  }

  // ── PLP: Evaluate Production Task ─────────────────────────────
  /// POST /api/plp/lessons/{lessonId}/production/{taskId}/evaluate
  static Future<Map<String, dynamic>> evaluateProduction(
    String lessonId,
    String taskId,
    String content,
  ) async {
    try {
      final response = await _client
          .post(
            Uri.parse(
              '$baseUrl/api/plp/lessons/$lessonId/production/$taskId/evaluate',
            ),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'content': content}),
          )
          .timeout(const Duration(seconds: 45));
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      return {'error': 'Server error: ${response.statusCode}'};
    } catch (e) {
      return {'error': 'Connection failed: $e'};
    }
  }

  // ── Vocabulary Lookup ─────────────────────────────────────────
  /// POST /api/vocabulary/lookup
  static Future<Map<String, dynamic>> lookupWord(String word) async {
    try {
      final response = await _client
          .post(
            Uri.parse('$baseUrl/api/vocabulary/lookup'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'word': word}),
          )
          .timeout(_timeout);
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        if (decoded is Map<String, dynamic>) return decoded;
        return {'error': 'The dictionary returned an invalid response.'};
      }
      try {
        final decoded = jsonDecode(response.body);
        if (decoded is Map && decoded['detail'] != null) {
          return {'error': decoded['detail'].toString()};
        }
      } catch (_) {
        // Use the status-based message below for non-JSON failures.
      }
      return {'error': 'Dictionary lookup failed (${response.statusCode}).'};
    } catch (e) {
      return {'error': 'Connection failed: $e'};
    }
  }

  static Future<Map<String, dynamic>> getPronunciationGuide(
    String target,
  ) async {
    try {
      final uri = Uri.parse(
        '$baseUrl/api/pronunciation/guide',
      ).replace(queryParameters: {'text': target});
      final response = await _client.get(uri).timeout(_timeout);
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        if (decoded is Map<String, dynamic>) return decoded;
        return {'error': 'Pronunciation guide returned an invalid response.'};
      }
      return {'error': _errorDetail(response)};
    } catch (e) {
      return {'error': 'Could not load pronunciation guide: $e'};
    }
  }

  static Uri ttsUri(String text) =>
      Uri.parse('$baseUrl/api/tts').replace(queryParameters: {'text': text});

  // ── Pronunciation Check ────────────────────────────────────
  /// POST /api/pronunciation (multipart: target_word + audio file)
  static Future<Map<String, dynamic>> checkPronunciation(
    String targetWord,
    String audioFilePath, {
    String? activityId,
    String? attemptSessionId,
  }) async {
    try {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$baseUrl/api/pronunciation'),
      );
      final token = AuthSessionStore.instance.accessToken;
      if (token != null) {
        request.headers['Authorization'] = 'Bearer $token';
      }
      request.fields['target_word'] = targetWord;
      if (activityId != null) request.fields['activity_id'] = activityId;
      if (attemptSessionId != null) {
        request.fields['attempt_session_id'] = attemptSessionId;
      }
      request.files.add(
        await http.MultipartFile.fromPath('file', audioFilePath),
      );

      final streamedResponse = await request.send().timeout(_longTimeout);
      final body = await streamedResponse.stream.bytesToString();
      if (streamedResponse.statusCode == 200) {
        return jsonDecode(body) as Map<String, dynamic>;
      }
      try {
        final payload = jsonDecode(body) as Map<String, dynamic>;
        return {
          'error':
              payload['detail']?.toString() ??
              'Server error: ${streamedResponse.statusCode}',
          'status_code': streamedResponse.statusCode,
        };
      } catch (_) {
        return {'error': 'Server error: ${streamedResponse.statusCode}'};
      }
    } catch (e) {
      return {'error': 'Connection failed: $e'};
    }
  }
}
