import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;

import '../core/auth/auth_session_store.dart';
import 'plp_models.dart';

abstract class PlpRepository {
  const PlpRepository();

  Future<PlpDocument> loadPlan();

  bool get isRemote => false;

  Future<JsonMap> loadProfile() =>
      throw UnsupportedError('This PLP repository does not persist profiles.');

  Future<JsonMap> saveProfile(JsonMap profile) =>
      throw UnsupportedError('This PLP repository does not persist profiles.');

  Future<String> generatePlan() =>
      throw UnsupportedError('This PLP repository does not generate plans.');

  Future<JsonMap> generationStatus(String jobId) =>
      throw UnsupportedError('This PLP repository has no generation jobs.');

  Future<JsonMap> latestGeneration() =>
      throw UnsupportedError('This PLP repository has no generation jobs.');

  Future<JsonMap> retryGeneration(String jobId) =>
      throw UnsupportedError('This PLP repository cannot retry generation.');

  Future<void> resetLearner() =>
      throw UnsupportedError('This PLP repository cannot reset learner data.');

  Future<PlpAttemptResult> submitAttempt(String activityId, JsonMap response) =>
      throw UnsupportedError('This PLP repository does not grade attempts.');
}

class AssetPlpRepository extends PlpRepository {
  static const defaultAssetPath = 'assets/mock/plp_plan_v1.json';

  final AssetBundle? bundle;
  final String assetPath;

  const AssetPlpRepository({this.bundle, this.assetPath = defaultAssetPath});

  @override
  Future<PlpDocument> loadPlan() async {
    final source = await (bundle ?? rootBundle).loadString(assetPath);
    final decoded = jsonDecode(source);
    if (decoded is! Map<String, dynamic>) {
      throw const PlpFormatException('document root must be a JSON object');
    }
    return PlpDocument.fromJson(decoded);
  }
}

class PlpApiException implements Exception {
  final int statusCode;
  final String message;

  const PlpApiException(this.statusCode, this.message);

  @override
  String toString() => message;
}

class PlpAttemptResult {
  final bool? correct;
  final int score;
  final String explanation;
  final JsonMap? correctResponse;
  final bool firstAttempt;
  final bool masteryEvidenceRecorded;
  final bool lessonCompleted;
  final int? lessonScore;
  final bool newlyCompleted;
  final int xpAwarded;
  final Set<String> completedActivityIds;

  const PlpAttemptResult({
    required this.correct,
    required this.score,
    required this.explanation,
    required this.correctResponse,
    required this.firstAttempt,
    required this.masteryEvidenceRecorded,
    required this.lessonCompleted,
    this.lessonScore,
    this.newlyCompleted = false,
    this.xpAwarded = 0,
    this.completedActivityIds = const {},
  });

  factory PlpAttemptResult.fromJson(JsonMap json) => PlpAttemptResult(
    correct: json['correct'] as bool?,
    score: json['score'] as int,
    explanation: json['explanation'] as String,
    correctResponse: json['correct_response'] is JsonMap
        ? json['correct_response'] as JsonMap
        : null,
    firstAttempt: json['first_attempt'] as bool? ?? true,
    masteryEvidenceRecorded:
        json['mastery_evidence_recorded'] as bool? ?? false,
    lessonCompleted: json['lesson_completed'] as bool? ?? false,
    lessonScore: json['lesson_score'] as int?,
    newlyCompleted: json['newly_completed'] as bool? ?? false,
    xpAwarded: json['xp_awarded'] as int? ?? 0,
    completedActivityIds:
        ((json['lesson_progress'] as JsonMap?)?['completed_activity_ids']
                    as List<dynamic>? ??
                const [])
            .map((item) => item.toString())
            .toSet(),
  );
}

class HttpPlpRepository extends PlpRepository {
  static const defaultBaseUrl = 'http://127.0.0.1:8000';
  final String baseUrl;
  final http.Client _client;

  HttpPlpRepository({this.baseUrl = defaultBaseUrl, http.Client? client})
    : _client = client ?? AuthenticatedHttpClient();

  @override
  bool get isRemote => true;

  @override
  Future<JsonMap> loadProfile() async => _decode(
    await _client.get(Uri.parse('$baseUrl/api/learners/local/profile')),
  );

  @override
  Future<PlpDocument> loadPlan() async {
    final response = await _client.get(Uri.parse('$baseUrl/api/plp/active'));
    final json = _decode(response);
    return PlpDocument.fromJson(json);
  }

  @override
  Future<JsonMap> saveProfile(JsonMap profile) async => _decode(
    await _client.put(
      Uri.parse('$baseUrl/api/learners/local/profile'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode(profile),
    ),
  );

  @override
  Future<String> generatePlan() async {
    final json = _decode(
      await _client.post(Uri.parse('$baseUrl/api/plp/generations')),
    );
    return json['job_id'] as String;
  }

  @override
  Future<JsonMap> generationStatus(String jobId) async => _decode(
    await _client.get(Uri.parse('$baseUrl/api/plp/generations/$jobId')),
  );

  @override
  Future<JsonMap> latestGeneration() async => _decode(
    await _client.get(Uri.parse('$baseUrl/api/plp/generations/latest')),
  );

  @override
  Future<JsonMap> retryGeneration(String jobId) async => _decode(
    await _client.post(Uri.parse('$baseUrl/api/plp/generations/$jobId/retry')),
  );

  @override
  Future<void> resetLearner() async {
    _decode(await _client.delete(Uri.parse('$baseUrl/api/learners/local')));
  }

  @override
  Future<PlpAttemptResult> submitAttempt(
    String activityId,
    JsonMap response,
  ) async => PlpAttemptResult.fromJson(
    _decode(
      await _client.post(
        Uri.parse('$baseUrl/api/plp/activities/$activityId/attempts'),
        headers: const {'Content-Type': 'application/json'},
        body: jsonEncode(response),
      ),
    ),
  );

  JsonMap _decode(http.Response response) {
    dynamic decoded;
    try {
      decoded = jsonDecode(response.body);
    } catch (_) {
      decoded = null;
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = decoded is Map<String, dynamic>
          ? decoded['detail']?.toString()
          : null;
      throw PlpApiException(
        response.statusCode,
        detail ?? 'PLP request failed (${response.statusCode}).',
      );
    }
    if (decoded is! Map<String, dynamic>) {
      throw const PlpFormatException('backend response must be a JSON object');
    }
    return decoded;
  }
}
