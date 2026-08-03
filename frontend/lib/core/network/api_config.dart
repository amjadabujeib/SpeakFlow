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
  static const String apiPrefix = '/api';

  static const ApiEndpoints endpoints = ApiEndpoints(
    origin: origin,
    websocketOrigin: websocketOrigin,
    apiPrefix: apiPrefix,
  );

  static Uri uri(String path, {Map<String, String>? queryParameters}) =>
      endpoints.uri(path, queryParameters: queryParameters);

  static Uri websocketUri() => endpoints.websocketUri('/ws/chat');
}

/// Injectable endpoint configuration for production code and isolated tests.
class ApiEndpoints {
  final String origin;
  final String websocketOrigin;
  final String apiPrefix;

  const ApiEndpoints({
    required this.origin,
    required this.websocketOrigin,
    this.apiPrefix = '/api',
  });

  String _join(String base, String path) {
    final cleanBase = base.endsWith('/')
        ? base.substring(0, base.length - 1)
        : base;
    final cleanPrefix = apiPrefix.startsWith('/') ? apiPrefix : '/$apiPrefix';
    final cleanPath = path.startsWith('/') ? path : '/$path';
    return '$cleanBase$cleanPrefix$cleanPath';
  }

  Uri uri(String path, {Map<String, String>? queryParameters}) =>
      Uri.parse(_join(origin, path)).replace(queryParameters: queryParameters);

  Uri websocketUri(String path) {
    final cleanOrigin = websocketOrigin.endsWith('/')
        ? websocketOrigin.substring(0, websocketOrigin.length - 1)
        : websocketOrigin;
    final cleanPath = path.startsWith('/') ? path : '/$path';
    return Uri.parse('$cleanOrigin$cleanPath');
  }
}
