import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;

import '../core/network/api_client.dart' show ApiClient, ApiException;
import '../core/network/api_config.dart';
import '../features/learning_plan/data/learning_plan_api.dart';
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
  final LearningPlanApi _api;

  HttpPlpRepository({this.baseUrl = defaultBaseUrl, http.Client? client})
    : _api = LearningPlanApi(
        ApiClient(
          httpClient: client,
          endpoints: ApiEndpoints(
            origin: baseUrl,
            websocketOrigin: baseUrl.replaceFirst('http', 'ws'),
          ),
        ),
      );

  @override
  bool get isRemote => true;

  @override
  Future<JsonMap> loadProfile() => _translate(_api.loadProfile);

  @override
  Future<PlpDocument> loadPlan() => _translate(() async {
    final json = await _api.loadPlan();
    return PlpDocument.fromJson(json);
  });

  @override
  Future<JsonMap> saveProfile(JsonMap profile) =>
      _translate(() => _api.saveProfile(profile));

  @override
  Future<String> generatePlan() => _translate(() async {
    final json = await _api.generate();
    final jobId = json['job_id'];
    if (jobId is! String) {
      throw const PlpFormatException(
        'generation response must include a job_id',
      );
    }
    return jobId;
  });

  @override
  Future<JsonMap> generationStatus(String jobId) =>
      _translate(() => _api.generationStatus(jobId));

  @override
  Future<JsonMap> latestGeneration() => _translate(_api.latestGeneration);

  @override
  Future<JsonMap> retryGeneration(String jobId) =>
      _translate(() => _api.retryGeneration(jobId));

  @override
  Future<void> resetLearner() => _translate(_api.resetLearner);

  @override
  Future<PlpAttemptResult> submitAttempt(String activityId, JsonMap response) =>
      _translate(() async {
        final json = await _api.submitAttempt(activityId, response);
        return PlpAttemptResult.fromJson(json);
      });

  Future<T> _translate<T>(Future<T> Function() request) async {
    try {
      return await request();
    } on ApiException catch (error) {
      final statusCode = error.statusCode;
      if (statusCode == null) {
        throw PlpFormatException(error.message);
      }
      throw PlpApiException(statusCode, error.message);
    }
  }
}
