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

part 'chat_session_controller.dart';
part 'chat_interaction_controller.dart';
part 'chat_input_widgets.dart';

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
  void _update(VoidCallback change) => setState(change);

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
}
