import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:just_talk/core/theme/local_fonts.dart';

import '../../core/services/api_service.dart';
import 'roleplay_models.dart';

const _background = Color(0xFF090E1A);
const _surface = Color(0xFF111827);
const _card = Color(0xFF1A2235);
const _primary = Color(0xFF4F7FFF);
const _accent = Color(0xFF8B5CF6);
const _text = Color(0xFFF1F5FF);
const _muted = Color(0xFF8896B0);
const _border = Color(0xFF263550);

typedef RoleplayTranscriptLoader =
    Future<Map<String, dynamic>> Function(String clientSessionId);

class RoleplayHistoryScreen extends StatefulWidget {
  final RoleplayHistoryArgs args;
  final RoleplayTranscriptLoader? loader;

  const RoleplayHistoryScreen({super.key, required this.args, this.loader});

  @override
  State<RoleplayHistoryScreen> createState() => _RoleplayHistoryScreenState();
}

class _RoleplayHistoryScreenState extends State<RoleplayHistoryScreen> {
  RoleplayTranscript? _transcript;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final loader = widget.loader ?? ApiService.getRoleplayTranscript;
      final value = await loader(widget.args.clientSessionId);
      final transcript = RoleplayTranscript.fromJson(value);
      if (!transcript.readOnly) {
        throw const FormatException('Transcript is not read-only');
      }
      if (!mounted) return;
      setState(() {
        _transcript = transcript;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'This saved conversation could not be loaded.';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _background,
      appBar: AppBar(
        backgroundColor: _surface,
        elevation: 0,
        leading: IconButton(
          tooltip: 'Back',
          onPressed: context.pop,
          icon: const Icon(Icons.arrow_back_ios_new_rounded, color: _text),
        ),
        title: Text(
          widget.args.title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: GoogleFonts.inter(
            color: _text,
            fontSize: 17,
            fontWeight: FontWeight.w700,
          ),
        ),
        bottom: const PreferredSize(
          preferredSize: Size.fromHeight(1),
          child: Divider(height: 1, color: _border),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: _primary))
          : _error != null
          ? _ErrorState(message: _error!, onRetry: _load)
          : _TranscriptBody(transcript: _transcript!),
    );
  }
}

class _TranscriptBody extends StatelessWidget {
  final RoleplayTranscript transcript;

  const _TranscriptBody({required this.transcript});

  @override
  Widget build(BuildContext context) {
    final session = transcript.session;
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
      children: [
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: _card,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: _border),
          ),
          child: Row(
            children: [
              Container(
                width: 38,
                height: 38,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: _primary.withValues(alpha: .14),
                  borderRadius: BorderRadius.circular(11),
                ),
                child: const Icon(
                  Icons.history_rounded,
                  color: _primary,
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Saved conversation · Read-only',
                      style: GoogleFonts.inter(
                        color: _text,
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      '${transcript.turns.length} turns · ${session['duration_seconds'] ?? 0}s',
                      style: GoogleFonts.inter(color: _muted, fontSize: 11),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.lock_outline_rounded, color: _muted, size: 18),
            ],
          ),
        ),
        const SizedBox(height: 20),
        _TranscriptBubble(
          text: transcript.scenario.opening,
          label: transcript.scenario.aiRole,
          learner: false,
        ),
        for (final turn in transcript.turns) ...[
          _TranscriptBubble(
            text: turn.userText,
            label: transcript.scenario.learnerRole,
            learner: true,
            audioTurn: turn.inputMode == 'audio',
          ),
          _TranscriptBubble(
            text: turn.assistantText,
            label: transcript.scenario.aiRole,
            learner: false,
          ),
        ],
      ],
    );
  }
}

class _TranscriptBubble extends StatelessWidget {
  final String text;
  final String label;
  final bool learner;
  final bool audioTurn;

  const _TranscriptBubble({
    required this.text,
    required this.label,
    required this.learner,
    this.audioTurn = false,
  });

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: learner ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.sizeOf(context).width * .82,
        ),
        margin: EdgeInsets.only(
          left: learner ? 34 : 0,
          right: learner ? 0 : 34,
          bottom: 14,
        ),
        padding: const EdgeInsets.fromLTRB(14, 10, 14, 12),
        decoration: BoxDecoration(
          color: learner ? _primary : _card,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(17),
            topRight: const Radius.circular(17),
            bottomLeft: Radius.circular(learner ? 17 : 4),
            bottomRight: Radius.circular(learner ? 4 : 17),
          ),
          border: learner ? null : Border.all(color: _border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (audioTurn) ...[
                  const Icon(
                    Icons.mic_rounded,
                    color: Colors.white70,
                    size: 12,
                  ),
                  const SizedBox(width: 4),
                ],
                Flexible(
                  child: Text(
                    label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: GoogleFonts.inter(
                      color: learner
                          ? Colors.white70
                          : _accent.withValues(alpha: .9),
                      fontSize: 9,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 5),
            Text(
              text,
              style: GoogleFonts.inter(
                color: _text,
                fontSize: 14,
                height: 1.45,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  final String message;
  final Future<void> Function() onRetry;

  const _ErrorState({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.history_toggle_off_rounded,
              color: _muted,
              size: 42,
            ),
            const SizedBox(height: 12),
            Text(
              message,
              textAlign: TextAlign.center,
              style: GoogleFonts.inter(color: _muted),
            ),
            const SizedBox(height: 14),
            OutlinedButton(onPressed: onRetry, child: const Text('Try again')),
          ],
        ),
      ),
    );
  }
}
