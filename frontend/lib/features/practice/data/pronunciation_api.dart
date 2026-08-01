import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_client.dart';

class PronunciationApi {
  final ApiClient _client;

  const PronunciationApi(this._client);

  Future<JsonMap> guide(String target) async {
    try {
      return _client.decodeMap(
        await _client.get('/pronunciation/guide', query: {'text': target}),
      );
    } on ApiException catch (error) {
      return {'error': error.message};
    } catch (error) {
      return {'error': 'Could not load pronunciation guide: $error'};
    }
  }

  Future<JsonMap> score(
    String targetWord,
    String audioFilePath, {
    String? activityId,
    String? attemptSessionId,
  }) async {
    try {
      final request = http.MultipartRequest(
        'POST',
        _client.uri('/pronunciation'),
      );
      request.fields['target_word'] = targetWord;
      if (activityId != null) request.fields['activity_id'] = activityId;
      if (attemptSessionId != null) {
        request.fields['attempt_session_id'] = attemptSessionId;
      }
      request.files.add(
        await http.MultipartFile.fromPath('file', audioFilePath),
      );

      final response = await _client.httpClient
          .send(request)
          .timeout(ApiClient.longTimeout);
      final body = await response.stream.bytesToString();
      if (response.statusCode == 200) {
        return Map<String, dynamic>.from(jsonDecode(body) as Map);
      }
      final decoded = _client.tryDecode(body);
      return {
        'error': decoded is Map && decoded['detail'] != null
            ? decoded['detail'].toString()
            : 'Server error: ${response.statusCode}',
        'status_code': response.statusCode,
      };
    } catch (error) {
      return {'error': 'Connection failed: $error'};
    }
  }
}
