import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:speakflow/core/network/api_client.dart';
import 'package:speakflow/core/network/api_config.dart';
import 'package:speakflow/features/chat/data/roleplay_api.dart';

void main() {
  test(
    'custom scenario update preserves weights and delete uses its resource',
    () async {
      final requests = <http.Request>[];
      final client = MockClient((request) async {
        requests.add(request);
        if (request.method == 'DELETE') return http.Response('', 204);
        return http.Response(
          jsonEncode({'id': 'custom_12345678901234567890'}),
          200,
        );
      });
      final api = RoleplayApi(
        ApiClient(
          httpClient: client,
          endpoints: const ApiEndpoints(
            origin: 'http://speakflow.test',
            websocketOrigin: 'ws://speakflow.test',
          ),
        ),
      );

      await api.updateScenario(
        scenarioId: 'custom_12345678901234567890',
        category: 'Travel',
        icon: '🚆',
        title: 'Change a train ticket',
        description: 'Ask an agent to change a train ticket to another time.',
        aiRole: 'ticket agent',
        learnerRole: 'passenger',
        opening: 'How may I help with your ticket?',
        objectives: const [
          {'id': 'request', 'label': 'Explain the request', 'weight': 4},
          {'id': 'time', 'label': 'Choose another time', 'weight': 2},
          {'id': 'confirm', 'label': 'Confirm the change', 'weight': 3},
        ],
        targetLanguage: const ['I need to change', 'Is there a train at'],
        evaluationRubric: const [
          {
            'id': 'clarity',
            'label': 'Request clarity',
            'description': 'Explains the requested change clearly.',
            'weight': 5,
          },
          {
            'id': 'confirmation',
            'label': 'Confirmation',
            'description': 'Confirms the final ticket details.',
            'weight': 3,
          },
        ],
        designedCefrLevel: 'A2',
      );
      await api.deleteScenario('custom_12345678901234567890');

      expect(requests[0].method, 'PUT');
      expect(
        requests[0].url.path,
        '/api/roleplay/scenarios/custom_12345678901234567890',
      );
      final body = jsonDecode(requests[0].body) as Map<String, dynamic>;
      expect((body['objectives'] as List).first['weight'], 4);
      expect((body['evaluation_rubric'] as List).first['weight'], 5);
      expect(requests[1].method, 'DELETE');
      expect(requests[1].url.path, requests[0].url.path);
    },
  );
}
