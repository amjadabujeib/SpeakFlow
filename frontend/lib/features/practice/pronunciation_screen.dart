// lib/features/practice/pronunciation_screen.dart
import 'dart:async';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:speakflow/core/theme/local_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:record/record.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:path_provider/path_provider.dart';
import '../../app/providers.dart';
import '../../core/data/phoneme_progress_store.dart';

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
    setState(() => _wordCtrl.text = target);
    _loadPronunciationGuide();
  }

  Future<void> _playExample() async {
    final target = _wordCtrl.text.trim();
    if (target.isEmpty) return;
    if (_isExamplePlaying) {
      await _examplePlayer.stop();
      if (mounted) setState(() => _isExamplePlaying = false);
      return;
    }
    setState(() {
      _isExamplePlaying = true;
      _guideError = null;
    });
    try {
      await _examplePlayer.play(
        UrlSource(
          AppDependencies.instance.languageTools.ttsUri(target).toString(),
        ),
      );
    } catch (_) {
      if (!mounted) return;
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
    if (status != PermissionStatus.granted) {
      setState(() => _errorMessage = 'Microphone permission denied.');
      return;
    }

    if (await _audioRecorder.hasPermission()) {
      final dir = await getTemporaryDirectory();
      final audioPath = '${dir.path}/pronunciation_audio.wav';

      await _audioRecorder.start(
        const RecordConfig(
          encoder: AudioEncoder.wav,
          sampleRate: 16000,
          numChannels: 1,
        ),
        path: audioPath,
      );

      setState(() {
        _isRecording = true;
        _spokenResult = null;
        _analysis = null;
        _scores = null;
        _feedback = null;
        _errorMessage = null;
      });
    }
  }

  Future<void> _stopRecording() async {
    final path = await _audioRecorder.stop();
    setState(() {
      _isRecording = false;
      _isProcessing = true;
    });

    if (path != null) {
      final result = await AppDependencies.instance.pronunciation.score(
        _wordCtrl.text.trim(),
        path,
      );

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

  Widget _buildInstructionCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            _primary.withValues(alpha: 0.12),
            _accent.withValues(alpha: 0.08),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _primary.withValues(alpha: 0.2)),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              gradient: const LinearGradient(colors: [_primary, _accent]),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(
              Icons.tips_and_updates_rounded,
              color: Colors.white,
              size: 20,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Text(
              widget.onPassed != null
                  ? 'Say the selected target exactly as shown. A correct '
                        'result moves it to your Mastered words.'
                  : 'Enter a word or sentence, then speak the exact target. '
                        'Unclear or mismatched audio is rejected instead of '
                        'guessed.',
              style: GoogleFonts.inter(
                fontSize: 13,
                color: _textSecondary,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    ).animate().fadeIn(duration: 400.ms).slideY(begin: -0.1, end: 0);
  }

  Widget _buildTargetInput() {
    return Container(
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _primary.withValues(alpha: 0.3)),
      ),
      child: TextField(
        controller: _wordCtrl,
        readOnly: widget.onPassed != null,
        onChanged: _handleTargetChanged,
        onSubmitted: (_) => _loadPronunciationGuide(),
        textInputAction: TextInputAction.done,
        minLines: 1,
        maxLines: 3,
        maxLength: 120,
        style: GoogleFonts.inter(
          fontSize: 20,
          fontWeight: FontWeight.w600,
          color: _textPrimary,
        ),
        textAlign: TextAlign.center,
        decoration: InputDecoration(
          hintText: 'Enter a word or sentence...',
          counterText: widget.onPassed != null ? '' : null,
          hintStyle: GoogleFonts.inter(
            color: _textSecondary.withValues(alpha: 0.5),
          ),
          border: InputBorder.none,
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 20,
            vertical: 16,
          ),
          prefixIcon: Icon(
            widget.onPassed != null
                ? Icons.lock_outline_rounded
                : Icons.edit_note_rounded,
            color: _primary,
          ),
        ),
      ),
    ).animate().fadeIn(duration: 400.ms, delay: 50.ms);
  }

  Widget _buildPracticeChips() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Or try a practice target:',
          style: GoogleFonts.inter(fontSize: 12, color: _textSecondary),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: _practiceTargets.map((target) {
            final isSelected = _wordCtrl.text == target;
            return GestureDetector(
              onTap: () => _selectTarget(target),
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: isSelected
                      ? _primary.withValues(alpha: 0.2)
                      : _surfaceCard,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: isSelected ? _primary : _surfaceCard,
                    width: 1.5,
                  ),
                ),
                child: Text(
                  target,
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color: isSelected ? _primary : _textSecondary,
                  ),
                ),
              ),
            );
          }).toList(),
        ),
      ],
    ).animate().fadeIn(duration: 400.ms, delay: 100.ms);
  }

  Widget _buildPronunciationGuide() {
    if (!_hasTarget) {
      return Container(
        key: const ValueKey('pronunciation-guide-empty'),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: _surfaceCard,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: _primary.withValues(alpha: 0.18)),
        ),
        child: Row(
          children: [
            const Icon(Icons.hearing_rounded, color: _primary),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                'Enter a word or sentence above, or choose a practice target.',
                style: GoogleFonts.inter(
                  color: _textSecondary,
                  fontSize: 13,
                  height: 1.35,
                ),
              ),
            ),
          ],
        ),
      );
    }
    if (_isGuideLoading) {
      return Container(
        key: const ValueKey('pronunciation-guide-loading'),
        height: 116,
        decoration: BoxDecoration(
          color: _surfaceCard,
          borderRadius: BorderRadius.circular(16),
        ),
        child: const Center(child: CircularProgressIndicator(strokeWidth: 2)),
      );
    }
    if (_guideError case final error?) {
      return Container(
        key: const ValueKey('pronunciation-guide-error'),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: _error.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: _error.withValues(alpha: 0.25)),
        ),
        child: Row(
          children: [
            const Icon(Icons.info_outline_rounded, color: _error),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                error,
                style: GoogleFonts.inter(color: _textSecondary, fontSize: 12),
              ),
            ),
            IconButton(
              tooltip: 'Try again',
              onPressed: _loadPronunciationGuide,
              icon: const Icon(Icons.refresh_rounded),
            ),
          ],
        ),
      );
    }

    final ipa = _guide?['ipa']?.toString() ?? '';
    return Container(
      key: const ValueKey('pronunciation-guide'),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _primary.withValues(alpha: 0.28)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'IPA',
                      style: GoogleFonts.inter(
                        color: _textSecondary,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.7,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      ipa.isEmpty ? 'Unavailable' : '/$ipa/',
                      style: GoogleFonts.inter(
                        color: _accent,
                        fontSize: 22,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
              FilledButton.tonalIcon(
                key: const ValueKey('listen-to-pronunciation'),
                onPressed: _playExample,
                icon: Icon(
                  _isExamplePlaying
                      ? Icons.stop_rounded
                      : Icons.volume_up_rounded,
                ),
                label: Text(_isExamplePlaying ? 'Stop' : 'Listen'),
              ),
            ],
          ),
        ],
      ),
    ).animate().fadeIn(duration: 300.ms);
  }

  Widget _buildMicButton() {
    return Center(
      child: Column(
        children: [
          GestureDetector(
            key: const ValueKey('pronunciation-record-button'),
            onTap: _hasTarget ? _toggleRecording : null,
            child: AnimatedBuilder(
              animation: _pulseController,
              builder: (context, child) {
                final scale = _isRecording
                    ? 1.0 + (_pulseController.value * 0.08)
                    : 1.0;
                return Transform.scale(
                  scale: scale,
                  child: Container(
                    width: 88,
                    height: 88,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: LinearGradient(
                        colors: !_hasTarget || _isProcessing
                            ? [Colors.grey.shade700, Colors.grey.shade600]
                            : _isRecording
                            ? [_error, const Color(0xFFDC2626)]
                            : [_primary, _accent],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color:
                              (!_hasTarget
                                      ? Colors.grey
                                      : _isRecording
                                      ? _error
                                      : _primary)
                                  .withValues(alpha: 0.3),
                          blurRadius: _isRecording ? 28 : 16,
                          spreadRadius: _isRecording ? 4 : 0,
                        ),
                      ],
                    ),
                    child: _isProcessing
                        ? const Center(
                            child: SizedBox(
                              width: 30,
                              height: 30,
                              child: CircularProgressIndicator(
                                color: Colors.white,
                                strokeWidth: 2.5,
                              ),
                            ),
                          )
                        : Icon(
                            _isRecording
                                ? Icons.stop_rounded
                                : Icons.mic_rounded,
                            color: Colors.white,
                            size: 38,
                          ),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 14),
          Text(
            _isRecording
                ? 'Tap to stop'
                : _isProcessing
                ? 'Analyzing your pronunciation...'
                : !_hasTarget
                ? 'Enter or select a target first'
                : 'Tap to start speaking',
            style: GoogleFonts.inter(
              fontSize: 14,
              fontWeight: FontWeight.w500,
              color: _textSecondary,
            ),
          ),
        ],
      ),
    ).animate().fadeIn(duration: 400.ms, delay: 150.ms);
  }

  Widget _buildErrorCard() {
    return Container(
          margin: const EdgeInsets.only(bottom: 16),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: _error.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: _error.withValues(alpha: 0.3)),
          ),
          child: Row(
            children: [
              const Icon(Icons.error_outline_rounded, color: _error, size: 20),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  _errorMessage!,
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    color: _error,
                    height: 1.3,
                  ),
                ),
              ),
            ],
          ),
        )
        .animate()
        .fadeIn(duration: 300.ms)
        .shakeX(hz: 3, amount: 3, duration: 400.ms);
  }

  Widget _buildScoreCard() {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _scoreColor.withValues(alpha: 0.3)),
      ),
      child: Column(
        children: [
          Text(
            'Pronunciation Score',
            style: GoogleFonts.inter(fontSize: 13, color: _textSecondary),
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '$_score',
                style: GoogleFonts.inter(
                  fontSize: 56,
                  fontWeight: FontWeight.w800,
                  color: _scoreColor,
                  height: 1,
                ),
              ),
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  '/100',
                  style: GoogleFonts.inter(
                    fontSize: 20,
                    fontWeight: FontWeight.w500,
                    color: _textSecondary,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          // Overall score bar
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(
              value: _score / 100.0,
              backgroundColor: _surface,
              color: _scoreColor,
              minHeight: 8,
            ),
          ),
          // Multi-aspect breakdown (when backend scores available)
          if (_scores != null) ...[
            const SizedBox(height: 20),
            const Divider(color: Color(0xFF1E2D45), height: 1),
            const SizedBox(height: 16),
            _buildScoreBar('Accuracy', _scores!['accuracy'] as num?),
            const SizedBox(height: 10),
            _buildScoreBar('Fluency', _scores!['fluency'] as num?),
            const SizedBox(height: 10),
            _buildScoreBar('Prosody', _scores!['prosody'] as num?),
            const SizedBox(height: 10),
            _buildScoreBar('Completeness', _scores!['completeness'] as num?),
          ],
          const SizedBox(height: 12),
          if (_spokenResult != null)
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  'You said: ',
                  style: GoogleFonts.inter(fontSize: 13, color: _textSecondary),
                ),
                Text(
                  '"$_spokenResult"',
                  style: GoogleFonts.inter(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color:
                        _spokenResult!.trim().toLowerCase() ==
                            _wordCtrl.text.trim().toLowerCase()
                        ? _success
                        : _textPrimary,
                  ),
                ),
                if (_spokenResult!.trim().toLowerCase() ==
                    _wordCtrl.text.trim().toLowerCase()) ...[
                  const SizedBox(width: 6),
                  const Icon(
                    Icons.stars_rounded,
                    color: Color(0xFFF59E0B),
                    size: 18,
                  ),
                ],
              ],
            ),
        ],
      ),
    ).animate().fadeIn(duration: 400.ms).slideY(begin: 0.05, end: 0);
  }

  Widget _buildPhonemeCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _primary.withValues(alpha: 0.15)),
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.graphic_eq_rounded, color: _accent, size: 18),
              const SizedBox(width: 8),
              Text(
                'Phone analysis (IPA)',
                style: GoogleFonts.inter(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: _textSecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Wrap(
            alignment: WrapAlignment.center,
            spacing: 4,
            runSpacing: 6,
            children: _analysis!.asMap().entries.map((entry) {
              final idx = entry.key;
              final charData = entry.value as Map<String, dynamic>;
              final String char = charData['char'] ?? '?';
              final status = charData['status']?.toString() ?? 'warning';
              final color = switch (status) {
                'correct' => _success,
                'incorrect' => _error,
                'omitted' => _textSecondary,
                _ => _warning,
              };
              final quality = charData['score'];
              final likelyIpa = charData['likely_ipa']?.toString();
              final closestIpa = charData['closest_ipa']?.toString();
              final errorType = charData['error_type']?.toString();
              final tooltip = quality is! num
                  ? 'Omitted / not acoustically scored'
                  : status == 'incorrect' &&
                        errorType == 'substitution' &&
                        likelyIpa != null &&
                        likelyIpa.isNotEmpty
                  ? 'Target /$char/ • sounded closer to /$likelyIpa/ • quality ${quality.round()}%'
                  : status == 'incorrect' && errorType == 'deletion'
                  ? 'Target /$char/ may have been omitted • quality ${quality.round()}%'
                  : status == 'warning' &&
                        closestIpa != null &&
                        closestIpa.isNotEmpty
                  ? 'Target /$char/ needs attention • closest acoustic guess /$closestIpa/ • quality ${quality.round()}%'
                  : '${status == 'warning' ? 'Needs attention' : status} • quality ${quality.round()}%';

              return Tooltip(
                    message: tooltip,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 6,
                      ),
                      decoration: BoxDecoration(
                        color: color.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: color.withValues(alpha: 0.4),
                          width: 1.5,
                        ),
                      ),
                      child: Text(
                        char,
                        style: GoogleFonts.inter(
                          fontSize: 24,
                          fontWeight: FontWeight.w700,
                          color: color,
                        ),
                      ),
                    ),
                  )
                  .animate(delay: Duration(milliseconds: 40 * idx))
                  .fadeIn(duration: 250.ms)
                  .scale(
                    begin: const Offset(0.8, 0.8),
                    end: const Offset(1, 1),
                    duration: 250.ms,
                  );
            }).toList(),
          ),
        ],
      ),
    ).animate().fadeIn(duration: 400.ms, delay: 100.ms).slideY(begin: 0.05, end: 0);
  }

  Widget _buildFeedbackCard() {
    return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                _accent.withValues(alpha: 0.1),
                _primary.withValues(alpha: 0.06),
              ],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: _accent.withValues(alpha: 0.25)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [_accent, _primary],
                      ),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(
                      Icons.psychology_rounded,
                      color: Colors.white,
                      size: 16,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    'How to improve',
                    style: GoogleFonts.inter(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: _textPrimary,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                _feedback!,
                style: GoogleFonts.inter(
                  fontSize: 13,
                  color: _textSecondary,
                  height: 1.5,
                ),
              ),
            ],
          ),
        )
        .animate()
        .fadeIn(duration: 400.ms, delay: 200.ms)
        .slideY(begin: 0.05, end: 0);
  }

  Widget _buildScoreBar(String label, num? rawScore) {
    final score = rawScore?.round();
    if (score == null) {
      return Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: GoogleFonts.inter(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: _textSecondary,
            ),
          ),
          Text(
            'Not enough evidence',
            style: GoogleFonts.inter(fontSize: 11, color: _textSecondary),
          ),
        ],
      );
    }
    Color barColor;
    if (score >= 90) {
      barColor = _success;
    } else if (score >= 70) {
      barColor = _primary;
    } else if (score >= 50) {
      barColor = _warning;
    } else {
      barColor = _error;
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              label,
              style: GoogleFonts.inter(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: _textSecondary,
              ),
            ),
            Text(
              '$score%',
              style: GoogleFonts.inter(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: barColor,
              ),
            ),
          ],
        ),
        const SizedBox(height: 5),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: score / 100.0,
            backgroundColor: _surface,
            color: barColor,
            minHeight: 6,
          ),
        ),
      ],
    );
  }
}
