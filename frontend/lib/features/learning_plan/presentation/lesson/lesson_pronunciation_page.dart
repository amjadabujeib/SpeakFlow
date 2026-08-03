part of 'lesson_screens.dart';

class _LessonPronunciationPracticePage extends StatefulWidget {
  final String initialTarget;
  final List<String> assignedTargets;
  final String? activityId;
  final String attemptSessionId;

  const _LessonPronunciationPracticePage({
    required this.initialTarget,
    required this.assignedTargets,
    required this.activityId,
    required this.attemptSessionId,
  });

  @override
  State<_LessonPronunciationPracticePage> createState() =>
      _LessonPronunciationPracticePageState();
}

class _LessonPronunciationPracticePageState
    extends State<_LessonPronunciationPracticePage> {
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();

  bool _recording = false;
  bool _processing = false;
  bool _playing = false;
  JsonMap? _result;
  PlpAttemptResult? _lessonAttempt;
  String? _error;
  String? _submissionId;

  String get _target => widget.initialTarget.trim();

  @override
  void dispose() {
    _recorder.dispose();
    _player.dispose();
    super.dispose();
  }

  Future<void> _playTarget() async {
    if (_target.isEmpty || _playing) return;
    setState(() {
      _playing = true;
      _error = null;
    });
    try {
      final audio = await AppDependencies.instance.languageTools
          .synthesizeSpeech(_target);
      await _player.play(BytesSource(audio));
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Kokoro playback could not be started.');
      }
    } finally {
      if (mounted) setState(() => _playing = false);
    }
  }

  Future<void> _startRecording() async {
    if (_target.isEmpty) {
      setState(() => _error = 'Enter a word or sentence first.');
      return;
    }
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
        '${directory.path}/lesson_pronunciation_'
        '${DateTime.now().microsecondsSinceEpoch}.wav';
    final recordingId = DateTime.now().microsecondsSinceEpoch;
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
      _result = null;
      _lessonAttempt = null;
      _error = null;
      _submissionId = widget.activityId == null
          ? null
          : '${widget.attemptSessionId}_${widget.activityId}_$recordingId';
    });
  }

  Future<void> _stopAndScore() async {
    final path = await _recorder.stop();
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
      final decoded = await AppDependencies.instance.pronunciation.score(
        _target,
        path,
        activityId: widget.activityId,
        attemptSessionId: widget.activityId == null
            ? null
            : widget.attemptSessionId,
        submissionId: _submissionId,
      );
      if (!mounted) return;
      if (decoded['error'] != null) {
        setState(() {
          _processing = false;
          _error = decoded['error'].toString();
        });
        return;
      }
      final lessonAttempt = decoded['lesson_attempt'] is JsonMap
          ? PlpAttemptResult.fromJson(decoded['lesson_attempt'] as JsonMap)
          : null;
      setState(() {
        _processing = false;
        _result = decoded;
        _lessonAttempt = lessonAttempt;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _processing = false;
        _error = 'Could not reach the local pronunciation service.';
      });
    } finally {
      try {
        final recording = File(path);
        if (await recording.exists()) await recording.delete();
      } catch (_) {
        // Temporary cleanup must not replace the scoring result.
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final scores = _result?['scores'] is Map
        ? Map<String, dynamic>.from(_result!['scores'] as Map)
        : null;
    final analysis = _result?['analysis'] is List
        ? _result!['analysis'] as List
        : const [];
    final targetIndex = widget.assignedTargets.indexWhere(
      (item) => item.trim().toLowerCase() == _target.toLowerCase(),
    );
    return Scaffold(
      appBar: AppBar(title: const Text('Sound check')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              key: const ValueKey('lesson-pronunciation-target'),
              padding: const EdgeInsets.fromLTRB(18, 14, 10, 14),
              decoration: BoxDecoration(
                color: AppColors.surfaceCard,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppColors.borderLight),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          targetIndex >= 0
                              ? 'TARGET ${targetIndex + 1} OF '
                                    '${widget.assignedTargets.length}'
                              : 'ASSIGNED TARGET',
                          style: const TextStyle(
                            color: AppColors.primaryLight,
                            fontSize: 11,
                            fontWeight: FontWeight.w900,
                            letterSpacing: 0.6,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          _target,
                          style: const TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 22,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    key: const ValueKey('lesson-pronunciation-tts'),
                    tooltip: 'Hear with Kokoro',
                    onPressed: _playing ? null : _playTarget,
                    icon: _playing
                        ? const SizedBox.square(
                            dimension: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.volume_up_rounded),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            const Text(
              'Listen if helpful, then record yourself saying the complete '
              'target exactly as shown.',
              style: TextStyle(color: AppColors.textSecondary, height: 1.4),
            ),
            const SizedBox(height: 26),
            Center(
              child: FilledButton.icon(
                key: const ValueKey('lesson-pronunciation-record'),
                onPressed: _processing
                    ? null
                    : (_recording ? _stopAndScore : _startRecording),
                style: FilledButton.styleFrom(
                  backgroundColor: _recording
                      ? AppColors.error
                      : AppColors.primary,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 24,
                    vertical: 16,
                  ),
                ),
                icon: _processing
                    ? const SizedBox.square(
                        dimension: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : Icon(_recording ? Icons.stop : Icons.mic),
                label: Text(
                  _processing
                      ? 'ANALYSING…'
                      : _recording
                      ? 'STOP AND SCORE'
                      : 'START RECORDING',
                ),
              ),
            ),
            if (_error case final error?) ...[
              const SizedBox(height: 18),
              _LessonPracticeMessage(
                color: Colors.red,
                icon: Icons.error_outline,
                text: error,
              ),
            ],
            if (_lessonAttempt case final attempt?) ...[
              const SizedBox(height: 18),
              _LessonPracticeMessage(
                color: attempt.correct == true ? Colors.green : Colors.orange,
                icon: attempt.correct == true ? Icons.verified : Icons.replay,
                text: attempt.explanation,
              ),
            ],
            if (scores != null) ...[
              const SizedBox(height: 24),
              Text(
                '${(scores['overall_score'] as num?)?.round() ?? 0}/100',
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 42,
                  fontWeight: FontWeight.w900,
                  color: AppColors.primaryLight,
                ),
              ),
              const Text(
                'Overall pronunciation quality',
                textAlign: TextAlign.center,
                style: TextStyle(color: AppColors.textSecondary),
              ),
              const SizedBox(height: 18),
              for (final metric in const [
                ('Accuracy', 'accuracy'),
                ('Fluency', 'fluency'),
                ('Prosody', 'prosody'),
                ('Completeness', 'completeness'),
              ])
                if (scores[metric.$2] is num)
                  _LessonScoreBar(
                    label: metric.$1,
                    score: (scores[metric.$2] as num).round(),
                  ),
            ],
            if (analysis.isNotEmpty) ...[
              const SizedBox(height: 20),
              const Text(
                'Sound feedback',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  for (final raw in analysis)
                    if (raw is Map)
                      _LessonPhoneChip(data: Map<String, dynamic>.from(raw)),
                ],
              ),
            ],
            if (_result?['feedback'] case final String feedback
                when feedback.isNotEmpty) ...[
              const SizedBox(height: 18),
              _LessonPracticeMessage(
                color: Colors.blue,
                icon: Icons.tips_and_updates_outlined,
                text: feedback,
              ),
            ],
            if (_lessonAttempt?.correct == true) ...[
              const SizedBox(height: 24),
              FilledButton.icon(
                onPressed: () => Navigator.pop(context, _lessonAttempt),
                icon: const Icon(Icons.check_circle),
                label: const Text('BACK TO TARGETS'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
