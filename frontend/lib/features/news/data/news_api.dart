import '../../../core/network/api_client.dart';

class NewsApi {
  final ApiClient _client;

  const NewsApi(this._client);

  Future<JsonMap> articles({
    required String category,
    required String level,
    int page = 1,
  }) async => _client.decodeMap(
    await _client.get(
      '/news',
      query: {'category': category, 'level': level, 'page': '$page'},
      requestTimeout: ApiClient.longTimeout,
    ),
  );
}
