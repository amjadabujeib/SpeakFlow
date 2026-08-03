import '../../../core/network/api_client.dart';

class LearningPlanApi {
  final ApiClient _client;

  const LearningPlanApi(this._client);

  Future<JsonMap> loadProfile() async =>
      _client.decodeMap(await _client.get('/learners/local/profile'));

  Future<JsonMap> loadPlan() async =>
      _client.decodeMap(await _client.get('/plp/active'));

  Future<JsonMap> saveProfile(JsonMap profile) async => _client.decodeMap(
    await _client.put('/learners/local/profile', body: profile),
  );

  Future<JsonMap> generate() async => _client.decodeMap(
    await _client.post('/plp/generations'),
    successStatuses: const {200, 202},
  );

  Future<JsonMap> generationStatus(String jobId) async =>
      _client.decodeMap(await _client.get('/plp/generations/$jobId'));

  Future<JsonMap> latestGeneration() async =>
      _client.decodeMap(await _client.get('/plp/generations/latest'));

  Future<JsonMap> retryGeneration(String jobId) async =>
      _client.decodeMap(await _client.post('/plp/generations/$jobId/retry'));

  Future<void> resetLearner() async {
    _client.decodeMap(await _client.delete('/learners/local'));
  }

  Future<JsonMap> submitAttempt(String activityId, JsonMap response) async =>
      _client.decodeMap(
        await _client.post(
          '/plp/activities/$activityId/attempts',
          body: response,
        ),
      );
}
