import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:just_talk/core/theme/local_fonts.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/io.dart';

import '../../core/auth/auth_session_store.dart';
import '../../core/services/api_service.dart';
import '../../core/data/practice_word_store.dart';
import 'roleplay_feedback_data.dart';
import 'roleplay_models.dart';

const _background = Color(0xFF090E1A);
const _surface = Color(0xFF111827);
const _card = Color(0xFF1A2235);
const _cardInner = Color(0xFF1E2D45);
const _primary = Color(0xFF4F7FFF);
const _accent = Color(0xFF8B5CF6);
const _success = Color(0xFF22C55E);
const _warning = Color(0xFFF59E0B);
const _error = Color(0xFFEF4444);
const _text = Color(0xFFF1F5FF);
const _muted = Color(0xFF8896B0);
const _border = Color(0xFF263550);

class ChatMessage {
  final String id;
  final bool isUser;
  final String text;
  final String? correctedText;
  final String? grammarFeedback;
  final List<Map<String, dynamic>> wordConfidence;
  final int? fluency;
  final int? pitchVariation;
  final Uint8List? audio;
  final String? localAudioPath;

  const ChatMessage({
    required this.id,
    required this.isUser,
    required this.text,
    this.correctedText,
    this.grammarFeedback,
    this.wordConfidence = const [],
    this.fluency,
    this.pitchVariation,
    this.audio,
    this.localAudioPath,
  });

  ChatMessage copyWith({
    String? text,
    String? correctedText,
    String? grammarFeedback,
    List<Map<String, dynamic>>? wordConfidence,
    int? fluency,
    int? pitchVariation,
    Uint8List? audio,
    String? localAudioPath,
  }) {
    return ChatMessage(
      id: id,
      isUser: isUser,
      text: text ?? this.text,
      correctedText: correctedText ?? this.correctedText,
      grammarFeedback: grammarFeedback ?? this.grammarFeedback,
      wordConfidence: wordConfidence ?? this.wordConfidence,
      fluency: fluency ?? this.fluency,
      pitchVariation: pitchVariation ?? this.pitchVariation,
      audio: audio ?? this.audio,
      localAudioPath: localAudioPath ?? this.localAudioPath,
    );
  }
}

class ChatScreen extends StatefulWidget {
  final RoleplayScenario scenario;

  const ChatScreen({super.key, required this.scenario});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen>
    with SingleTickerProviderStateMixin {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();
  final List<ChatMessage> _messages = [];
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
      final started = await ApiService.startRoleplaySession(
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
          ChatMessage(
            id: 'opening',
            isUser: false,
            text: widget.scenario.opening,
          ),
        );
      final channel = IOWebSocketChannel.connect(
        Uri.parse('${ApiService.wsUrl}/ws/chat'),
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
    final metrics = Map<String, dynamic>.from(
      event['delivery_metrics'] as Map? ?? {},
    );
    final userIndex = _messages.indexWhere((item) => item.id == turnId);
    final userMessage = ChatMessage(
      id: turnId,
      isUser: true,
      text: event['user_text']?.toString() ?? '',
      correctedText: event['grammar_corrected_text']?.toString(),
      grammarFeedback: event['grammar_feedback']?.toString(),
      wordConfidence: words,
      fluency: (metrics['fluency'] as num?)?.round(),
      pitchVariation: (metrics['pitch_variation'] as num?)?.round(),
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
        ChatMessage(
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
      setState(
        () => _messages[index] = _messages[index].copyWith(audio: bytes),
      );
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
      _messages.add(ChatMessage(id: turnId, isUser: true, text: text));
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
      builder: (_) => _LanguageHelpSheet(
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
      final result = await ApiService.finalizeRoleplaySession(
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
      final feedback = RoleplayFeedbackData.fromFinalizeJson(result);
      await PracticeWordStore.instance.addRoleplayWords(
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
        await ApiService.finalizeRoleplaySession(
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

  Future<void> _play(ChatMessage message) async {
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
            ? _StartError(message: _startError!, onRetry: _retryStart)
            : Column(
                children: [
                  _GoalProgressCard(
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
        if (index == _messages.length) return const _ThinkingBubble();
        final message = _messages[index];
        return message.isUser
            ? _UserBubble(message: message, onPlay: () => _play(message))
            : _PartnerBubble(message: message, onPlay: () => _play(message));
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
          _RoundAction(
            icon: Icons.translate_rounded,
            tooltip: 'Say it in English',
            onTap: disabled ? null : _openHelp,
          ),
          const SizedBox(width: 9),
          Expanded(
            child: _recording
                ? _RecordingState(animation: _recordingAnimation)
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
          _RoundAction(
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

class _GoalProgressCard extends StatelessWidget {
  final RoleplayScenario scenario;
  final Map<String, dynamic> objectiveState;
  final int progress;
  final bool complete;

  const _GoalProgressCard({
    required this.scenario,
    required this.objectiveState,
    required this.progress,
    required this.complete,
  });

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      collapsedBackgroundColor: _card,
      backgroundColor: _card,
      iconColor: _primary,
      collapsedIconColor: _muted,
      tilePadding: const EdgeInsets.symmetric(horizontal: 16),
      childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
      title: Row(
        children: [
          Icon(
            complete ? Icons.verified_rounded : Icons.route_rounded,
            color: complete ? _success : _primary,
            size: 20,
          ),
          const SizedBox(width: 9),
          Expanded(
            child: Text(
              complete ? 'All goals complete' : 'Your goals',
              style: GoogleFonts.inter(
                color: _text,
                fontWeight: FontWeight.w700,
                fontSize: 13,
              ),
            ),
          ),
          Text(
            '$progress%',
            style: GoogleFonts.inter(
              color: complete ? _success : _primary,
              fontWeight: FontWeight.w800,
              fontSize: 13,
            ),
          ),
        ],
      ),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 8),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: progress / 100,
            minHeight: 5,
            color: complete ? _success : _primary,
            backgroundColor: _border,
          ),
        ),
      ),
      children: [
        for (final objective in scenario.objectives)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  _completed(objective.id)
                      ? Icons.check_circle_rounded
                      : Icons.radio_button_unchecked_rounded,
                  size: 17,
                  color: _completed(objective.id) ? _success : _muted,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    objective.label,
                    style: GoogleFonts.inter(
                      color: _completed(objective.id) ? _text : _muted,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }

  bool _completed(String id) {
    final value = objectiveState[id];
    return value is Map && value['completed'] == true;
  }
}

class _PartnerBubble extends StatelessWidget {
  final ChatMessage message;
  final VoidCallback onPlay;

  const _PartnerBubble({required this.message, required this.onPlay});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.sizeOf(context).width * .82,
        ),
        margin: const EdgeInsets.only(bottom: 14, right: 32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Container(
                  width: 31,
                  height: 31,
                  margin: const EdgeInsets.only(right: 8),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(colors: [_primary, _accent]),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(
                    Icons.forum_rounded,
                    color: Colors.white,
                    size: 17,
                  ),
                ),
                Expanded(
                  child: Container(
                    padding: const EdgeInsets.all(14),
                    decoration: const BoxDecoration(
                      color: _card,
                      borderRadius: BorderRadius.only(
                        topLeft: Radius.circular(15),
                        topRight: Radius.circular(15),
                        bottomRight: Radius.circular(15),
                        bottomLeft: Radius.circular(4),
                      ),
                    ),
                    child: Text(
                      message.text,
                      style: GoogleFonts.inter(
                        color: _text,
                        fontSize: 14,
                        height: 1.45,
                      ),
                    ),
                  ),
                ),
              ],
            ),
            if (message.audio != null)
              Padding(
                padding: const EdgeInsets.only(left: 39, top: 4),
                child: TextButton.icon(
                  onPressed: onPlay,
                  icon: const Icon(Icons.volume_up_rounded, size: 15),
                  label: const Text('Listen again'),
                  style: TextButton.styleFrom(
                    foregroundColor: _primary,
                    textStyle: GoogleFonts.inter(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _UserBubble extends StatelessWidget {
  final ChatMessage message;
  final VoidCallback onPlay;

  const _UserBubble({required this.message, required this.onPlay});

  bool get _hasCorrection {
    final corrected = message.correctedText?.trim();
    return corrected != null &&
        corrected.isNotEmpty &&
        corrected.toLowerCase() != message.text.trim().toLowerCase();
  }

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerRight,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.sizeOf(context).width * .82,
        ),
        margin: const EdgeInsets.only(bottom: 14, left: 32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    _primary.withValues(alpha: .9),
                    _accent.withValues(alpha: .85),
                  ],
                ),
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(15),
                  topRight: Radius.circular(15),
                  bottomLeft: Radius.circular(15),
                  bottomRight: Radius.circular(4),
                ),
              ),
              child: Text(
                message.text,
                style: GoogleFonts.inter(
                  color: Colors.white,
                  fontSize: 14,
                  height: 1.45,
                ),
              ),
            ),
            if (message.localAudioPath != null ||
                message.fluency != null ||
                _hasCorrection)
              Wrap(
                spacing: 6,
                crossAxisAlignment: WrapCrossAlignment.center,
                alignment: WrapAlignment.end,
                children: [
                  if (message.localAudioPath != null)
                    TextButton.icon(
                      onPressed: onPlay,
                      icon: const Icon(Icons.play_arrow_rounded, size: 15),
                      label: const Text('Replay'),
                      style: TextButton.styleFrom(
                        foregroundColor: _primary,
                        textStyle: GoogleFonts.inter(fontSize: 11),
                      ),
                    ),
                  if (message.fluency != null)
                    _MetricChip(
                      label: 'Fluency ${message.fluency}',
                      color: _accent,
                    ),
                  if (_hasCorrection)
                    Builder(
                      builder: (context) => TextButton.icon(
                        onPressed: () => _showCorrection(context),
                        icon: const Icon(
                          Icons.tips_and_updates_rounded,
                          size: 14,
                        ),
                        label: const Text('Language tip'),
                        style: TextButton.styleFrom(
                          foregroundColor: _warning,
                          textStyle: GoogleFonts.inter(fontSize: 11),
                        ),
                      ),
                    ),
                ],
              ),
          ],
        ),
      ),
    );
  }

  void _showCorrection(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: _surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'A clearer way to say it',
                style: GoogleFonts.inter(
                  color: _text,
                  fontSize: 17,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 13),
              Text(
                message.correctedText!,
                style: GoogleFonts.inter(
                  color: _success,
                  fontSize: 15,
                  height: 1.45,
                ),
              ),
              if (message.grammarFeedback?.trim().isNotEmpty == true) ...[
                const SizedBox(height: 10),
                Text(
                  message.grammarFeedback!,
                  style: GoogleFonts.inter(
                    color: _muted,
                    fontSize: 12,
                    height: 1.45,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _MetricChip extends StatelessWidget {
  final String label;
  final Color color;

  const _MetricChip({required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: .12),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: GoogleFonts.inter(
          color: color,
          fontSize: 10,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _ThinkingBubble extends StatelessWidget {
  const _ThinkingBubble();

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 14, right: 120),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        decoration: BoxDecoration(
          color: _card,
          borderRadius: BorderRadius.circular(15),
        ),
        child: Text(
          'Responding…',
          style: GoogleFonts.inter(color: _muted, fontSize: 12),
        ),
      ),
    );
  }
}

class _RoundAction extends StatelessWidget {
  final IconData icon;
  final String tooltip;
  final VoidCallback? onTap;
  final bool active;

  const _RoundAction({
    required this.icon,
    required this.tooltip,
    required this.onTap,
    this.active = false,
  });

  @override
  Widget build(BuildContext context) {
    return IconButton(
      tooltip: tooltip,
      onPressed: onTap,
      style: IconButton.styleFrom(
        backgroundColor: active ? _error : _cardInner,
        foregroundColor: onTap == null ? _muted : Colors.white,
        fixedSize: const Size(46, 46),
      ),
      icon: Icon(icon),
    );
  }
}

class _RecordingState extends StatelessWidget {
  final Animation<double> animation;

  const _RecordingState({required this.animation});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 48,
      padding: const EdgeInsets.symmetric(horizontal: 15),
      decoration: BoxDecoration(
        color: _error.withValues(alpha: .1),
        borderRadius: BorderRadius.circular(15),
        border: Border.all(color: _error.withValues(alpha: .35)),
      ),
      child: Row(
        children: [
          FadeTransition(
            opacity: animation,
            child: const Icon(Icons.circle, color: _error, size: 10),
          ),
          const SizedBox(width: 9),
          Text(
            'Recording your turn…',
            style: GoogleFonts.inter(
              color: _text,
              fontSize: 13,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _LanguageHelpSheet extends StatefulWidget {
  final List<RoleplayObjective> objectives;
  final List<String> phrases;
  final ValueChanged<String> onSelect;

  const _LanguageHelpSheet({
    required this.objectives,
    required this.phrases,
    required this.onSelect,
  });

  @override
  State<_LanguageHelpSheet> createState() => _LanguageHelpSheetState();
}

class _LanguageHelpSheetState extends State<_LanguageHelpSheet> {
  final TextEditingController _arabicController = TextEditingController();
  List<RoleplayEscapeOption> _options = const [];
  bool _loading = false;
  String? _errorMessage;

  Future<void> _generateOptions() async {
    final source = _arabicController.text.trim();
    if (source.isEmpty || _loading) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _loading = true;
      _errorMessage = null;
      _options = const [];
    });
    try {
      final result = await ApiService.getArabicTranslationOptions(
        arabicText: source,
      );
      final rawOptions = result['options'];
      if (rawOptions is! List) {
        throw const FormatException('Missing English options');
      }
      final options = rawOptions
          .whereType<Map>()
          .map(
            (item) =>
                RoleplayEscapeOption.fromJson(Map<String, dynamic>.from(item)),
          )
          .where((item) => item.text.isNotEmpty)
          .toList(growable: false);
      if (options.length != 3) {
        throw const FormatException('Expected three English options');
      }
      if (mounted) setState(() => _options = options);
    } catch (error) {
      if (mounted) {
        final detail = error.toString().toLowerCase();
        final serviceUnavailable =
            detail.contains('connection refused') ||
            detail.contains('failed host lookup') ||
            detail.contains('clientexception') ||
            detail.contains('socketexception') ||
            detail.contains('timed out');
        setState(
          () => _errorMessage = serviceUnavailable
              ? 'The learning service is offline. Reconnect the backend, then try again.'
              : 'I could not create the English options. Please try again.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _arabicController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: AnimatedPadding(
        duration: const Duration(milliseconds: 180),
        padding: EdgeInsets.only(
          bottom: MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxHeight: MediaQuery.sizeOf(context).height * .82,
          ),
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    width: 42,
                    height: 4,
                    decoration: BoxDecoration(
                      color: _muted.withValues(alpha: .4),
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
                ),
                const SizedBox(height: 18),
                Text(
                  'Say what you mean',
                  style: GoogleFonts.inter(
                    color: _text,
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  widget.objectives.isEmpty
                      ? 'All goals complete. Keep chatting freely, or end whenever you’re ready.'
                      : 'Next goal: ${widget.objectives.first.label}',
                  style: GoogleFonts.inter(
                    color: _muted,
                    fontSize: 12,
                    height: 1.45,
                  ),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _arabicController,
                  minLines: 2,
                  maxLines: 4,
                  textDirection: TextDirection.rtl,
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) => _generateOptions(),
                  style: GoogleFonts.inter(color: _text, fontSize: 14),
                  decoration: InputDecoration(
                    hintText: 'اكتب ما تريد قوله بالعربية',
                    hintTextDirection: TextDirection.rtl,
                    hintStyle: GoogleFonts.inter(color: _muted),
                    filled: true,
                    fillColor: _card,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(14),
                      borderSide: const BorderSide(color: _border),
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(14),
                      borderSide: const BorderSide(color: _border),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(14),
                      borderSide: const BorderSide(color: _primary),
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: _loading ? null : _generateOptions,
                    style: FilledButton.styleFrom(
                      backgroundColor: _primary,
                      foregroundColor: Colors.white,
                      disabledBackgroundColor: _primary.withValues(alpha: .45),
                      padding: const EdgeInsets.symmetric(vertical: 13),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(13),
                      ),
                    ),
                    icon: _loading
                        ? const SizedBox.square(
                            dimension: 17,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.translate_rounded, size: 19),
                    label: Text(
                      _loading ? 'Creating options…' : 'Show me 3 ways',
                    ),
                  ),
                ),
                if (_errorMessage != null) ...[
                  const SizedBox(height: 10),
                  Text(
                    _errorMessage!,
                    style: GoogleFonts.inter(color: _error, fontSize: 12),
                  ),
                ],
                if (_options.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  for (final option in _options)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 9),
                      child: Material(
                        color: _card,
                        borderRadius: BorderRadius.circular(14),
                        child: InkWell(
                          borderRadius: BorderRadius.circular(14),
                          onTap: () {
                            widget.onSelect(option.text);
                            Navigator.pop(context);
                          },
                          child: Padding(
                            padding: const EdgeInsets.all(14),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 8,
                                    vertical: 4,
                                  ),
                                  decoration: BoxDecoration(
                                    color: _primary.withValues(alpha: .14),
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                  child: Text(
                                    option.label,
                                    style: GoogleFonts.inter(
                                      color: _primary,
                                      fontSize: 10,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Text(
                                    option.text,
                                    style: GoogleFonts.inter(
                                      color: _text,
                                      fontSize: 13,
                                      height: 1.4,
                                    ),
                                  ),
                                ),
                                const Icon(
                                  Icons.north_west_rounded,
                                  color: _muted,
                                  size: 17,
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                ],
                if (widget.phrases.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Text(
                    'Or use a sentence starter',
                    style: GoogleFonts.inter(
                      color: _muted,
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 4),
                  for (final phrase in widget.phrases)
                    ListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      leading: const Icon(
                        Icons.arrow_forward_rounded,
                        color: _primary,
                        size: 18,
                      ),
                      title: Text(
                        phrase,
                        style: GoogleFonts.inter(color: _text, fontSize: 14),
                      ),
                      subtitle: Text(
                        'Tap to use as a sentence starter',
                        style: GoogleFonts.inter(color: _muted, fontSize: 10),
                      ),
                      onTap: () {
                        widget.onSelect('$phrase ');
                        Navigator.pop(context);
                      },
                    ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _StartError extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _StartError({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off_rounded, color: _muted, size: 42),
            const SizedBox(height: 14),
            Text(
              'Could not start the roleplay',
              style: GoogleFonts.inter(
                color: _text,
                fontSize: 17,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 7),
            Text(
              message,
              textAlign: TextAlign.center,
              style: GoogleFonts.inter(color: _muted, fontSize: 12),
            ),
            const SizedBox(height: 18),
            FilledButton(
              onPressed: onRetry,
              style: FilledButton.styleFrom(backgroundColor: _primary),
              child: const Text('Try again'),
            ),
          ],
        ),
      ),
    );
  }
}
