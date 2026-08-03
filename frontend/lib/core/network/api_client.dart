import 'dart:convert';

import 'package:http/http.dart' as http;

import '../auth/auth_session_store.dart';
import 'api_config.dart';

typedef JsonMap = Map<String, dynamic>;

class ApiException implements Exception {
  final int? statusCode;
  final String message;

  const ApiException(this.message, {this.statusCode});

  @override
  String toString() => message;
}

class ApiClient {
  static const timeout = Duration(seconds: 30);
  static const longTimeout = Duration(seconds: 60);
  static const historyTimeout = Duration(seconds: 8);

  final http.Client httpClient;
  final ApiEndpoints endpoints;

  ApiClient({http.Client? httpClient, this.endpoints = ApiConfig.endpoints})
    : httpClient = httpClient ?? AuthenticatedHttpClient();

  Uri uri(String path, {Map<String, String>? query}) =>
      endpoints.uri(path, queryParameters: query);

  Future<http.Response> get(
    String path, {
    Map<String, String>? query,
    Duration requestTimeout = timeout,
  }) => httpClient.get(uri(path, query: query)).timeout(requestTimeout);

  Future<http.Response> post(
    String path, {
    JsonMap? body,
    Duration requestTimeout = timeout,
  }) => httpClient
      .post(
        uri(path),
        headers: body == null
            ? null
            : const {'Content-Type': 'application/json'},
        body: body == null ? null : jsonEncode(body),
      )
      .timeout(requestTimeout);

  Future<http.Response> put(
    String path, {
    required JsonMap body,
    Duration requestTimeout = timeout,
  }) => httpClient
      .put(
        uri(path),
        headers: const {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      )
      .timeout(requestTimeout);

  Future<http.Response> delete(
    String path, {
    Duration requestTimeout = timeout,
  }) => httpClient.delete(uri(path)).timeout(requestTimeout);

  JsonMap decodeMap(
    http.Response response, {
    Set<int> successStatuses = const {200},
  }) {
    final decoded = tryDecode(response.body);
    if (!successStatuses.contains(response.statusCode)) {
      throw ApiException(
        errorDetail(response, decoded: decoded),
        statusCode: response.statusCode,
      );
    }
    if (decoded is! Map) {
      throw const ApiException('The backend returned an invalid response.');
    }
    return Map<String, dynamic>.from(decoded);
  }

  List<JsonMap> decodeMapList(
    http.Response response, {
    Set<int> successStatuses = const {200},
  }) {
    final decoded = tryDecode(response.body);
    if (!successStatuses.contains(response.statusCode)) {
      throw ApiException(
        errorDetail(response, decoded: decoded),
        statusCode: response.statusCode,
      );
    }
    if (decoded is! List) {
      throw const ApiException('The backend returned an invalid response.');
    }
    return decoded
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList(growable: false);
  }

  dynamic tryDecode(String body) {
    try {
      return jsonDecode(body);
    } catch (_) {
      return null;
    }
  }

  String errorDetail(http.Response response, {dynamic decoded}) {
    final payload = decoded ?? tryDecode(response.body);
    if (payload is Map && payload['detail'] != null) {
      return payload['detail'].toString();
    }
    return 'Server error: ${response.statusCode}';
  }

  void close() => httpClient.close();
}
