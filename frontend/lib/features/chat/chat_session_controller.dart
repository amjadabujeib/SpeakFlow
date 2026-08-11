part of 'chat_screen.dart';

extension _ChatSessionController on _ChatScreenState {
  Future<void> _start() async {
    if (mounted) {
      _update(() {
        _starting = true;
        _startError = null;
      });
    }
    try {
      final started = await ref
          .read(roleplayApiProvider)
          .startSession(
            clientSessionId: _clientSessionId,
            scenarioId: widget.scenario.id,
          );
      _sessionCreated = true;
      _scenario = RoleplayScenario.fromJson(
        Map<String, dynamic>.from(started['scenario'] as Map? ?? {}),
      );
      _objectiveState = Map<String, dynamic>.from(
        started['objective_state'] as Map? ?? {},
      );
      _messages
        ..clear()
        ..add(
          RoleplayChatMessage(
            id: 'opening',
            isUser: false,
            text: _scenario.opening,
          ),
        );
      final channel = IOWebSocketChannel.connect(
        ApiConfig.websocketUri(),
        headers: {
          'Authorization':
              'Bearer ${AuthSessionStore.instance.accessToken ?? ''}',
        },
      );
      await channel.ready;
      _channel = channel;
      _socketSubscription = channel.stream.listen(
        _onSocketMessage,
        onError: (Object error) {
          if (!mounted || _ending) return;
          _update(() {
            _socketReady = false;
            _waiting = false;
            _pendingTurnId = null;
            _startError = 'The conversation connection was lost.';
          });
          _showError('The conversation connection was lost.');
        },
        onDone: () {
          if (!mounted || _ending) return;
          _update(() {
            _socketReady = false;
            _waiting = false;
            _pendingTurnId = null;
            _startError = 'The conversation connection was closed.';
          });
        },
      );
      channel.sink.add(
        jsonEncode({
          'type': 'session_context',
          'client_session_id': _clientSessionId,
        }),
      );
      if (mounted) _update(() => _starting = false);
    } catch (error) {
      if (!mounted) return;
      _update(() {
        _starting = false;
        _startError = '$error';
      });
    }
  }

  void _onSocketMessage(dynamic raw) {
    if (!mounted || raw is! String) return;
    try {
      final event = Map<String, dynamic>.from(jsonDecode(raw) as Map);
      switch (event['type']) {
        case 'session_ready':
          _update(() {
            _socketReady = true;
            _objectiveState = Map<String, dynamic>.from(
              event['objective_state'] as Map? ?? _objectiveState,
            );
          });
        case 'turn_response':
          _handleTurnResponse(event);
        case 'turn_audio':
          _handleTurnAudio(event);
        case 'turn_error':
          _handleTurnError(event);
        case 'protocol_error':
          if (!_socketReady) {
            _update(
              () => _startError =
                  event['error']?.toString() ??
                  'The roleplay session could not be connected.',
            );
          }
          _showError(
            event['error']?.toString() ?? 'The turn could not be completed.',
          );
      }
    } catch (_) {
      _showError('The conversation returned an invalid response.');
    }
  }

  void _handleTurnError(Map<String, dynamic> event) {
    final turnId = event['turn_id']?.toString();
    final failedRecording = turnId == null ? null : _recordingPaths[turnId];
    _update(() {
      if (turnId != null && turnId == _pendingTurnId) {
        final index = _messages.indexWhere((item) => item.id == turnId);
        if (index >= 0) {
          final failedText = _messages[index].text;
          _messages.removeAt(index);
          if (_textController.text.trim().isEmpty) {
            _textController.text = failedText;
            _textController.selection = TextSelection.collapsed(
              offset: failedText.length,
            );
          }
        }
        _recordingPaths.remove(turnId);
        _waiting = false;
        _pendingTurnId = null;
      }
    });
    if (failedRecording != null) {
      File(failedRecording).delete().catchError((_) => File(failedRecording));
    }
    _showError(
      event['error']?.toString() ?? 'The turn could not be completed.',
    );
  }

  void _handleTurnResponse(Map<String, dynamic> event) {
    final turnId = event['turn_id']?.toString() ?? '';
    if (turnId.isEmpty) return;
    final rawWords = event['word_confidence'];
    final words = rawWords is List
        ? rawWords
              .whereType<Map>()
              .map((item) => Map<String, dynamic>.from(item))
              .toList(growable: false)
        : <Map<String, dynamic>>[];
    final userIndex = _messages.indexWhere((item) => item.id == turnId);
    final userMessage = RoleplayChatMessage(
      id: turnId,
      isUser: true,
      text: event['user_text']?.toString() ?? '',
      correctedText: event['grammar_corrected_text']?.toString(),
      grammarFeedback: event['grammar_feedback']?.toString(),
      wordConfidence: words,
      localAudioPath: _recordingPaths[turnId],
    );
    final completedNow =
        !_scenarioComplete && event['scenario_complete'] == true;
    _update(() {
      if (userIndex >= 0) {
        _messages[userIndex] = userMessage;
      } else {
        _messages.add(userMessage);
      }
      if (_messages.every((item) => item.id != 'ai-$turnId')) {
        _messages.add(
          RoleplayChatMessage(
            id: 'ai-$turnId',
            isUser: false,
            text: event['text']?.toString() ?? 'Could you say that again?',
          ),
        );
      }
      _objectiveState = Map<String, dynamic>.from(
        event['objective_state'] as Map? ?? _objectiveState,
      );
      _objectiveProgress =
          (event['objective_progress'] as num?)?.round().clamp(0, 100) ??
          _objectiveProgress;
      _scenarioComplete = event['scenario_complete'] == true;
      _waiting = false;
      _pendingTurnId = null;
    });
    if (completedNow) {
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(
          SnackBar(
            content: const Row(
              children: [
                Icon(Icons.verified_rounded, color: _success, size: 19),
                SizedBox(width: 9),
                Expanded(
                  child: Text(
                    'All goals complete. Keep talking or end when you’re ready.',
                  ),
                ),
              ],
            ),
            duration: const Duration(milliseconds: 1800),
            backgroundColor: const Color(0xFF0B3328),
            behavior: SnackBarBehavior.floating,
          ),
        );
    }
    _scrollToBottom();
  }

  void _handleTurnAudio(Map<String, dynamic> event) {
    final turnId = event['turn_id']?.toString() ?? '';
    final encoded = event['audio_base64']?.toString() ?? '';
    if (turnId.isEmpty || encoded.isEmpty) return;
    try {
      final bytes = base64Decode(encoded);
      final index = _messages.indexWhere((item) => item.id == 'ai-$turnId');
      if (index < 0) return;
      _update(() => _messages[index] = _messages[index].withAudio(bytes));
      if (!_recording) _player.play(BytesSource(bytes));
    } catch (_) {
      // Text remains usable if generated audio cannot be decoded or played.
    }
  }

  String _newTurnId() =>
      'turn-${DateTime.now().microsecondsSinceEpoch}-${_messages.length}';

  void _sendText() {
    final text = _textController.text.trim();
    if (text.isEmpty || !_canSubmit) return;
    final languageError = roleplayTypedTurnError(text);
    if (languageError != null) {
      _showError(languageError);
      return;
    }
    final turnId = _newTurnId();
    _update(() {
      _messages.add(RoleplayChatMessage(id: turnId, isUser: true, text: text));
      _textController.clear();
      _waiting = true;
      _pendingTurnId = turnId;
    });
    _channel!.sink.add(
      jsonEncode({'type': 'user_turn', 'turn_id': turnId, 'text': text}),
    );
    _scrollToBottom();
  }

  bool get _canSubmit =>
      _socketReady && !_waiting && !_recording && !_ending && !_starting;
}
