// lib/core/services/api_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = 'http://localhost:8000';
  static const String wsUrl = 'ws://localhost:8000';
  static const Duration _timeout = Duration(seconds: 30);
  static const Duration _longTimeout = Duration(seconds: 60);

  // ── Grammar Check ─────────────────────────────────────────────
  /// POST /api/grammar/check
  /// Body: {"text": string}
  /// Returns: corrected_text, corrections list, is_correct
  static Future<Map<String, dynamic>> checkGrammar(String text) async {
    try {
      final response = await http
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
      String topic, String level) async {
    try {
      final response = await http
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

  // ── PLP: List Lessons ─────────────────────────────────────────
  /// GET /api/plp/lessons
  static Future<List<dynamic>> getPLPLessons() async {
    try {
      final response = await http
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
      final response = await http
          .get(Uri.parse('$baseUrl/api/plp/lessons/$id'))
          .timeout(_timeout);
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      return {'error': 'Not found'};
    } catch (e) {
      return {'error': 'Connection failed: $e'};
    }
  }

  // ── PLP: Check Exercise Answer ────────────────────────────────
  /// GET /api/plp/lessons/{lessonId}/exercise/{exerciseId}/check?answer=...
  static Future<Map<String, dynamic>> checkExerciseAnswer(
      String lessonId, String exerciseId, String answer) async {
    try {
      final uri = Uri.parse(
              '$baseUrl/api/plp/lessons/$lessonId/exercise/$exerciseId/check')
          .replace(queryParameters: {'answer': answer});
      final response = await http.get(uri).timeout(_timeout);
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
      String lessonId, String taskId, String content) async {
    try {
      final response = await http
          .post(
            Uri.parse(
                '$baseUrl/api/plp/lessons/$lessonId/production/$taskId/evaluate'),
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
      final response = await http
          .post(
            Uri.parse('$baseUrl/api/vocabulary/lookup'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'word': word}),
          )
          .timeout(_timeout);
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      return {'error': 'Not found'};
    } catch (e) {
      return {'error': 'Connection failed: $e'};
    }
  }
}
