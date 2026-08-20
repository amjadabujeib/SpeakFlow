import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

import '../../../../app/providers.dart';
import '../../../../core/theme/app_colors.dart';

class GuidedSpeakingPracticePage extends ConsumerStatefulWidget {
  final String prompt;
  final int minimumSeconds;

  const GuidedSpeakingPracticePage({
    super.key,
    required this.prompt,
    required this.minimumSeconds,
  });

  @override
  ConsumerState<GuidedSpeakingPracticePage> createState() =>
      _GuidedSpeakingPracticePageState();
}

class _GuidedSpeakingPracticePageState
    extends ConsumerState<GuidedSpeakingPracticePage> {
  final AudioRecorder _recorder = AudioRecorder();
  bool _recording = false;
  bool _processing = false;
  String? _error;
  DateTime? _startedAt;

  @override
  void dispose() {
    _recorder.dispose();
    super.dispose();
  }

  Future<void> _start() async {
    final permission = await Permission.microphone.request();
    if (permission != PermissionStatus.granted ||
        !await _recorder.hasPermission()) {
      if (mounted) {
        setState(() => _error = 'Microphone permission is required.');
      }
      return;
    }
    final directory = await getTemporaryDirectory();
    final path =
        '${directory.path}/guided_speaking_'
        '${DateTime.now().microsecondsSinceEpoch}.wav';
    await _recorder.start(
      const RecordConfig(
        encoder: AudioEncoder.wav,
        sampleRate: 16000,
        numChannels: 1,
      ),
      path: path,
    );
    if (!mounted) return;
    setState(() {
      _recording = true;
      _startedAt = DateTime.now();
      _error = null;
    });
  }

  Future<void> _stop() async {
    final path = await _recorder.stop();
    final elapsed = _startedAt == null
        ? Duration.zero
        : DateTime.now().difference(_startedAt!);
    if (!mounted) return;
    setState(() {
      _recording = false;
      _processing = true;
      _error = null;
    });
    if (path == null) {
      setState(() {
        _processing = false;
        _error = 'The recording could not be saved.';
      });
      return;
    }
    try {
      if (elapsed.inMilliseconds < widget.minimumSeconds * 1000) {
        throw StateError(
          'Speak for at least ${widget.minimumSeconds} seconds before stopping.',
        );
      }
      final result = await ref
          .read(pronunciationApiProvider)
          .transcribeSpeaking(path);
      if (!mounted) return;
      if (result['error'] != null) {
        setState(() {
          _processing = false;
          _error = result['error'].toString();
        });
        return;
      }
      Navigator.pop(context, result);
    } catch (error) {
      if (mounted) {
        setState(() {
          _processing = false;
          _error = error is StateError
              ? error.message
              : 'Could not process the recording.';
        });
      }
    } finally {
      try {
        final recording = File(path);
        if (await recording.exists()) await recording.delete();
      } catch (_) {
        // Temporary cleanup must not replace the transcription result.
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Guided speaking')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 24, 24, 28),
          child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              widget.prompt,
              style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 14),
            Text(
              'Speak for at least ${widget.minimumSeconds} seconds.',
              style: const TextStyle(color: AppColors.textSecondary),
            ),
            const Spacer(),
            if (_error != null) ...[
              Text(
                _error!,
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.error),
              ),
              const SizedBox(height: 16),
            ],
            FilledButton.icon(
              onPressed: _processing ? null : (_recording ? _stop : _start),
              icon: _processing
                  ? const SizedBox.square(
                      dimension: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : Icon(_recording ? Icons.stop_rounded : Icons.mic_rounded),
              label: Text(
                _processing
                    ? 'TRANSCRIBING...'
                    : _recording
                    ? 'STOP AND USE RESPONSE'
                    : 'START RECORDING',
              ),
            ),
          ],
        ),
      ),
    ),
  );
}
}
