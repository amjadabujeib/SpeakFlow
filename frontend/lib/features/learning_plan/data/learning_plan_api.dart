import '../../../core/network/api_client.dart';

class LearningPlanApi {
  final ApiClient _client;

  const LearningPlanApi(this._client);

  Future<JsonMap> loadProfile() async =>
      _client.decodeMap(await _client.get('/me/profile'));

  Future<JsonMap> loadPlan() async =>
      _client.decodeMap(await _client.get('/learning-plan/active'));

  Future<JsonMap> saveProfile(JsonMap profile) async =>
      _client.decodeMap(await _client.put('/me/profile', body: profile));

  Future<JsonMap> generate() async => _client.decodeMap(
    await _client.post('/learning-plan/generations'),
    successStatuses: const {200, 202},
  );

  Future<JsonMap> generationStatus(String jobId) async =>
      _client.decodeMap(await _client.get('/learning-plan/generations/$jobId'));

  Future<JsonMap> latestGeneration() async =>
      _client.decodeMap(await _client.get('/learning-plan/generations/latest'));

  Future<JsonMap> retryGeneration(String jobId) async => _client.decodeMap(
    await _client.post('/learning-plan/generations/$jobId/retry'),
  );

  Future<void> resetLearner() async {
    _client.decodeMap(await _client.delete('/me/learning-data'));
  }

  Future<JsonMap> submitAttempt(String activityId, JsonMap response) async =>
      _client.decodeMap(
        await _client.post(
          '/learning-plan/activities/$activityId/attempts',
          body: response,
        ),
      );
}
