// lib/features/practice/grammar_check_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:go_router/go_router.dart';
import '../../core/services/api_service.dart';

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

class GrammarCheckScreen extends StatefulWidget {
  const GrammarCheckScreen({super.key});

  @override
  State<GrammarCheckScreen> createState() => _GrammarCheckScreenState();
}

class _GrammarCheckScreenState extends State<GrammarCheckScreen> {
  final TextEditingController _textCtrl = TextEditingController();
  bool _isLoading = false;
  bool _hasResult = false;

  // Result data
  String _correctedText = '';
  bool _isCorrect = false;
  List<Map<String, dynamic>> _corrections = [];
  String? _errorMsg;

  static const int _maxChars = 500;

  Future<void> _checkGrammar() async {
    final text = _textCtrl.text.trim();
    if (text.isEmpty) return;

    setState(() {
      _isLoading = true;
      _hasResult = false;
      _errorMsg = null;
    });

    final result = await ApiService.checkGrammar(text);

    if (!mounted) return;

    setState(() {
      _isLoading = false;
      if (result.containsKey('error')) {
        _errorMsg = result['error'];
        _hasResult = false;
      } else {
        _hasResult = true;
        _correctedText =
            result['corrected_text']?.toString() ?? text;
        _isCorrect = result['is_correct'] == true;
        _corrections = (result['corrections'] as List?)
                ?.map((e) => Map<String, dynamic>.from(e as Map))
                .toList() ??
            [];
      }
    });
  }

  void _tryExample() {
    _textCtrl.text =
        'I goed to the store yesterday and buyed some foods for my familys.';
    setState(() {
      _hasResult = false;
      _errorMsg = null;
    });
  }

  void _clearText() {
    _textCtrl.clear();
    setState(() {
      _hasResult = false;
      _errorMsg = null;
    });
  }

  @override
  void dispose() {
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
                  .scale(begin: const Offset(0.9, 0.9), end: const Offset(1, 1)),
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
        icon: const Icon(Icons.arrow_back_ios_new_rounded,
            color: _textPrimary, size: 20),
        onPressed: () {
          if (context.canPop()) {
            context.pop();
          } else {
            context.go('/practice');
          }
        },
      ),
      title: ShaderMask(
        shaderCallback: (b) => const LinearGradient(
          colors: [_primary, _accent],
        ).createShader(b),
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
            color: _accent.withOpacity(0.15),
            borderRadius: BorderRadius.circular(10),
          ),
          child: const Icon(Icons.auto_awesome_rounded,
              color: _accent, size: 20),
        ),
      ],
      bottom: PreferredSize(
        preferredSize: const Size.fromHeight(1),
        child: Container(height: 1, color: _border),
      ),
    );
  }

  Widget _buildInputCard() {
    final charCount = _textCtrl.text.length;
    return Container(
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: _border, width: 1),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.25),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        children: [
          TextField(
            controller: _textCtrl,
            maxLines: 6,
            maxLength: _maxChars,
            style: GoogleFonts.inter(
              color: _textPrimary,
              fontSize: 15,
              height: 1.6,
            ),
            onChanged: (_) => setState(() {}),
            decoration: InputDecoration(
              hintText: 'Type or paste your English text here…',
              hintStyle: GoogleFonts.inter(
                  color: _textSecondary, fontSize: 15),
              filled: true,
              fillColor: Colors.transparent,
              counterText: '',
              contentPadding: const EdgeInsets.all(18),
              border: InputBorder.none,
            ),
          ),
          Container(
            height: 1,
            color: _border.withOpacity(0.5),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(
                horizontal: 14, vertical: 10),
            child: Row(
              children: [
                // Character count
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: charCount > _maxChars * 0.9
                        ? _error.withOpacity(0.15)
                        : _primary.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    '$charCount/$_maxChars',
                    style: GoogleFonts.inter(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: charCount > _maxChars * 0.9
                          ? _error
                          : _primary,
                    ),
                  ),
                ),
                const Spacer(),
                // Clear button
                if (_textCtrl.text.isNotEmpty)
                  GestureDetector(
                    onTap: _clearText,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        border: Border.all(
                            color: _textSecondary.withOpacity(0.4)),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        'Clear',
                        style: GoogleFonts.inter(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: _textSecondary,
                        ),
                      ),
                    ),
                  ),
                const SizedBox(width: 8),
                // Try example
                GestureDetector(
                  onTap: _tryExample,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: _accent.withOpacity(0.12),
                      border: Border.all(
                          color: _accent.withOpacity(0.3)),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      '💡 Try Example',
                      style: GoogleFonts.inter(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: _accent,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    ).animate().fadeIn(duration: 400.ms).slideY(begin: -0.05, end: 0);
  }

  Widget _buildCheckButton() {
    final isEnabled = _textCtrl.text.trim().isNotEmpty && !_isLoading;
    return GestureDetector(
      onTap: isEnabled ? _checkGrammar : null,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        height: 56,
        decoration: BoxDecoration(
          gradient: isEnabled
              ? const LinearGradient(
                  colors: [_primary, _accent],
                  begin: Alignment.centerLeft,
                  end: Alignment.centerRight,
                )
              : null,
          color: isEnabled ? null : _surfaceCard,
          borderRadius: BorderRadius.circular(16),
          boxShadow: isEnabled
              ? [
                  BoxShadow(
                    color: _primary.withOpacity(0.35),
                    blurRadius: 16,
                    offset: const Offset(0, 6),
                  ),
                ]
              : null,
        ),
        child: Center(
          child: _isLoading
              ? const SizedBox(
                  width: 24,
                  height: 24,
                  child: CircularProgressIndicator(
                    color: Colors.white,
                    strokeWidth: 2.5,
                  ),
                )
              : Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.spellcheck_rounded,
                      color: isEnabled
                          ? Colors.white
                          : _textSecondary,
                      size: 20,
                    ),
                    const SizedBox(width: 10),
                    Text(
                      'Check Grammar ✨',
                      style: GoogleFonts.inter(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: isEnabled
                            ? Colors.white
                            : _textSecondary,
                      ),
                    ),
                  ],
                ),
        ),
      ),
    );
  }

  Widget _buildErrorCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _error.withOpacity(0.1),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: _error.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline_rounded,
              color: _error, size: 22),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              _errorMsg ?? 'An error occurred',
              style: GoogleFonts.inter(
                  color: _error, fontSize: 13, height: 1.4),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.refresh_rounded,
                color: _error, size: 20),
            onPressed: _checkGrammar,
          ),
        ],
      ),
    ).animate().fadeIn(duration: 300.ms).shake(hz: 2, duration: 400.ms);
  }

  Widget _buildStatusCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: _isCorrect
              ? [_success.withOpacity(0.12), _success.withOpacity(0.05)]
              : [_accent.withOpacity(0.12), _primary.withOpacity(0.05)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: _isCorrect
              ? _success.withOpacity(0.3)
              : _accent.withOpacity(0.3),
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              color: _isCorrect
                  ? _success.withOpacity(0.2)
                  : _accent.withOpacity(0.2),
              shape: BoxShape.circle,
            ),
            child: Icon(
              _isCorrect
                  ? Icons.check_circle_rounded
                  : Icons.edit_note_rounded,
              color: _isCorrect ? _success : _accent,
              size: 28,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _isCorrect
                      ? 'Perfect! ✨'
                      : '${_corrections.length} Correction${_corrections.length == 1 ? '' : 's'} Found',
                  style: GoogleFonts.inter(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: _isCorrect ? _success : _textPrimary,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  _isCorrect
                      ? 'Your grammar is correct. Well done!'
                      : 'RoBERTa detected some issues. See below.',
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    color: _textSecondary,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCorrectedTextCard() {
    return Container(
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 8, 0),
            child: Row(
              children: [
                const Icon(Icons.auto_fix_high_rounded,
                    color: _success, size: 18),
                const SizedBox(width: 8),
                Text(
                  'Corrected Text',
                  style: GoogleFonts.inter(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: _success,
                  ),
                ),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.copy_rounded,
                      color: _textSecondary, size: 18),
                  tooltip: 'Copy corrected text',
                  onPressed: () {
                    Clipboard.setData(
                        ClipboardData(text: _correctedText));
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(
                          'Corrected text copied!',
                          style: GoogleFonts.inter(),
                        ),
                        backgroundColor: _success,
                        behavior: SnackBarBehavior.floating,
                        shape: RoundedRectangleBorder(
                            borderRadius:
                                BorderRadius.circular(10)),
                      ),
                    );
                  },
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
            child: Text(
              _correctedText,
              style: GoogleFonts.inter(
                fontSize: 15,
                color: _textPrimary,
                height: 1.6,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCorrectionsList() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Text(
            'Details',
            style: GoogleFonts.inter(
              fontSize: 16,
              fontWeight: FontWeight.w700,
              color: _textPrimary,
            ),
          ),
        ),
        ...List.generate(_corrections.length, (i) {
          final c = _corrections[i];
          return _CorrectionCard(
            original: c['original']?.toString() ?? '',
            corrected: c['corrected']?.toString() ?? '',
            explanation: c['explanation']?.toString() ?? '',
            index: i,
          )
              .animate(delay: Duration(milliseconds: 80 * i + 200))
              .fadeIn(duration: 350.ms)
              .slideX(begin: 0.08, end: 0);
        }),
      ],
    );
  }
}

// ── Correction Card ──────────────────────────────────────────
class _CorrectionCard extends StatelessWidget {
  final String original;
  final String corrected;
  final String explanation;
  final int index;

  const _CorrectionCard({
    required this.original,
    required this.corrected,
    required this.explanation,
    required this.index,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(14),
        border:
            Border(left: BorderSide(color: _accent, width: 3)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.15),
            blurRadius: 8,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Original → Corrected
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Text(
                    original,
                    style: GoogleFonts.inter(
                      fontSize: 14,
                      color: _error,
                      decoration: TextDecoration.lineThrough,
                      decorationColor: _error.withOpacity(0.7),
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                Padding(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10),
                  child: Icon(Icons.arrow_forward_rounded,
                      color: _textSecondary, size: 18),
                ),
                Expanded(
                  child: Text(
                    corrected,
                    style: GoogleFonts.inter(
                      fontSize: 14,
                      color: _success,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
            if (explanation.isNotEmpty) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: _primary.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.lightbulb_outline_rounded,
                        color: _primary.withOpacity(0.7),
                        size: 16),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        explanation,
                        style: GoogleFonts.inter(
                          fontSize: 12,
                          color: _textSecondary,
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
