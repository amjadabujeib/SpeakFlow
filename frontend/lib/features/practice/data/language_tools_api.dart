import '../../../core/network/api_client.dart';

class LanguageToolsApi {
  final ApiClient _client;

  const LanguageToolsApi(this._client);

  Future<JsonMap> checkGrammar(String text) async {
    try {
      return _client.decodeMap(
        await _client.post('/grammar/check', body: {'text': text}),
      );
    } catch (error) {
      return {'error': 'Connection failed. Is the backend running?\n$error'};
    }
  }

  Future<JsonMap> lookupWord(String word) async {
    try {
      return _client.decodeMap(
        await _client.post('/vocabulary/lookup', body: {'word': word}),
      );
    } on ApiException catch (error) {
      return {'error': error.message};
    } catch (error) {
      return {'error': 'Connection failed: $error'};
    }
  }

  Uri ttsUri(String text) => _client.uri('/tts', query: {'text': text});
}
