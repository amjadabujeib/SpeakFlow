import '../../../core/network/api_client.dart';

class RoleplayApi {
  final ApiClient _client;

  const RoleplayApi(this._client);

  Future<List<JsonMap>> scenarios() async =>
      _client.decodeMapList(await _client.get('/roleplay/scenarios'));

  Future<JsonMap> createScenario({
    required String category,
    required String icon,
    required String title,
    required String description,
    required String aiRole,
    required String learnerRole,
    required String opening,
    required List<JsonMap> objectives,
    required List<String> targetLanguage,
    required List<JsonMap> evaluationRubric,
    required String designedCefrLevel,
  }) async => _client.decodeMap(
    await _client.post(
      '/roleplay/scenarios',
      body: {
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
      },
    ),
    successStatuses: const {200, 201},
  );

  Future<JsonMap> generateScenarioDraft({
    required String category,
    required String title,
    required String description,
  }) async => _client.decodeMap(
    await _client.post(
      '/roleplay/scenarios/draft',
      body: {'category': category, 'title': title, 'description': description},
      requestTimeout: ApiClient.longTimeout,
    ),
  );

  Future<JsonMap> startSession({
    required String clientSessionId,
    required String scenarioId,
  }) async => _client.decodeMap(
    await _client.post(
      '/roleplay/sessions/start',
      body: {'client_session_id': clientSessionId, 'scenario_id': scenarioId},
    ),
    successStatuses: const {200, 201},
  );

  Future<JsonMap> finalizeSession({
    required String clientSessionId,
    required String endedReason,
  }) async => _client.decodeMap(
    await _client.post(
      '/roleplay/sessions/$clientSessionId/finalize',
      body: {'ended_reason': endedReason},
      requestTimeout: ApiClient.longTimeout,
    ),
  );

  Future<JsonMap> arabicTranslationOptions(String arabicText) async =>
      _client.decodeMap(
        await _client.post('/translation/arabic', body: {'text': arabicText}),
      );

  Future<List<JsonMap>> history() async => _client.decodeMapList(
    await _client.get(
      '/roleplay/sessions',
      query: const {'limit': '100'},
      requestTimeout: ApiClient.historyTimeout,
    ),
  );

  Future<JsonMap> transcript(String clientSessionId) async => _client.decodeMap(
    await _client.get(
      '/roleplay/sessions/$clientSessionId/transcript',
      requestTimeout: ApiClient.historyTimeout,
    ),
  );
}
