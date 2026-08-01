import '../../../core/auth/auth_session_store.dart';
import '../../../core/network/api_client.dart';

class AuthApi {
  final ApiClient _client;
  final AuthSessionStore _sessionStore;

  AuthApi(this._client, {AuthSessionStore? sessionStore})
    : _sessionStore = sessionStore ?? AuthSessionStore.instance;

  bool get hasSession => _sessionStore.hasSession;

  Future<JsonMap> signUp({
    required String displayName,
    required String email,
    required String password,
  }) async {
    final payload = _client.decodeMap(
      await _client.post(
        '/auth/signup',
        body: {
          'display_name': displayName,
          'email': email,
          'password': password,
        },
      ),
      successStatuses: const {201},
    );
    await _sessionStore.setSession(payload);
    return payload;
  }

  Future<JsonMap> signIn({
    required String email,
    required String password,
  }) async {
    final payload = _client.decodeMap(
      await _client.post(
        '/auth/signin',
        body: {'email': email, 'password': password},
      ),
    );
    await _sessionStore.setSession(payload);
    return payload;
  }

  Future<JsonMap> continueAsGuest() async {
    final payload = _client.decodeMap(
      await _client.post('/auth/guest', body: {'display_name': 'Guest'}),
      successStatuses: const {201},
    );
    await _sessionStore.setSession(payload);
    return payload;
  }

  Future<bool> validateSession() async {
    if (!_sessionStore.hasSession) return false;
    final response = await _client.get('/auth/me');
    if (response.statusCode == 401) {
      await _sessionStore.clear();
      return false;
    }
    final user = _client.decodeMap(response);
    await _sessionStore.updateUser(user);
    return true;
  }

  Future<void> signOut() async {
    try {
      await _client.post('/auth/signout');
    } finally {
      await _sessionStore.clear();
    }
  }

  Future<void> forgetSession() => _sessionStore.clear();
}
