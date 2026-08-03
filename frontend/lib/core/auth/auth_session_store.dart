import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

class AuthSessionStore extends ChangeNotifier {
  AuthSessionStore._();

  static final AuthSessionStore instance = AuthSessionStore._();
  static const _storageKey = 'speakflow_auth_session';
  static const _secureStorage = FlutterSecureStorage(
    aOptions: AndroidOptions(),
  );

  String? _accessToken;
  Map<String, dynamic>? _user;

  String? get accessToken => _accessToken;
  Map<String, dynamic>? get user => _user;
  String? get userId => _user?['user_id']?.toString();
  bool get hasSession => _accessToken != null && _user != null;
  bool get isGuest => _user?['kind'] == 'guest';

  Future<void> restore() async {
    try {
      var stored = await _secureStorage.read(key: _storageKey);
      stored ??= await _migrateLegacyStorage();
      if (stored == null) return;
      final decoded = jsonDecode(stored);
      if (decoded is! Map) return;
      final value = Map<String, dynamic>.from(decoded);
      final token = value['access_token']?.toString();
      final user = value['user'];
      if (token == null || token.isEmpty || user is! Map) return;
      _accessToken = token;
      _user = Map<String, dynamic>.from(user);
    } catch (_) {
      _accessToken = null;
      _user = null;
    }
  }

  Future<void> setSession(Map<String, dynamic> payload) async {
    final token = payload['access_token']?.toString();
    final user = payload['user'];
    if (token == null || token.isEmpty || user is! Map) {
      throw const FormatException('Invalid authentication response.');
    }
    final normalizedUser = Map<String, dynamic>.from(user);
    await _persistSession(token, normalizedUser);
    _accessToken = token;
    _user = normalizedUser;
    notifyListeners();
  }

  Future<void> updateUser(Map<String, dynamic> user) async {
    if (_accessToken == null) {
      throw StateError('Cannot update a user without an active session.');
    }
    final normalizedUser = Map<String, dynamic>.from(user);
    await _persistSession(_accessToken!, normalizedUser);
    _user = normalizedUser;
    notifyListeners();
  }

  Future<void> clear() async {
    _accessToken = null;
    _user = null;
    try {
      await _secureStorage.delete(key: _storageKey);
    } catch (_) {
      // In-memory sign-out still succeeds when local storage is unavailable.
    }
    notifyListeners();
  }

  Future<void> _persistSession(
    String accessToken,
    Map<String, dynamic> user,
  ) async {
    await _secureStorage.write(
      key: _storageKey,
      value: jsonEncode({'access_token': accessToken, 'user': user}),
    );
  }

  Future<String?> _migrateLegacyStorage() async {
    final directory = await getApplicationDocumentsDirectory();
    final file = File('${directory.path}/auth_session.json');
    if (!await file.exists()) return null;
    final value = await file.readAsString();
    await _secureStorage.write(key: _storageKey, value: value);
    await file.delete();
    return value;
  }
}

class AuthenticatedHttpClient extends http.BaseClient {
  final http.Client _inner;

  AuthenticatedHttpClient([http.Client? inner])
    : _inner = inner ?? http.Client();

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final token = AuthSessionStore.instance.accessToken;
    if (token != null && token.isNotEmpty) {
      request.headers.putIfAbsent('Authorization', () => 'Bearer $token');
    }
    final response = await _inner.send(request);
    final isCredentialEndpoint = const {
      '/auth/signin',
      '/auth/signup',
      '/auth/guest',
    }.any(request.url.path.endsWith);
    if (token != null &&
        token.isNotEmpty &&
        response.statusCode == 401 &&
        !isCredentialEndpoint) {
      await AuthSessionStore.instance.clear();
    }
    return response;
  }

  @override
  void close() => _inner.close();
}
