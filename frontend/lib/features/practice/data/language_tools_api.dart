import 'dart:typed_data';

import '../../../core/network/api_client.dart';

class LanguageToolsApi {
  final ApiClient _client;

  const LanguageToolsApi(this._client);

  Future<JsonMap> checkGrammar(String text) async {
    try {
      return _client.decodeMap(
        await _client.post('/grammar/check', body: {'text': text}),
      );
    } on ApiException catch (error) {
      return {'error': error.message};
    } catch (_) {
      return {'error': 'Could not reach the backend. Check your connection.'};
    }
  }

  Future<JsonMap> lookupWord(String word) async {
    try {
      return _client.decodeMap(
        await _client.post('/vocabulary/lookup', body: {'word': word}),
      );
    } on ApiException catch (error) {
      return {'error': error.message};
    } catch (_) {
      return {'error': 'Could not reach the backend. Check your connection.'};
    }
  }

  Future<Uint8List> synthesizeSpeech(String text) async {
    final response = await _client.post(
      '/tts',
      body: {'text': text},
      requestTimeout: ApiClient.longTimeout,
    );
    if (response.statusCode != 200) {
      throw ApiException(
        _client.errorDetail(response),
        statusCode: response.statusCode,
      );
    }
    return response.bodyBytes;
  }
}
