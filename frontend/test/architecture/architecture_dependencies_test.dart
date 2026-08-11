import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:speakflow/app/providers.dart';
import 'package:speakflow/core/network/api_client.dart';
import 'package:speakflow/core/network/api_config.dart';
import 'package:speakflow/features/learning_plan/data/plp_repository.dart';

void main() {
  test('API configuration owns the HTTP and WebSocket paths', () {
    expect(ApiConfig.uri('/auth/me').path, '/api/auth/me');
    expect(ApiConfig.websocketUri().path, '/ws/chat');
  });

  test('features do not bypass the shared API client', () {
    final dartFiles = Directory('lib')
        .listSync(recursive: true)
        .whereType<File>()
        .where((file) => file.path.endsWith('.dart'));
    final violations = <String>[];
    for (final file in dartFiles) {
      final source = file.readAsStringSync();
      if (RegExp(r'http\.(get|post|put|patch|delete)\(').hasMatch(source) ||
          source.contains('ApiService')) {
        violations.add(file.path);
      }
    }

    expect(violations, isEmpty);
  });

  test('runtime dependencies and app state are provider-owned', () {
    final violations = <String>[];
    for (final file in Directory(
      'lib',
    ).listSync(recursive: true).whereType<File>()) {
      if (!file.path.endsWith('.dart')) continue;
      final source = file.readAsStringSync();
      if (source.contains('AppDependencies.instance') ||
          (source.contains('AppState()') &&
              !file.path.endsWith('app/providers.dart') &&
              !file.path.endsWith('core/providers/app_state.dart'))) {
        violations.add(file.path);
      }
    }
    expect(violations, isEmpty);
  });

  test('test fixtures are not bundled as production assets', () {
    final manifest = File('pubspec.yaml').readAsStringSync();
    expect(manifest, isNot(contains('assets/mock/')));
    expect(File('test/fixtures/plp_plan.json').existsSync(), isTrue);
  });

  test('feature dependencies can be replaced through Riverpod', () async {
    late Uri requestedUri;
    late String requestBody;
    final mockClient = MockClient((request) async {
      requestedUri = request.url;
      requestBody = request.body;
      return http.Response('{"job_id":"job-1"}', 202);
    });
    final dependencies = AppDependencies(
      apiClient: ApiClient(httpClient: mockClient),
    );
    final container = ProviderContainer(
      overrides: [appDependenciesProvider.overrideWithValue(dependencies)],
    );
    addTearDown(container.dispose);

    final result = await container
        .read(learningPlanApiProvider)
        .generate(regenerate: true);

    expect(result['job_id'], 'job-1');
    expect(requestedUri.path, '/api/plp/generations');
    expect(jsonDecode(requestBody), {'regenerate': true});
  });

  test('PLP repository delegates to the learning-plan feature API', () async {
    late Uri requestedUri;
    final repository = HttpPlpRepository(
      baseUrl: 'https://example.test',
      client: MockClient((request) async {
        requestedUri = request.url;
        return http.Response('{"level":"B1"}', 200);
      }),
    );

    final profile = await repository.loadProfile();

    expect(profile['level'], 'B1');
    expect(
      requestedUri.toString(),
      'https://example.test/api/learners/local/profile',
    );
  });

  test('feature API errors retain the PLP repository contract', () async {
    final repository = HttpPlpRepository(
      client: MockClient(
        (_) async => http.Response('{"detail":"No active plan"}', 404),
      ),
    );

    expect(
      repository.loadPlan,
      throwsA(
        isA<PlpApiException>()
            .having((error) => error.statusCode, 'statusCode', 404)
            .having((error) => error.message, 'message', 'No active plan'),
      ),
    );
  });
}
