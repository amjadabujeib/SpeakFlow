import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

class AuthSessionStore extends ChangeNotifier {
  AuthSessionStore._();

  static final AuthSessionStore instance = AuthSessionStore._();
  static const _baseUrl = 'http://localhost:8000';

  String? _accessToken;
  Map<String, dynamic>? _user;

  String? get accessToken => _accessToken;
  Map<String, dynamic>? get user => _user;
  String? get userId => _user?['user_id']?.toString();
  bool get hasSession => _accessToken != null && _user != null;
  bool get isGuest => _user?['kind'] == 'guest';

  Future<void> restore() async {
    try {
      final file = await _storageFile();
      if (!await file.exists()) return;
      final decoded = jsonDecode(await file.readAsString());
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

  Future<bool> validate() async {
    final token = _accessToken;
    if (token == null) return false;
    try {
      final response = await http.get(
        Uri.parse('$_baseUrl/api/auth/me'),
        headers: {'Authorization': 'Bearer $token'},
      );
      if (response.statusCode == 401) {
        await clear();
        return false;
      }
      if (response.statusCode != 200) {
        throw StateError('Authentication check failed.');
      }
      _user = Map<String, dynamic>.from(jsonDecode(response.body) as Map);
      await _persist();
      notifyListeners();
      return true;
    } catch (_) {
      rethrow;
    }
  }

  Future<void> setSession(Map<String, dynamic> payload) async {
    final token = payload['access_token']?.toString();
    final user = payload['user'];
    if (token == null || token.isEmpty || user is! Map) {
      throw const FormatException('Invalid authentication response.');
    }
    _accessToken = token;
    _user = Map<String, dynamic>.from(user);
    await _persist();
    notifyListeners();
  }

  Future<void> clear() async {
    _accessToken = null;
    _user = null;
    try {
      final file = await _storageFile();
      if (await file.exists()) await file.delete();
    } catch (_) {
      // In-memory sign-out still succeeds when local storage is unavailable.
    }
    notifyListeners();
  }

  Future<void> _persist() async {
    final file = await _storageFile();
    await file.writeAsString(
      jsonEncode({'access_token': _accessToken, 'user': _user}),
      flush: true,
    );
  }

  Future<File> _storageFile() async {
    final directory = await getApplicationDocumentsDirectory();
    return File('${directory.path}/auth_session.json');
  }
}

class AuthenticatedHttpClient extends http.BaseClient {
  final http.Client _inner;

  AuthenticatedHttpClient([http.Client? inner])
    : _inner = inner ?? http.Client();

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) {
    final token = AuthSessionStore.instance.accessToken;
    if (token != null && token.isNotEmpty) {
      request.headers.putIfAbsent('Authorization', () => 'Bearer $token');
    }
    return _inner.send(request);
  }

  @override
  void close() => _inner.close();
}
