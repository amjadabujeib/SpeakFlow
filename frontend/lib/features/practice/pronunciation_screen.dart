// lib/features/practice/pronunciation_screen.dart
import 'dart:async';
import 'dart:io';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:speakflow/core/theme/local_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:record/record.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:path_provider/path_provider.dart';
import '../../app/providers.dart';
import '../../core/data/phoneme_progress_store.dart';

part 'pronunciation_input_widgets.dart';
part 'pronunciation_result_widgets.dart';

class PronunciationLaunchArgs {
  final String target;
  final Future<void> Function()? onPassed;

  const PronunciationLaunchArgs({required this.target, this.onPassed});
}

bool isPracticePronunciationPass(Map<String, dynamic>? scores) {
  final accuracy = scores?['accuracy'];
  final completeness = scores?['completeness'];
  return accuracy is num &&
      completeness is num &&
      accuracy >= 85 &&
      completeness >= 90;
}

// ─── Colors (matching SpeakFlow dark theme) ──────────────────
const _background = Color(0xFF090E1A);
const _surface = Color(0xFF111827);
const _surfaceCard = Color(0xFF1E2D45);
const _primary = Color(0xFF4F7FFF);
const _accent = Color(0xFF8B5CF6);
const _success = Color(0xFF22C55E);
const _error = Color(0xFFEF4444);
const _warning = Color(0xFFF59E0B);
const _textPrimary = Color(0xFFF1F5FF);
const _textSecondary = Color(0xFF8896B0);

class PronunciationScreen extends StatefulWidget {
  final String? initialTarget;
  final Future<void> Function()? onPassed;

  const PronunciationScreen({super.key, this.initialTarget, this.onPassed});

  @override
  State<PronunciationScreen> createState() => _PronunciationScreenState();
}

class _PronunciationScreenState extends State<PronunciationScreen>
    with TickerProviderStateMixin {
  late final TextEditingController _wordCtrl;
  final _audioRecorder = AudioRecorder();
  final _examplePlayer = AudioPlayer();
  StreamSubscription<void>? _playerCompleteSubscription;
  Timer? _guideDebounce;
  int _exampleAudioRequest = 0;
  String? _recordingTarget;

  bool _isRecording = false;
  bool _isProcessing = false;
  bool _isGuideLoading = false;
  bool _isExamplePlaying = false;

  String? _spokenResult;
  List<dynamic>? _analysis;
  Map<String, dynamic>? _scores;
  Map<String, dynamic>? _guide;
  String? _feedback;
  String? _errorMessage;
  String? _guideError;
  bool _passHandled = false;
  int _guideRequest = 0;

  late AnimationController _pulseController;

  final _practiceTargets = [
    'apple',
    'through',
    'very',
    'three',
    'Please bring the blue folder.',
    'I would like a window seat, please.',
  ];

  @override
  void initState() {
    super.initState();
    _wordCtrl = TextEditingController(text: widget.initialTarget?.trim() ?? '');
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat(reverse: true);
    _playerCompleteSubscription = _examplePlayer.onPlayerComplete.listen((_) {
      if (mounted) setState(() => _isExamplePlaying = false);
    });
    if (_wordCtrl.text.isNotEmpty) {
      _loadPronunciationGuide();
    }
  }

  @override
  void dispose() {
    _exampleAudioRequest++;
    _wordCtrl.dispose();
    _audioRecorder.dispose();
    _guideDebounce?.cancel();
    _playerCompleteSubscription?.cancel();
    _examplePlayer.dispose();
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _loadPronunciationGuide() async {
    final target = _wordCtrl.text.trim();
    if (target.isEmpty) {
      ++_guideRequest;
      if (!mounted) return;
      setState(() {
        _isGuideLoading = false;
        _guide = null;
        _guideError = null;
      });
      return;
    }
    final request = ++_guideRequest;
    setState(() {
      _isGuideLoading = true;
      _guideError = null;
    });
    final result = await AppDependencies.instance.pronunciation.guide(target);
    if (!mounted || request != _guideRequest) return;
    setState(() {
      _isGuideLoading = false;
      if (result.containsKey('error')) {
        _guide = null;
        _guideError = result['error'].toString();
      } else {
        _guide = result;
      }
    });
  }

  void _handleTargetChanged(String value) {
    _guideDebounce?.cancel();
    setState(() {
      _guide = null;
      _guideError = null;
      _isGuideLoading = value.trim().isNotEmpty;
      _errorMessage = null;
    });
    _guideDebounce = Timer(
      const Duration(milliseconds: 450),
      _loadPronunciationGuide,
    );
  }

  void _selectTarget(String target) {
    if (_isRecording || _isProcessing) return;
    setState(() => _wordCtrl.text = target);
    _loadPronunciationGuide();
  }

  Future<void> _playExample() async {
    final target = _wordCtrl.text.trim();
    if (target.isEmpty) return;
    if (_isExamplePlaying) {
      _exampleAudioRequest++;
      await _examplePlayer.stop();
      if (mounted) setState(() => _isExamplePlaying = false);
      return;
    }
    final request = ++_exampleAudioRequest;
    setState(() {
      _isExamplePlaying = true;
      _guideError = null;
    });
    try {
      final audio = await AppDependencies.instance.languageTools
          .synthesizeSpeech(target);
      if (!mounted || request != _exampleAudioRequest) return;
      await _examplePlayer.play(BytesSource(audio));
    } catch (_) {
      if (!mounted || request != _exampleAudioRequest) return;
      setState(() {
        _isExamplePlaying = false;
        _guideError = 'Kokoro could not play this pronunciation.';
      });
    }
  }

  // ── Recording Logic ────────────────────────────────────────

  Future<void> _startRecording() async {
    if (_wordCtrl.text.trim().isEmpty) {
      setState(() {
        _errorMessage = 'Enter or select a practice target first.';
      });
      return;
    }
    final status = await Permission.microphone.request();
    if (!mounted) return;
    if (status != PermissionStatus.granted) {
      setState(() => _errorMessage = 'Microphone permission denied.');
      return;
    }

    if (await _audioRecorder.hasPermission()) {
      if (!mounted) return;
      final dir = await getTemporaryDirectory();
      final audioPath =
          '${dir.path}/pronunciation_${DateTime.now().microsecondsSinceEpoch}.wav';
      final recordingTarget = _wordCtrl.text.trim();

      await _audioRecorder.start(
        const RecordConfig(
          encoder: AudioEncoder.wav,
          sampleRate: 16000,
          numChannels: 1,
        ),
        path: audioPath,
      );

      if (!mounted) return;
      setState(() {
        _isRecording = true;
        _recordingTarget = recordingTarget;
        _spokenResult = null;
        _analysis = null;
        _scores = null;
        _feedback = null;
        _errorMessage = null;
      });
    }
  }

  Future<void> _stopRecording() async {
    final target = _recordingTarget;
    final path = await _audioRecorder.stop();
    if (!mounted) return;
    setState(() {
      _isRecording = false;
      _recordingTarget = null;
      _isProcessing = true;
    });

    if (path != null && target != null && target.isNotEmpty) {
      Map<String, dynamic> result;
      try {
        result = await AppDependencies.instance.pronunciation.score(
          target,
          path,
        );
      } finally {
        try {
          final recording = File(path);
          if (await recording.exists()) await recording.delete();
        } catch (_) {
          // Temporary cleanup must not replace the scoring result.
        }
      }

      if (!mounted) return;

      if (result.containsKey('error')) {
        setState(() {
          _errorMessage = result['error'].toString();
          _isProcessing = false;
        });
      } else {
        final analysis = result['analysis'] as List<dynamic>?;
        final scores = result['scores'] as Map<String, dynamic>?;
        if (analysis != null) {
          await PhonemeProgressStore.instance.recordAnalysis(analysis);
        }
        if (!mounted) return;
        setState(() {
          _spokenResult = result['spoken']?.toString();
          _analysis = analysis;
          _scores = scores;
          _feedback = result['feedback']?.toString();
          _isProcessing = false;
        });
        if (!_passHandled &&
            widget.onPassed != null &&
            isPracticePronunciationPass(scores)) {
          _passHandled = true;
          await widget.onPassed!();
        }
      }
    } else {
      setState(() => _isProcessing = false);
    }
  }

  void _toggleRecording() {
    if (_isProcessing) return;
    if (_isRecording) {
      _stopRecording();
    } else {
      _startRecording();
    }
  }

  int get _score {
    final value = _scores?['overall_score'] ?? _scores?['gop_score'];
    return value is num ? value.round() : 0;
  }

  bool get _queueTargetPassed =>
      widget.onPassed != null && isPracticePronunciationPass(_scores);

  bool get _hasTarget => _wordCtrl.text.trim().isNotEmpty;

  Color get _scoreColor {
    if (_score >= 90) return _success;
    if (_score >= 70) return _primary;
    if (_score >= 50) return _warning;
    return _error;
  }

  // ── Build ──────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _background,
      appBar: AppBar(
        backgroundColor: _surface,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: _textPrimary),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(
          'Pronunciation Practice',
          style: GoogleFonts.inter(
            fontSize: 18,
            fontWeight: FontWeight.w700,
            color: _textPrimary,
          ),
        ),
        centerTitle: true,
      ),
      body: SingleChildScrollView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // ── Instruction Card ─────────────────────────────
            _buildInstructionCard(),
            const SizedBox(height: 20),

            // ── Target Word Input ────────────────────────────
            _buildTargetInput(),
            const SizedBox(height: 12),

            _buildPronunciationGuide(),
            const SizedBox(height: 12),

            // ── Practice Word Chips ──────────────────────────
            if (widget.onPassed == null) _buildPracticeChips(),
            const SizedBox(height: 32),

            // ── Mic Button ───────────────────────────────────
            _buildMicButton(),
            const SizedBox(height: 32),

            // ── Error ────────────────────────────────────────
            if (_errorMessage != null) _buildErrorCard(),

            // ── Results ──────────────────────────────────────
            if (_analysis != null && _analysis!.isNotEmpty) ...[
              _buildScoreCard(),
              if (_queueTargetPassed) ...[
                const SizedBox(height: 16),
                Container(
                  key: const ValueKey('practice-word-passed'),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: _success.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: _success.withValues(alpha: 0.35)),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.verified_rounded, color: _success),
                      SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          'Pronounced correctly. This target was moved to '
                          'your Mastered words.',
                          style: TextStyle(color: _textPrimary, height: 1.35),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
              const SizedBox(height: 16),
              _buildPhonemeCard(),
              if (_feedback != null && _feedback!.isNotEmpty) ...[
                const SizedBox(height: 16),
                _buildFeedbackCard(),
              ],
              const SizedBox(height: 40),
            ],
          ],
        ),
      ),
    );
  }

  // ── Widgets ────────────────────────────────────────────────
}
