import 'dart:convert';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:go_router/go_router.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../../core/services/api_service.dart';

// ─────────────────────────────────────────────
// Colors
// ─────────────────────────────────────────────

const _background    = Color(0xFF090E1A);
const _surface       = Color(0xFF111827);
const _surfaceCard   = Color(0xFF1A2235);
// ignore: unused_element
const _surfaceCard2  = Color(0xFF1E2D45);
const _primary       = Color(0xFF4F7FFF);
const _accent        = Color(0xFF8B5CF6);
const _success       = Color(0xFF22C55E);
const _warning       = Color(0xFFF59E0B);
const _error         = Color(0xFFEF4444);
const _textPrimary   = Color(0xFFF1F5FF);
const _textSecondary = Color(0xFF8896B0);
const _border        = Color(0xFF1E2D45);

// ─────────────────────────────────────────────
// Data models
// ─────────────────────────────────────────────

class ChatMessage {
  final bool isUser;
  final String text;
  final int? score;
  final String? hint;

  const ChatMessage({
    required this.isUser,
    required this.text,
    this.score,
    this.hint,
  });
}

// ─────────────────────────────────────────────
// Mock messages
// ─────────────────────────────────────────────

const List<ChatMessage> _mockMessages = [
  ChatMessage(
    isUser: false,
    text: 'Good morning! Welcome to Heathrow Airport. May I see your passport?',
  ),
  ChatMessage(
    isUser: true,
    text: 'Good morning! Here is my passport. I am checking in for New York.',
    score: 82,
    hint: 'Great! Try linking checking in more smoothly.',
  ),
  ChatMessage(
    isUser: false,
    text: 'Do you have bags to check? Window or aisle seat?',
  ),
  ChatMessage(
    isUser: true,
    text: 'I have one bag for check. And I want window seat please.',
    score: 64,
    hint: "Say 'to check in' not 'for check'. Add article: 'a window seat'.",
  ),
  ChatMessage(
    isUser: false,
    text: 'I assigned seat 14A - a window seat. Flight boards at Gate 22 in two hours.',
  ),
];

// ─────────────────────────────────────────────
// Chat Screen
// ─────────────────────────────────────────────

class ChatScreen extends StatefulWidget {
  final String roleplaysTitle;

  const ChatScreen({super.key, required this.roleplaysTitle});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> with TickerProviderStateMixin {
  final TextEditingController _textCtrl = TextEditingController();
  final ScrollController _scrollCtrl = ScrollController();

  late List<ChatMessage> _messages;
  final Set<int> _translatedIndices = {};
  bool _isRecording = false;
  bool _isWaitingForReply = false;

  late AnimationController _waveController;
  WebSocketChannel? _wsChannel;
  bool _wsConnected = false;

  @override
  void initState() {
    super.initState();
    _messages = [];
    _waveController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    )..repeat(reverse: true);
    _connectWebSocket();
    // Add initial AI greeting
    _messages.add(ChatMessage(
      isUser: false,
      text: 'Hello! I\'m your conversation partner for the "${widget.roleplaysTitle}" scenario. Let\'s practice! Say something to get started.',
    ));
  }

  void _connectWebSocket() {
    try {
      _wsChannel = WebSocketChannel.connect(
        Uri.parse('${ApiService.wsUrl}/ws/chat'),
      );
      _wsConnected = true;
      _wsChannel!.stream.listen(
        (message) {
          if (!mounted) return;
          try {
            final data = jsonDecode(message as String);
            setState(() {
              _isWaitingForReply = false;
              // AI reply
              _messages.add(ChatMessage(
                isUser: false,
                text: data['text']?.toString() ?? data['reply']?.toString() ?? 'I didn\'t catch that.',
              ));
              // If there's grammar feedback on the user's last message, update it
              final grammarFeedback = data['grammar_feedback']?.toString();
              if (grammarFeedback != null && grammarFeedback != 'Correct' && grammarFeedback.isNotEmpty) {
                // Find last user message and add hint
                for (int i = _messages.length - 1; i >= 0; i--) {
                  if (_messages[i].isUser && _messages[i].hint == null) {
                    _messages[i] = ChatMessage(
                      isUser: true,
                      text: _messages[i].text,
                      score: _messages[i].score,
                      hint: grammarFeedback,
                    );
                    break;
                  }
                }
              }
            });
            _scrollToBottom();
          } catch (e) {
            // Non-JSON message (could be audio bytes)
          }
        },
        onError: (e) {
          if (mounted) setState(() => _wsConnected = false);
        },
        onDone: () {
          if (mounted) setState(() => _wsConnected = false);
        },
      );
    } catch (e) {
      _wsConnected = false;
    }
  }

  @override
  void dispose() {
    _wsChannel?.sink.close();
    _waveController.dispose();
    _textCtrl.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(
          _scrollCtrl.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  // ── Translation ───────────────────────────

  void _toggleTranslation(int idx) {
    setState(() {
      if (_translatedIndices.contains(idx)) {
        _translatedIndices.remove(idx);
      } else {
        _translatedIndices.add(idx);
      }
    });
  }

  // ── Mic / Recording ──────────────────────

  void _toggleRecording() {
    setState(() {
      if (_isRecording) {
        _isRecording = false;
        // Simulate "sending" recorded message
        _messages.add(const ChatMessage(
          isUser: true,
          text: '(Voice message sent)',
          score: 75,
          hint: 'Keep practising your pronunciation!',
        ));
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (_scrollCtrl.hasClients) {
            _scrollCtrl.animateTo(
              _scrollCtrl.position.maxScrollExtent,
              duration: const Duration(milliseconds: 300),
              curve: Curves.easeOut,
            );
          }
        });
      } else {
        _isRecording = true;
      }
    });
  }

  // ── Send text ────────────────────────────

  void _sendText() {
    final text = _textCtrl.text.trim();
    if (text.isEmpty) return;
    setState(() {
      _messages.add(ChatMessage(isUser: true, text: text, score: null));
      _textCtrl.clear();
      _isWaitingForReply = true;
    });
    _scrollToBottom();

    // Send to backend via WebSocket
    if (_wsConnected && _wsChannel != null) {
      try {
        _wsChannel!.sink.add(jsonEncode({'text': text}));
      } catch (e) {
        setState(() {
          _isWaitingForReply = false;
          _messages.add(const ChatMessage(
            isUser: false,
            text: 'Connection lost. Please try again.',
          ));
        });
      }
    } else {
      // Offline fallback
      setState(() {
        _isWaitingForReply = false;
        _messages.add(const ChatMessage(
          isUser: false,
          text: 'Backend not connected. Start the server with: python backend/main.py',
        ));
      });
    }
  }

  // ── Escape Route bottom sheet ─────────────

  void _openEscapeRoute() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: _surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      builder: (_) => _EscapeRouteSheet(
        onOptionSelected: (text) {
          setState(() => _textCtrl.text = text);
        },
      ),
    );
  }

  // ─────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _background,
      appBar: _buildAppBar(),
      body: Column(
        children: [
          Expanded(child: _buildMessageList()),
          _buildInputBar(),
        ],
      ),
    );
  }

  AppBar _buildAppBar() {
    return AppBar(
      backgroundColor: _surface,
      elevation: 0,
      leading: IconButton(
        icon: const Icon(Icons.arrow_back_ios_new_rounded, color: _textPrimary, size: 20),
        onPressed: () {
          if (context.canPop()) {
            context.pop();
          } else {
            context.go('/chat');
          }
        },
      ),
      title: Text(
        widget.roleplaysTitle,
        style: GoogleFonts.inter(
          color: _textPrimary,
          fontWeight: FontWeight.w700,
          fontSize: 17,
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => context.go('/chat/feedback'),
          child: Text(
            'End Session',
            style: GoogleFonts.inter(
              color: _error,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
      bottom: PreferredSize(
        preferredSize: const Size.fromHeight(1),
        child: Container(height: 1, color: _border),
      ),
    );
  }

  Widget _buildMessageList() {
    return ListView.builder(
      controller: _scrollCtrl,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      itemCount: _messages.length + (_isWaitingForReply ? 1 : 0),
      itemBuilder: (ctx, idx) {
        // Typing indicator at the end
        if (idx == _messages.length && _isWaitingForReply) {
          return Align(
            alignment: Alignment.centerLeft,
            child: Container(
              margin: const EdgeInsets.only(top: 8, right: 80),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: _surfaceCard,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(20),
                  topRight: Radius.circular(20),
                  bottomRight: Radius.circular(20),
                  bottomLeft: Radius.circular(6),
                ),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: List.generate(3, (i) =>
                  Container(
                    width: 8,
                    height: 8,
                    margin: const EdgeInsets.symmetric(horizontal: 2),
                    decoration: BoxDecoration(
                      color: _primary.withValues(alpha: 0.6),
                      shape: BoxShape.circle,
                    ),
                  )
                      .animate(onPlay: (c) => c.repeat(reverse: true))
                      .scale(
                        begin: const Offset(0.6, 0.6),
                        end: const Offset(1.2, 1.2),
                        delay: Duration(milliseconds: 150 * i),
                        duration: 500.ms,
                      ),
                ),
              ),
            ),
          ).animate().fadeIn(duration: 200.ms);
        }
        final msg = _messages[idx];
        final isTranslated = _translatedIndices.contains(idx);
        return msg.isUser
            ? _UserBubble(
                message: msg,
                isTranslated: isTranslated,
                onTranslateTap: () => _toggleTranslation(idx),
              ).animate().fadeIn(duration: 300.ms).slideX(begin: 0.05, end: 0)
            : _AIBubble(
                message: msg,
                isTranslated: isTranslated,
                onTranslateTap: () => _toggleTranslation(idx),
              ).animate().fadeIn(duration: 300.ms).slideX(begin: -0.05, end: 0);
      },
    );
  }

  Widget _buildInputBar() {
    return Container(
      color: _surface,
      padding: EdgeInsets.only(
        left: 12,
        right: 12,
        top: 10,
        bottom: MediaQuery.of(context).padding.bottom + 10,
      ),
      child: Row(
        children: [
          // Wand / Escape route button
          _GradientCircleBtn(
            icon: Icons.auto_awesome_rounded,
            onTap: _openEscapeRoute,
          ),
          const SizedBox(width: 10),
          // Text field
          Expanded(
            child: _isRecording
                ? _WaveformIndicator(controller: _waveController)
                : TextField(
                    controller: _textCtrl,
                    style: GoogleFonts.inter(color: _textPrimary),
                    onSubmitted: (_) => _sendText(),
                    decoration: InputDecoration(
                      hintText: 'Type a message…',
                      hintStyle: GoogleFonts.inter(color: _textSecondary, fontSize: 14),
                      filled: true,
                      fillColor: _surfaceCard,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(14),
                        borderSide: BorderSide.none,
                      ),
                      suffixIcon: IconButton(
                        icon: const Icon(Icons.send_rounded, color: _primary, size: 20),
                        onPressed: _sendText,
                      ),
                    ),
                  ),
          ),
          const SizedBox(width: 10),
          // Mic button
          _GradientCircleBtn(
            icon: _isRecording ? Icons.stop_rounded : Icons.mic_rounded,
            onTap: _toggleRecording,
            isActive: _isRecording,
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────
// AI Bubble
// ─────────────────────────────────────────────

class _AIBubble extends StatelessWidget {
  final ChatMessage message;
  final bool isTranslated;
  final VoidCallback onTranslateTap;

  const _AIBubble({
    required this.message,
    required this.isTranslated,
    required this.onTranslateTap,
  });

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 14),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Avatar + bubble
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Container(
                  width: 32,
                  height: 32,
                  margin: const EdgeInsets.only(right: 8),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [_primary, _accent],
                    ),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.smart_toy_rounded, color: Colors.white, size: 18),
                ),
                Expanded(
                  child: Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: _surfaceCard,
                      borderRadius: const BorderRadius.only(
                        topLeft: Radius.circular(12),
                        topRight: Radius.circular(12),
                        bottomRight: Radius.circular(12),
                        bottomLeft: Radius.circular(4),
                      ),
                    ),
                    child: Text(
                      message.text,
                      style: GoogleFonts.inter(color: Colors.white, fontSize: 14, height: 1.5),
                    ),
                  ),
                ),
              ],
            ),
            // Translate and Replay row
            Padding(
              padding: const EdgeInsets.only(left: 40, top: 4),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  GestureDetector(
                    onTap: onTranslateTap,
                    child: Row(
                      children: [
                        Icon(Icons.language_rounded, size: 14, color: _primary.withOpacity(0.8)),
                        const SizedBox(width: 4),
                        Text(
                          isTranslated ? 'Hide' : 'Translate',
                          style: GoogleFonts.inter(color: _primary, fontSize: 11, fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 16),
                  GestureDetector(
                    onTap: () {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Playing AI voice...')),
                      );
                    },
                    child: Row(
                      children: [
                        Icon(Icons.replay_rounded, size: 14, color: _primary.withOpacity(0.8)),
                        const SizedBox(width: 4),
                        Text(
                          'Replay',
                          style: GoogleFonts.inter(color: _primary, fontSize: 11, fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            if (isTranslated)
              Padding(
                padding: const EdgeInsets.only(left: 40, top: 4, right: 8),
                child: Text(
                  'صباح الخير! مرحباً بك في مطار هيثرو. هل يمكنني رؤية جواز سفرك؟',
                  style: GoogleFonts.cairo(
                    color: _textSecondary,
                    fontSize: 13,
                    fontStyle: FontStyle.italic,
                  ),
                  textDirection: TextDirection.rtl,
                ).animate().fadeIn(duration: 300.ms),
              ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// User Bubble
// ─────────────────────────────────────────────

class _UserBubble extends StatelessWidget {
  final ChatMessage message;
  final bool isTranslated;
  final VoidCallback onTranslateTap;

  const _UserBubble({
    required this.message,
    required this.isTranslated,
    required this.onTranslateTap,
  });

  Color get _bgColor {
    final score = message.score ?? 0;
    if (score > 80) return _success.withOpacity(0.15);
    if (score >= 50) return _warning.withOpacity(0.15);
    return _error.withOpacity(0.15);
  }

  Color get _borderColor {
    final score = message.score ?? 0;
    if (score > 80) return _success;
    if (score >= 50) return _warning;
    return _error;
  }

  String get _scoreLabel {
    final score = message.score ?? 0;
    if (score > 80) return '😊 $score';
    if (score >= 50) return '😐 $score';
    return '😟 $score';
  }

  Widget _buildColoredText(String text, int? averageScore) {
    if (averageScore == null) {
      return Text(
        text,
        style: GoogleFonts.inter(color: _textPrimary, fontSize: 14, height: 1.5),
        textAlign: TextAlign.end,
      );
    }
    final words = text.split(' ');
    return RichText(
      textAlign: TextAlign.end,
      text: TextSpan(
        children: words.map((w) {
          int wordScore = (averageScore + w.length * 3) % 100;
          if (wordScore < 30) wordScore += 30;
          
          Color wColor = _success;
          if (wordScore < 50) wColor = _error;
          else if (wordScore < 80) wColor = _warning;
          
          return TextSpan(
            text: '$w ',
            style: GoogleFonts.inter(color: wColor, fontSize: 14, height: 1.5, fontWeight: FontWeight.w600),
          );
        }).toList(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerRight,
      child: Container(
        margin: const EdgeInsets.only(bottom: 14),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            // Bubble with left colour strip
            ClipRRect(
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(12),
                topRight: Radius.circular(12),
                bottomLeft: Radius.circular(12),
                bottomRight: Radius.circular(4),
              ),
              child: Container(
                decoration: BoxDecoration(
                  color: _bgColor,
                  border: Border(left: BorderSide(color: _borderColor, width: 3.5)),
                ),
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      _buildColoredText(message.text, message.score),
                      if (message.score != null) ...[
                        const SizedBox(height: 6),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: _borderColor.withOpacity(0.2),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            _scoreLabel,
                            style: GoogleFonts.inter(
                              color: _borderColor,
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
            // Translate and Replay row directly under message, ABOVE hint
            Padding(
              padding: const EdgeInsets.only(top: 4, right: 2, bottom: 4),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  GestureDetector(
                    onTap: () {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Playing user voice recording...')),
                      );
                    },
                    child: Row(
                      children: [
                        Icon(Icons.replay_rounded, size: 14, color: _primary.withOpacity(0.8)),
                        const SizedBox(width: 4),
                        Text(
                          'Replay',
                          style: GoogleFonts.inter(color: _primary, fontSize: 11, fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 16),
                  GestureDetector(
                    onTap: onTranslateTap,
                    child: Row(
                      children: [
                        Icon(Icons.language_rounded, size: 14, color: _primary.withOpacity(0.8)),
                        const SizedBox(width: 4),
                        Text(
                          isTranslated ? 'Hide' : 'Translate',
                          style: GoogleFonts.inter(color: _primary, fontSize: 11, fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            // Hint text
            if (message.hint != null)
              Padding(
                padding: const EdgeInsets.only(top: 2, right: 4, left: 20),
                child: Text(
                  '💡 ${message.hint}',
                  style: GoogleFonts.inter(
                    color: _textSecondary,
                    fontSize: 11,
                    fontStyle: FontStyle.italic,
                    height: 1.4,
                  ),
                  textAlign: TextAlign.end,
                ),
              ),
            if (isTranslated)
              Padding(
                padding: const EdgeInsets.only(top: 4, right: 4, left: 20),
                child: Text(
                  'صباح الخير! هذا جواز سفري. أنا أسجّل للسفر إلى نيويورك.',
                  style: GoogleFonts.cairo(
                    color: _textSecondary,
                    fontSize: 13,
                    fontStyle: FontStyle.italic,
                  ),
                  textAlign: TextAlign.end,
                  textDirection: TextDirection.rtl,
                ).animate().fadeIn(duration: 300.ms),
              ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Waveform indicator
// ─────────────────────────────────────────────

class _WaveformIndicator extends StatelessWidget {
  final AnimationController controller;
  const _WaveformIndicator({required this.controller});

  @override
  Widget build(BuildContext context) {
    final heights = [18.0, 28.0, 38.0, 24.0, 32.0, 20.0, 34.0];
    return Container(
      height: 48,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.circle, color: _error, size: 8),
          const SizedBox(width: 10),
          ...List.generate(heights.length, (i) {
            return AnimatedBuilder(
              animation: controller,
              builder: (_, __) {
                final t = (controller.value + i * 0.14) % 1.0;
                final h = heights[i] * (0.5 + 0.5 * math.sin(t * math.pi * 2));
                return Container(
                  width: 4,
                  height: h,
                  margin: const EdgeInsets.symmetric(horizontal: 2),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [_primary, _accent],
                      begin: Alignment.bottomCenter,
                      end: Alignment.topCenter,
                    ),
                    borderRadius: BorderRadius.circular(2),
                  ),
                );
              },
            );
          }),
          const SizedBox(width: 10),
          Text(
            'Recording…',
            style: GoogleFonts.inter(color: _textSecondary, fontSize: 13),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Gradient circle button
// ─────────────────────────────────────────────

class _GradientCircleBtn extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;
  final bool isActive;

  const _GradientCircleBtn({
    required this.icon,
    required this.onTap,
    this.isActive = false,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 46,
        height: 46,
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: isActive ? [_error, const Color(0xFFFF6B6B)] : [_primary, _accent],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(14),
          boxShadow: [
            BoxShadow(
              color: (isActive ? _error : _primary).withOpacity(0.35),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Icon(icon, color: Colors.white, size: 22),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Escape Route Bottom Sheet
// ─────────────────────────────────────────────

class _EscapeRouteSheet extends StatefulWidget {
  final void Function(String) onOptionSelected;
  const _EscapeRouteSheet({required this.onOptionSelected});

  @override
  State<_EscapeRouteSheet> createState() => _EscapeRouteSheetState();
}

class _EscapeRouteSheetState extends State<_EscapeRouteSheet> {
  final TextEditingController _ctrl = TextEditingController();
  bool _showOptions = false;

  final List<Map<String, String>> _options = [
    {'style': 'Casual', 'text': 'Hi, can I check in please?', 'icon': '😊'},
    {'style': 'Polite', 'text': 'Excuse me, I would like to check in.', 'icon': '🎩'},
    {'style': 'Technical', 'text': 'I am here to complete the check-in process for my flight.', 'icon': '📋'},
  ];

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Handle
            Center(
              child: Container(
                width: 40,
                height: 4,
                margin: const EdgeInsets.only(bottom: 16),
                decoration: BoxDecoration(
                  color: _border,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            // Title row
            Row(
              children: [
                const Text('🪄', style: TextStyle(fontSize: 22)),
                const SizedBox(width: 8),
                Text(
                  'Escape Route',
                  style: GoogleFonts.inter(
                    color: _textPrimary,
                    fontWeight: FontWeight.w700,
                    fontSize: 18,
                  ),
                ),
                const Spacer(),
                IconButton(
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.close_rounded, color: _textSecondary),
                ),
              ],
            ),
            Text(
              'Type what you want to say in Arabic',
              style: GoogleFonts.inter(color: _textSecondary, fontSize: 13),
            ),
            const SizedBox(height: 14),
            // Arabic input
            TextField(
              controller: _ctrl,
              textDirection: TextDirection.rtl,
              style: GoogleFonts.cairo(color: _textPrimary),
              decoration: InputDecoration(
                hintText: 'اكتب ما تريد قوله…',
                hintStyle: GoogleFonts.cairo(color: _textSecondary),
                hintTextDirection: TextDirection.rtl,
                filled: true,
                fillColor: _surfaceCard,
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
            const SizedBox(height: 12),
            // Translate button
            SizedBox(
              width: double.infinity,
              child: GestureDetector(
                onTap: () => setState(() => _showOptions = true),
                child: Container(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(colors: [_primary, _accent]),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    'Translate',
                    style: GoogleFonts.inter(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                      fontSize: 15,
                    ),
                  ),
                ),
              ),
            ),
            // Options
            if (_showOptions) ...[
              const SizedBox(height: 16),
              Text(
                'Choose a style:',
                style: GoogleFonts.inter(
                  color: _textSecondary,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 10),
              ..._options.asMap().entries.map((e) {
                final opt = e.value;
                return GestureDetector(
                  onTap: () {
                    widget.onOptionSelected(opt['text']!);
                    Navigator.pop(context);
                  },
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 8),
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: _surfaceCard,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: _border),
                    ),
                    child: Row(
                      children: [
                        Text(opt['icon']!, style: const TextStyle(fontSize: 18)),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                opt['style']!,
                                style: GoogleFonts.inter(
                                  color: _primary,
                                  fontSize: 11,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                              Text(
                                opt['text']!,
                                style: GoogleFonts.inter(color: _textPrimary, fontSize: 13),
                              ),
                            ],
                          ),
                        ),
                        const Icon(Icons.chevron_right_rounded, color: _textSecondary, size: 18),
                      ],
                    ),
                  ).animate(delay: Duration(milliseconds: e.key * 80)).fadeIn().slideY(begin: 0.05, end: 0),
                );
              }),
            ],
          ],
        ),
      ),
    );
  }
}
