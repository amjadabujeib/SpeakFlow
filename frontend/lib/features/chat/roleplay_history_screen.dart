import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:speakflow/core/theme/local_fonts.dart';

import '../../app/providers.dart';
import 'roleplay_confidence_transcript.dart';
import 'roleplay_message_bubbles.dart';
import 'roleplay_models.dart';

const _background = Color(0xFF090E1A);
const _surface = Color(0xFF111827);
const _primary = Color(0xFF4F7FFF);
const _accent = Color(0xFF8B5CF6);
const _text = Color(0xFFF1F5FF);
const _muted = Color(0xFF8896B0);
const _border = Color(0xFF263550);

typedef RoleplayTranscriptLoader =
    Future<Map<String, dynamic>> Function(String clientSessionId);

class RoleplayHistoryScreen extends ConsumerStatefulWidget {
  final RoleplayHistoryArgs args;
  final RoleplayTranscriptLoader? loader;

  const RoleplayHistoryScreen({super.key, required this.args, this.loader});

  @override
  ConsumerState<RoleplayHistoryScreen> createState() =>
      _RoleplayHistoryScreenState();
}

class _RoleplayHistoryScreenState extends ConsumerState<RoleplayHistoryScreen> {
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
      final loader = widget.loader ?? ref.read(roleplayApiProvider).transcript;
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
      body: SafeArea(
        top: false,
        child: _loading
            ? const Center(child: CircularProgressIndicator(color: _primary))
            : _error != null
            ? _ErrorState(message: _error!, onRetry: _load)
            : _TranscriptBody(transcript: _transcript!),
      ),
    );
  }
}

class _TranscriptBody extends StatelessWidget {
  final RoleplayTranscript transcript;

  const _TranscriptBody({required this.transcript});

  @override
  Widget build(BuildContext context) {
    final hasWordConfidence = transcript.turns.any(
      (turn) => turn.wordConfidence.any((word) => word['score'] is num),
    );
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 32),
      children: [
        _HistorySessionHeader(
          transcript: transcript,
          showConfidenceLegend: hasWordConfidence,
        ),
        const SizedBox(height: 22),
        RoleplayPartnerMessageBubble(text: transcript.scenario.opening),
        for (final turn in transcript.turns) ...[
          RoleplayUserMessageBubble(
            text: turn.userText,
            correctedText: turn.correctedText,
            grammarFeedback: turn.grammarFeedback,
            wordConfidence: turn.wordConfidence,
            transcriptKey: ValueKey(
              'history-confidence-transcript-${turn.turnId}',
            ),
          ),
          RoleplayPartnerMessageBubble(text: turn.assistantText),
        ],
      ],
    );
  }
}

class _HistorySessionHeader extends StatelessWidget {
  final RoleplayTranscript transcript;
  final bool showConfidenceLegend;

  const _HistorySessionHeader({
    required this.transcript,
    required this.showConfidenceLegend,
  });

  @override
  Widget build(BuildContext context) {
    final rawDuration = transcript.session['duration_seconds'];
    final duration = rawDuration is num ? rawDuration.round() : 0;
    final minutes = duration ~/ 60;
    final seconds = duration % 60;
    final turnLabel = transcript.turns.length == 1 ? 'turn' : 'turns';
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            _primary.withValues(alpha: .16),
            _accent.withValues(alpha: .09),
          ],
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _primary.withValues(alpha: .28)),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: _surface.withValues(alpha: .72),
                  borderRadius: BorderRadius.circular(13),
                  border: Border.all(color: _border),
                ),
                child: Text(
                  transcript.scenario.icon,
                  style: const TextStyle(fontSize: 21),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Conversation replay',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: GoogleFonts.inter(
                        color: _text,
                        fontSize: 14,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${transcript.turns.length} $turnLabel  •  '
                      '$minutes:${seconds.toString().padLeft(2, '0')}',
                      style: GoogleFonts.inter(
                        color: _muted,
                        fontSize: 11,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 6),
                decoration: BoxDecoration(
                  color: _surface.withValues(alpha: .72),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: _border),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.lock_outline_rounded,
                      color: _muted,
                      size: 13,
                    ),
                    const SizedBox(width: 5),
                    Text(
                      'Read only',
                      style: GoogleFonts.inter(
                        color: _muted,
                        fontSize: 9,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (showConfidenceLegend) ...[
            const SizedBox(height: 14),
            const Divider(height: 1, color: _border),
            const SizedBox(height: 11),
            const Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'WORD CONFIDENCE',
                style: TextStyle(
                  color: _muted,
                  fontSize: 9,
                  fontWeight: FontWeight.w700,
                  letterSpacing: .7,
                ),
              ),
            ),
            const SizedBox(height: 8),
            const Wrap(
              spacing: 12,
              runSpacing: 7,
              children: [
                _LegendItem(
                  color: RoleplayConfidenceTranscript.highConfidenceColor,
                  label: 'Clear',
                ),
                _LegendItem(
                  color: RoleplayConfidenceTranscript.mediumConfidenceColor,
                  label: 'Review',
                ),
                _LegendItem(
                  color: RoleplayConfidenceTranscript.lowConfidenceColor,
                  label: 'Low',
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _LegendItem extends StatelessWidget {
  final Color color;
  final String label;

  const _LegendItem({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 7,
          height: 7,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 4),
        Text(
          label,
          style: GoogleFonts.inter(
            color: _text,
            fontSize: 9,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
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
