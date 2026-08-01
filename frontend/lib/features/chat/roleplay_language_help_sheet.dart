import 'package:flutter/material.dart';
import 'package:speakflow/core/theme/local_fonts.dart';

import '../../app/providers.dart';
import 'roleplay_models.dart';

const _card = Color(0xFF1A2235);
const _primary = Color(0xFF4F7FFF);
const _error = Color(0xFFEF4444);
const _text = Color(0xFFF1F5FF);
const _muted = Color(0xFF8896B0);
const _border = Color(0xFF263550);

class RoleplayLanguageHelpSheet extends StatefulWidget {
  final List<RoleplayObjective> objectives;
  final List<String> phrases;
  final ValueChanged<String> onSelect;

  const RoleplayLanguageHelpSheet({
    super.key,
    required this.objectives,
    required this.phrases,
    required this.onSelect,
  });

  @override
  State<RoleplayLanguageHelpSheet> createState() =>
      _RoleplayLanguageHelpSheetState();
}

class _RoleplayLanguageHelpSheetState extends State<RoleplayLanguageHelpSheet> {
  final TextEditingController _arabicController = TextEditingController();
  List<RoleplayEscapeOption> _options = const [];
  bool _loading = false;
  String? _errorMessage;

  Future<void> _generateOptions() async {
    final source = _arabicController.text.trim();
    if (source.isEmpty || _loading) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _loading = true;
      _errorMessage = null;
      _options = const [];
    });
    try {
      final result = await AppDependencies.instance.roleplay
          .arabicTranslationOptions(source);
      final rawOptions = result['options'];
      if (rawOptions is! List) {
        throw const FormatException('Missing English options');
      }
      final options = rawOptions
          .whereType<Map>()
          .map(
            (item) =>
                RoleplayEscapeOption.fromJson(Map<String, dynamic>.from(item)),
          )
          .where((item) => item.text.isNotEmpty)
          .toList(growable: false);
      if (options.length != 3) {
        throw const FormatException('Expected three English options');
      }
      if (mounted) setState(() => _options = options);
    } catch (error) {
      if (!mounted) return;
      final detail = error.toString().toLowerCase();
      final serviceUnavailable =
          detail.contains('connection refused') ||
          detail.contains('failed host lookup') ||
          detail.contains('clientexception') ||
          detail.contains('socketexception') ||
          detail.contains('timed out');
      setState(
        () => _errorMessage = serviceUnavailable
            ? 'The learning service is offline. Reconnect the backend, then try again.'
            : 'I could not create the English options. Please try again.',
      );
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _arabicController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: AnimatedPadding(
        duration: const Duration(milliseconds: 180),
        padding: EdgeInsets.only(
          bottom: MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxHeight: MediaQuery.sizeOf(context).height * .82,
          ),
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const _SheetHandle(),
                const SizedBox(height: 18),
                Text(
                  'Say what you mean',
                  style: GoogleFonts.inter(
                    color: _text,
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  widget.objectives.isEmpty
                      ? 'All goals complete. Keep chatting freely, or end whenever you’re ready.'
                      : 'Next goal: ${widget.objectives.first.label}',
                  style: GoogleFonts.inter(
                    color: _muted,
                    fontSize: 12,
                    height: 1.45,
                  ),
                ),
                const SizedBox(height: 16),
                _arabicInput(),
                const SizedBox(height: 10),
                _generateButton(),
                if (_errorMessage != null) ...[
                  const SizedBox(height: 10),
                  Text(
                    _errorMessage!,
                    style: GoogleFonts.inter(color: _error, fontSize: 12),
                  ),
                ],
                if (_options.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  for (final option in _options) _optionTile(option),
                ],
                if (widget.phrases.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Text(
                    'Or use a sentence starter',
                    style: GoogleFonts.inter(
                      color: _muted,
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 4),
                  for (final phrase in widget.phrases) _phraseTile(phrase),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _arabicInput() {
    return TextField(
      controller: _arabicController,
      minLines: 2,
      maxLines: 4,
      textDirection: TextDirection.rtl,
      textInputAction: TextInputAction.done,
      onSubmitted: (_) => _generateOptions(),
      style: GoogleFonts.inter(color: _text, fontSize: 14),
      decoration: InputDecoration(
        hintText: 'اكتب ما تريد قوله بالعربية',
        hintTextDirection: TextDirection.rtl,
        hintStyle: GoogleFonts.inter(color: _muted),
        filled: true,
        fillColor: _card,
        border: _inputBorder(_border),
        enabledBorder: _inputBorder(_border),
        focusedBorder: _inputBorder(_primary),
      ),
    );
  }

  Widget _generateButton() {
    return SizedBox(
      width: double.infinity,
      child: FilledButton.icon(
        onPressed: _loading ? null : _generateOptions,
        style: FilledButton.styleFrom(
          backgroundColor: _primary,
          foregroundColor: Colors.white,
          disabledBackgroundColor: _primary.withValues(alpha: .45),
          padding: const EdgeInsets.symmetric(vertical: 13),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(13),
          ),
        ),
        icon: _loading
            ? const SizedBox.square(
                dimension: 17,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Colors.white,
                ),
              )
            : const Icon(Icons.translate_rounded, size: 19),
        label: Text(_loading ? 'Creating options…' : 'Show me 3 ways'),
      ),
    );
  }

  Widget _optionTile(RoleplayEscapeOption option) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 9),
      child: Material(
        color: _card,
        borderRadius: BorderRadius.circular(14),
        child: InkWell(
          borderRadius: BorderRadius.circular(14),
          onTap: () => _select(option.text),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: _primary.withValues(alpha: .14),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    option.label,
                    style: GoogleFonts.inter(
                      color: _primary,
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    option.text,
                    style: GoogleFonts.inter(
                      color: _text,
                      fontSize: 13,
                      height: 1.4,
                    ),
                  ),
                ),
                const Icon(Icons.north_west_rounded, color: _muted, size: 17),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _phraseTile(String phrase) {
    return ListTile(
      dense: true,
      contentPadding: EdgeInsets.zero,
      leading: const Icon(
        Icons.arrow_forward_rounded,
        color: _primary,
        size: 18,
      ),
      title: Text(phrase, style: GoogleFonts.inter(color: _text, fontSize: 14)),
      subtitle: Text(
        'Tap to use as a sentence starter',
        style: GoogleFonts.inter(color: _muted, fontSize: 10),
      ),
      onTap: () => _select('$phrase '),
    );
  }

  void _select(String value) {
    widget.onSelect(value);
    Navigator.pop(context);
  }

  static OutlineInputBorder _inputBorder(Color color) {
    return OutlineInputBorder(
      borderRadius: BorderRadius.circular(14),
      borderSide: BorderSide(color: color),
    );
  }
}

class _SheetHandle extends StatelessWidget {
  const _SheetHandle();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Container(
        width: 42,
        height: 4,
        decoration: BoxDecoration(
          color: _muted.withValues(alpha: .4),
          borderRadius: BorderRadius.circular(4),
        ),
      ),
    );
  }
}
