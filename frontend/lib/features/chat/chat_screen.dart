import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:speakflow/core/theme/local_fonts.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/io.dart';

import '../../core/auth/auth_session_store.dart';
import '../../app/providers.dart';
import '../../core/network/api_config.dart';
import '../../core/data/practice_word_store.dart';
import 'roleplay_chat_components.dart';
import 'roleplay_chat_message.dart';
import 'roleplay_feedback_data.dart';
import 'roleplay_language_help_sheet.dart';
import 'roleplay_message_bubbles.dart';
import 'roleplay_models.dart';

const _background = Color(0xFF090E1A);
const _surface = Color(0xFF111827);
const _card = Color(0xFF1A2235);
const _cardInner = Color(0xFF1E2D45);
const _primary = Color(0xFF4F7FFF);
const _success = Color(0xFF22C55E);
const _error = Color(0xFFEF4444);
const _text = Color(0xFFF1F5FF);
const _muted = Color(0xFF8896B0);
const _border = Color(0xFF263550);

class ChatScreen extends ConsumerStatefulWidget {
  final RoleplayScenario scenario;

  const ChatScreen({super.key, required this.scenario});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen>
    with SingleTickerProviderStateMixin {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();
  final List<RoleplayChatMessage> _messages = [];
  final Map<String, String> _recordingPaths = {};

  late String _clientSessionId;
  late final AnimationController _recordingAnimation;
  WebSocketChannel? _channel;
  StreamSubscription? _socketSubscription;

  Map<String, dynamic> _objectiveState = {};
  int _objectiveProgress = 0;
  bool _scenarioComplete = false;
  bool _starting = true;
  bool _sessionCreated = false;
  bool _socketReady = false;
  bool _waiting = false;
  bool _recording = false;
  bool _ending = false;
  String? _startError;
  String? _pendingTurnId;

  @override
  void initState() {
    super.initState();
    _clientSessionId =
        'roleplay-${DateTime.now().microsecondsSinceEpoch}-${identityHashCode(this)}';
    _recordingAnimation = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 650),
    )..repeat(reverse: true);
    _start();
  }

  Future<void> _start() async {
    if (mounted) {
      setState(() {
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
      _objectiveState = Map<String, dynamic>.from(
        started['objective_state'] as Map? ?? {},
      );
      _messages
        ..clear()
        ..add(
          RoleplayChatMessage(
            id: 'opening',
            isUser: false,
            text: widget.scenario.opening,
          ),
        );
      final channel = IOWebSocketChannel.connect(
        ApiConfig.websocketUri('/chat/ws'),
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
          setState(() {
            _socketReady = false;
            _waiting = false;
            _pendingTurnId = null;
          });
          _showError('The conversation connection was lost.');
        },
        onDone: () {
          if (!mounted || _ending) return;
          setState(() {
            _socketReady = false;
            _waiting = false;
            _pendingTurnId = null;
          });
        },
      );
      channel.sink.add(
        jsonEncode({
          'type': 'session_context',
          'client_session_id': _clientSessionId,
        }),
      );
      if (mounted) setState(() => _starting = false);
    } catch (error) {
      if (!mounted) return;
      setState(() {
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
          setState(() {
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
            setState(
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
    setState(() {
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
    setState(() {
      if (userIndex >= 0) {
        _messages[userIndex] = userMessage;
      } else {
        _messages.add(userMessage);
      }
      _messages.add(
        RoleplayChatMessage(
          id: 'ai-$turnId',
          isUser: false,
          text: event['text']?.toString() ?? 'Could you say that again?',
        ),
      );
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
      setState(() => _messages[index] = _messages[index].withAudio(bytes));
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
    final turnId = _newTurnId();
    setState(() {
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

  Future<void> _toggleRecording() async {
    if (_ending || _waiting || !_socketReady) return;
    if (_recording) {
      final path = await _recorder.stop();
      if (!mounted) return;
      setState(() => _recording = false);
      if (path == null) return;
      final turnId = _newTurnId();
      try {
        final bytes = await File(path).readAsBytes();
        _recordingPaths[turnId] = path;
        setState(() {
          _waiting = true;
          _pendingTurnId = turnId;
        });
        _channel!.sink.add(
          jsonEncode({'type': 'audio_turn', 'turn_id': turnId}),
        );
        _channel!.sink.add(bytes);
      } catch (error) {
        _recordingPaths.remove(turnId);
        if (mounted) {
          setState(() {
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
      if (mounted) setState(() => _recording = true);
    } catch (error) {
      _showError('Could not start recording: $error');
    }
  }

  void _openHelp() {
    final unfinished = widget.scenario.objectives.where((objective) {
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
        phrases: widget.scenario.targetLanguage,
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
      if (mounted) setState(() => _recording = false);
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
    setState(() => _ending = true);
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
      setState(() => _ending = false);
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

  @override
  void dispose() {
    _socketSubscription?.cancel();
    _channel?.sink.close();
    _recorder.dispose();
    _player.dispose();
    _recordingAnimation.dispose();
    _textController.dispose();
    _scrollController.dispose();
    for (final path in _recordingPaths.values) {
      File(path).delete().catchError((_) => File(path));
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _requestEnd('back_navigation');
      },
      child: Scaffold(
        backgroundColor: _background,
        appBar: _appBar(),
        body: _starting
            ? const Center(child: CircularProgressIndicator(color: _primary))
            : _startError != null
            ? RoleplayStartError(message: _startError!, onRetry: _retryStart)
            : Column(
                children: [
                  RoleplayGoalProgressCard(
                    scenario: widget.scenario,
                    objectiveState: _objectiveState,
                    progress: _objectiveProgress,
                    complete: _scenarioComplete,
                  ),
                  Expanded(child: _messageList()),
                  _inputBar(),
                ],
              ),
      ),
    );
  }

  AppBar _appBar() {
    return AppBar(
      backgroundColor: _surface,
      elevation: 0,
      leading: IconButton(
        onPressed: () => _requestEnd('back_navigation'),
        icon: const Icon(Icons.arrow_back_ios_new_rounded, color: _text),
      ),
      title: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            widget.scenario.title,
            style: GoogleFonts.inter(
              color: _text,
              fontWeight: FontWeight.w700,
              fontSize: 16,
            ),
          ),
          Text(
            'You are the ${widget.scenario.learnerRole}',
            style: GoogleFonts.inter(color: _muted, fontSize: 11),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: _ending ? null : () => _requestEnd('learner_ended'),
          child: _ending
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: _primary,
                  ),
                )
              : Text(
                  'End',
                  style: GoogleFonts.inter(
                    color: _error,
                    fontWeight: FontWeight.w700,
                  ),
                ),
        ),
      ],
      bottom: const PreferredSize(
        preferredSize: Size.fromHeight(1),
        child: Divider(height: 1, color: _border),
      ),
    );
  }

  Widget _messageList() {
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 20),
      itemCount: _messages.length + (_waiting ? 1 : 0),
      itemBuilder: (context, index) {
        if (index == _messages.length) {
          return const RoleplayThinkingBubble();
        }
        final message = _messages[index];
        return message.isUser
            ? RoleplayUserMessageBubble(
                text: message.text,
                correctedText: message.correctedText,
                grammarFeedback: message.grammarFeedback,
                wordConfidence: message.wordConfidence,
                hasReplay: message.localAudioPath != null,
                onReplay: () => _play(message),
                transcriptKey: const ValueKey('roleplay-confidence-transcript'),
              )
            : RoleplayPartnerMessageBubble(
                text: message.text,
                hasAudio: message.audio != null,
                onPlay: () => _play(message),
              );
      },
    );
  }

  Widget _inputBar() {
    final disabled = !_socketReady || _waiting || _ending || _starting;
    return Container(
      color: _surface,
      padding: EdgeInsets.fromLTRB(
        12,
        10,
        12,
        MediaQuery.paddingOf(context).bottom + 10,
      ),
      child: Row(
        children: [
          RoleplayRoundAction(
            icon: Icons.translate_rounded,
            tooltip: 'Say it in English',
            onTap: disabled ? null : _openHelp,
          ),
          const SizedBox(width: 9),
          Expanded(
            child: _recording
                ? RoleplayRecordingState(animation: _recordingAnimation)
                : TextField(
                    controller: _textController,
                    enabled: !disabled,
                    onSubmitted: (_) => _sendText(),
                    style: GoogleFonts.inter(color: _text),
                    decoration: InputDecoration(
                      hintText: !_socketReady
                          ? 'Connecting…'
                          : _waiting
                          ? 'Waiting for a reply…'
                          : 'Your response…',
                      hintStyle: GoogleFonts.inter(color: _muted, fontSize: 13),
                      filled: true,
                      fillColor: _card,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(15),
                        borderSide: BorderSide.none,
                      ),
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 15,
                        vertical: 12,
                      ),
                      suffixIcon: IconButton(
                        onPressed: _canSubmit ? _sendText : null,
                        icon: const Icon(Icons.send_rounded),
                        color: _primary,
                      ),
                    ),
                  ),
          ),
          const SizedBox(width: 9),
          RoleplayRoundAction(
            icon: _recording ? Icons.stop_rounded : Icons.mic_rounded,
            tooltip: _recording ? 'Stop recording' : 'Speak',
            active: _recording,
            onTap: (_socketReady && !_waiting && !_ending)
                ? _toggleRecording
                : null,
          ),
        ],
      ),
    );
  }
}
