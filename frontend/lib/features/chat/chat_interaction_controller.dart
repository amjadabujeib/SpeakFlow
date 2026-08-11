part of 'chat_screen.dart';

extension _ChatInteractionController on _ChatScreenState {
  Future<void> _toggleRecording() async {
    if (_ending || _waiting || !_socketReady) return;
    if (_recording) {
      final path = await _recorder.stop();
      if (!mounted) return;
      _update(() => _recording = false);
      if (path == null) return;
      final turnId = _newTurnId();
      try {
        final bytes = await File(path).readAsBytes();
        _recordingPaths[turnId] = path;
        _update(() {
          _waiting = true;
          _pendingTurnId = turnId;
        });
        _channel!.sink.add(
          jsonEncode({'type': 'audio_turn', 'turn_id': turnId}),
        );
        _channel!.sink.add(bytes);
      } catch (error) {
        _recordingPaths.remove(turnId);
        try {
          final recording = File(path);
          if (await recording.exists()) await recording.delete();
        } catch (_) {
          // Preserve the send error; cleanup is best effort.
        }
        if (mounted) {
          _update(() {
            _waiting = false;
            _pendingTurnId = null;
          });
          _showError('Could not send the recording: $error');
        }
      }
      return;
    }

    final permission = await Permission.microphone.request();
    if (permission != PermissionStatus.granted) {
      _showError('Microphone permission is needed for a spoken turn.');
      return;
    }
    final directory = await getTemporaryDirectory();
    final path =
        '${directory.path}/roleplay-${DateTime.now().microsecondsSinceEpoch}.wav';
    try {
      await _player.stop();
      await _recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.wav,
          sampleRate: 16000,
          numChannels: 1,
        ),
        path: path,
      );
      if (mounted) _update(() => _recording = true);
    } catch (error) {
      _showError('Could not start recording: $error');
    }
  }

  void _openHelp() {
    final unfinished = _scenario.objectives.where((objective) {
      final state = _objectiveState[objective.id];
      return state is! Map || state['completed'] != true;
    }).toList();
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: _surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
      ),
      builder: (_) => RoleplayLanguageHelpSheet(
        objectives: unfinished,
        phrases: _scenario.targetLanguage,
        onSelect: (value) {
          _textController.text = value;
          _textController.selection = TextSelection.collapsed(
            offset: value.length,
          );
        },
      ),
    );
  }

  Future<void> _requestEnd(String reason) async {
    if (_ending) return;
    if (_starting) {
      _showError('The roleplay is still preparing. Try again in a moment.');
      return;
    }
    if (_startError != null && !_sessionCreated) {
      context.go('/chat');
      return;
    }
    if (_startError != null && _sessionCreated) {
      await _finalize('disconnected');
      return;
    }
    if (_waiting) {
      _showError('Wait for your conversation partner to finish this turn.');
      return;
    }
    if (_recording) {
      final discard = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          backgroundColor: _card,
          title: Text(
            'Discard this recording?',
            style: GoogleFonts.inter(color: _text),
          ),
          content: Text(
            'The current recording has not been sent.',
            style: GoogleFonts.inter(color: _muted),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Keep recording'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text(
                'Discard and end',
                style: TextStyle(color: _error),
              ),
            ),
          ],
        ),
      );
      if (discard != true) return;
      await _recorder.stop();
      if (mounted) _update(() => _recording = false);
    }
    if (!mounted) return;
    final shouldEnd = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: _card,
        title: Text(
          _scenarioComplete ? 'Finish this roleplay?' : 'End practice?',
          style: GoogleFonts.inter(color: _text),
        ),
        content: Text(
          _scenarioComplete
              ? 'You completed every conversation goal. Your evidence-based summary is ready.'
              : 'You can end now, but unfinished goals will stay visible in your summary.',
          style: GoogleFonts.inter(color: _muted, height: 1.45),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep practicing'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: FilledButton.styleFrom(backgroundColor: _primary),
            child: const Text('View summary'),
          ),
        ],
      ),
    );
    if (shouldEnd != true) return;
    await _finalize(
      _scenarioComplete && reason == 'learner_ended'
          ? 'objective_completed'
          : reason,
    );
  }

  Future<void> _finalize(String reason) async {
    _update(() => _ending = true);
    try {
      final result = await ref
          .read(roleplayApiProvider)
          .finalizeSession(
            clientSessionId: _clientSessionId,
            endedReason: reason,
          );
      if (!mounted) return;
      final session = Map<String, dynamic>.from(
        result['session'] as Map? ?? {},
      );
      if (session['status'] == 'abandoned') {
        context.go('/chat');
        return;
      }
      var feedback = RoleplayFeedbackData.fromFinalizeJson(result);
      final practiceWordsAdded = await PracticeWordStore.instance
          .addRoleplayWords(
            scenario: feedback.scenario,
            candidates: feedback.recognitionChecks
                .map(
                  (item) => PracticeWordCandidate(
                    word: item.word,
                    score: item.confidence,
                  ),
                )
                .toList(growable: false),
          );
      feedback = feedback.withPracticeWordsAdded(practiceWordsAdded);
      if (!mounted) return;
      context.go('/chat/feedback', extra: feedback);
    } catch (error) {
      if (!mounted) return;
      _update(() => _ending = false);
      _showError('Could not create the session summary. Please try again.');
    }
  }

  Future<void> _retryStart() async {
    if (_sessionCreated) {
      try {
        await ref
            .read(roleplayApiProvider)
            .finalizeSession(
              clientSessionId: _clientSessionId,
              endedReason: 'disconnected',
            );
      } catch (_) {
        // The server also finalizes an unexpectedly disconnected socket.
      }
    }
    await _socketSubscription?.cancel();
    await _channel?.sink.close();
    _clientSessionId =
        'roleplay-${DateTime.now().microsecondsSinceEpoch}-${identityHashCode(this)}';
    _sessionCreated = false;
    _socketReady = false;
    _waiting = false;
    _pendingTurnId = null;
    await _start();
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(message),
          backgroundColor: _cardInner,
          behavior: SnackBarBehavior.floating,
        ),
      );
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 280),
        curve: Curves.easeOut,
      );
    });
  }

  Future<void> _play(RoleplayChatMessage message) async {
    try {
      if (message.audio != null) {
        await _player.play(BytesSource(message.audio!));
      } else if (message.localAudioPath != null) {
        await _player.play(DeviceFileSource(message.localAudioPath!));
      }
    } catch (_) {
      _showError('This audio is no longer available.');
    }
  }
}
