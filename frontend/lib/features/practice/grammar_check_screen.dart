// lib/features/practice/grammar_check_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/services.dart';
import 'package:speakflow/core/theme/local_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:go_router/go_router.dart';
import '../../app/providers.dart';

part 'grammar_input_widgets.dart';
part 'grammar_result_widgets.dart';
part 'grammar_correction_card.dart';

// ─────────────────────── Colors ──────────────────────────────
const _background = Color(0xFF090E1A);
const _surface = Color(0xFF111827);
const _surfaceCard = Color(0xFF1E2D45);
const _primary = Color(0xFF4F7FFF);
const _accent = Color(0xFF8B5CF6);
const _success = Color(0xFF22C55E);
const _error = Color(0xFFEF4444);
const _textPrimary = Color(0xFFF1F5FF);
const _textSecondary = Color(0xFF8896B0);
const _border = Color(0xFF1E2D45);

class GrammarCheckScreen extends ConsumerStatefulWidget {
  const GrammarCheckScreen({super.key});

  @override
  ConsumerState<GrammarCheckScreen> createState() => _GrammarCheckScreenState();
}

class _GrammarCheckScreenState extends ConsumerState<GrammarCheckScreen> {
  void _update(VoidCallback change) => setState(change);

  final TextEditingController _textCtrl = TextEditingController();
  bool _isLoading = false;
  bool _hasResult = false;

  // Result data
  String _correctedText = '';
  bool _isCorrect = false;
  List<Map<String, dynamic>> _corrections = [];
  String? _errorMsg;
  int _requestSerial = 0;

  static const int _maxChars = 500;

  Future<void> _checkGrammar() async {
    final request = ++_requestSerial;
    final text = _textCtrl.text.trim();
    if (text.isEmpty) return;

    setState(() {
      _isLoading = true;
      _hasResult = false;
      _errorMsg = null;
    });

    final result = await ref.read(languageToolsApiProvider).checkGrammar(text);

    if (!mounted || request != _requestSerial) return;

    setState(() {
      _isLoading = false;
      if (result.containsKey('error')) {
        _errorMsg = result['error'];
        _hasResult = false;
      } else {
        _hasResult = true;
        _correctedText = result['corrected_text']?.toString() ?? text;
        _isCorrect = result['is_correct'] == true;
        _corrections =
            (result['corrections'] as List?)
                ?.map((e) => Map<String, dynamic>.from(e as Map))
                .toList() ??
            [];
      }
    });
  }

  void _tryExample() {
    _requestSerial++;
    _textCtrl.text =
        'I goed to the store yesterday and buyed some foods for my familys.';
    setState(() {
      _hasResult = false;
      _errorMsg = null;
    });
  }

  void _clearText() {
    _requestSerial++;
    _textCtrl.clear();
    setState(() {
      _hasResult = false;
      _errorMsg = null;
    });
  }

  @override
  void dispose() {
    _requestSerial++;
    _textCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _background,
      appBar: _buildAppBar(),
      body: SingleChildScrollView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 40),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _buildInputCard(),
            const SizedBox(height: 16),
            _buildCheckButton(),
            if (_errorMsg != null) ...[
              const SizedBox(height: 16),
              _buildErrorCard(),
            ],
            if (_hasResult) ...[
              const SizedBox(height: 24),
              _buildStatusCard()
                  .animate()
                  .fadeIn(duration: 400.ms)
                  .scale(
                    begin: const Offset(0.9, 0.9),
                    end: const Offset(1, 1),
                  ),
              if (!_isCorrect) ...[
                const SizedBox(height: 16),
                _buildCorrectedTextCard()
                    .animate()
                    .fadeIn(duration: 400.ms, delay: 100.ms)
                    .slideY(begin: 0.1, end: 0),
                const SizedBox(height: 16),
                _buildCorrectionsList(),
              ],
            ],
          ],
        ),
      ),
    );
  }

  AppBar _buildAppBar() {
    return AppBar(
      backgroundColor: _surface,
      elevation: 0,
      leading: IconButton(
        icon: const Icon(
          Icons.arrow_back_ios_new_rounded,
          color: _textPrimary,
          size: 20,
        ),
        onPressed: () {
          if (context.canPop()) {
            context.pop();
          } else {
            context.go('/practice');
          }
        },
      ),
      title: ShaderMask(
        shaderCallback: (b) =>
            const LinearGradient(colors: [_primary, _accent]).createShader(b),
        child: Text(
          'Grammar Check',
          style: GoogleFonts.inter(
            fontWeight: FontWeight.w700,
            fontSize: 18,
            color: Colors.white,
          ),
        ),
      ),
      actions: [
        Container(
          margin: const EdgeInsets.only(right: 12),
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: _accent.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(10),
          ),
          child: const Icon(
            Icons.auto_awesome_rounded,
            color: _accent,
            size: 20,
          ),
        ),
      ],
      bottom: PreferredSize(
        preferredSize: const Size.fromHeight(1),
        child: Container(height: 1, color: _border),
      ),
    );
  }
}
