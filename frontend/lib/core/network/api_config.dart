class ApiConfig {
  const ApiConfig._();

  static const String origin = String.fromEnvironment(
    'SPEAKFLOW_API_URL',
    defaultValue: 'http://localhost:8000',
  );
  static const String websocketOrigin = String.fromEnvironment(
    'SPEAKFLOW_WS_URL',
    defaultValue: 'ws://localhost:8000',
  );
  static const String apiPrefix = '/api/v1';

  static const ApiEndpoints endpoints = ApiEndpoints(
    origin: origin,
    websocketOrigin: websocketOrigin,
    apiPrefix: apiPrefix,
  );

  static Uri uri(String path, {Map<String, String>? queryParameters}) =>
      endpoints.uri(path, queryParameters: queryParameters);

  static Uri websocketUri(String path) => endpoints.websocketUri(path);
}

/// Injectable endpoint configuration for production code and isolated tests.
class ApiEndpoints {
  final String origin;
  final String websocketOrigin;
  final String apiPrefix;

  const ApiEndpoints({
    required this.origin,
    required this.websocketOrigin,
    this.apiPrefix = '/api/v1',
  });

  Uri uri(String path, {Map<String, String>? queryParameters}) => Uri.parse(
    '$origin$apiPrefix$path',
  ).replace(queryParameters: queryParameters);

  Uri websocketUri(String path) => Uri.parse('$websocketOrigin$apiPrefix$path');
}
