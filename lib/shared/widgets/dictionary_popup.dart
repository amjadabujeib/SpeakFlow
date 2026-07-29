// lib/shared/widgets/dictionary_popup.dart
import 'package:flutter/material.dart';
import 'package:speakflow/core/theme/local_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../core/theme/app_colors.dart';
import '../../core/services/api_service.dart';

typedef DictionaryLookup = Future<Map<String, dynamic>> Function(String word);

class DictionaryPopup extends StatelessWidget {
  final String word;
  final Offset tapPosition;
  final DictionaryLookup lookup;

  DictionaryPopup({
    super.key,
    required this.word,
    required this.tapPosition,
    DictionaryLookup? lookup,
  }) : lookup = lookup ?? ApiService.lookupWord;

  static void show(BuildContext context, String word, Offset globalPosition) {
    showDialog(
      context: context,
      barrierColor: Colors.transparent,
      builder: (_) => DictionaryPopup(word: word, tapPosition: globalPosition),
    );
  }

  @override
  Widget build(BuildContext context) {
    final screenSize = MediaQuery.of(context).size;

    double left = tapPosition.dx - 150;
    double top = tapPosition.dy + 20;

    // Keep within screen bounds
    left = left.clamp(16.0, screenSize.width - 316.0);
    if (top + 260 > screenSize.height - 100) {
      top = tapPosition.dy - 280;
    }

    return GestureDetector(
      onTap: () => Navigator.pop(context),
      child: Material(
        color: Colors.transparent,
        child: Stack(
          children: [
            Positioned(
              left: left,
              top: top,
              child: _LivePopupCard(word: word, lookup: lookup),
            ),
          ],
        ),
      ),
    );
  }
}

/// Fetches dictionary data for exactly the selected word.
class _LivePopupCard extends StatefulWidget {
  final String word;
  final DictionaryLookup lookup;

  const _LivePopupCard({required this.word, required this.lookup});

  @override
  State<_LivePopupCard> createState() => _LivePopupCardState();
}

class _LivePopupCardState extends State<_LivePopupCard> {
  Map<String, dynamic>? _data;
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchDefinition();
  }

  Future<void> _fetchDefinition() async {
    final result = await widget.lookup(widget.word);
    if (!mounted) return;
    setState(() {
      _isLoading = false;
      if (result.containsKey('error')) {
        _data = {'word': widget.word};
        _error = result['error']?.toString() ?? 'Lookup failed.';
      } else {
        _data = {...result, 'word': widget.word};
        _error = null;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Container(
          width: 300,
          decoration: BoxDecoration(
            color: AppColors.surfaceCard,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.borderLight),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.5),
                blurRadius: 30,
                offset: const Offset(0, 10),
              ),
              BoxShadow(
                color: AppColors.primary.withValues(alpha: 0.08),
                blurRadius: 20,
                offset: const Offset(0, 0),
              ),
            ],
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                // Top gradient bar
                Container(
                  height: 3,
                  decoration: const BoxDecoration(
                    gradient: AppColors.primaryGradient,
                  ),
                ),
                if (_isLoading) _buildLoadingState() else _buildContent(),
              ],
            ),
          ),
        )
        .animate()
        .fadeIn(duration: 250.ms)
        .scale(
          begin: const Offset(0.92, 0.92),
          end: const Offset(1, 1),
          duration: 250.ms,
        );
  }

  Widget _buildLoadingState() {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          Text(
            widget.word,
            style: GoogleFonts.inter(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 16),
          const SizedBox(
            width: 24,
            height: 24,
            child: CircularProgressIndicator(
              color: AppColors.primary,
              strokeWidth: 2,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Looking up…',
            style: GoogleFonts.inter(
              fontSize: 12,
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildContent() {
    final data = _data ?? {'word': widget.word};
    final ipa = data['phonetic']?.toString() ?? data['ipa']?.toString() ?? '';
    final partOfSpeech =
        data['part_of_speech']?.toString() ??
        data['partOfSpeech']?.toString() ??
        '';
    final translation =
        data['arabic_translation']?.toString() ??
        data['translation']?.toString() ??
        '';
    final definition = data['definition']?.toString() ?? '';
    final example =
        data['example_sentence']?.toString() ??
        data['example']?.toString() ??
        '';

    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Word + speaker
          Row(
            children: [
              Expanded(
                child: Text(
                  data['word']?.toString() ?? widget.word,
                  style: GoogleFonts.inter(
                    fontSize: 20,
                    fontWeight: FontWeight.w700,
                    color: AppColors.textPrimary,
                  ),
                ),
              ),
              GestureDetector(
                onTap: () {},
                child: Container(
                  width: 34,
                  height: 34,
                  decoration: BoxDecoration(
                    gradient: AppColors.primaryGradient,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    Icons.volume_up_rounded,
                    color: Colors.white,
                    size: 16,
                  ),
                ),
              ),
            ],
          ),
          if (_error case final error?) ...[
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.error.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: AppColors.error.withValues(alpha: 0.3),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Could not look up “${widget.word}”.',
                    style: GoogleFonts.inter(
                      color: AppColors.textPrimary,
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    error,
                    style: GoogleFonts.inter(
                      color: AppColors.textSecondary,
                      fontSize: 11,
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextButton.icon(
                    onPressed: () {
                      setState(() {
                        _isLoading = true;
                        _error = null;
                      });
                      _fetchDefinition();
                    },
                    icon: const Icon(Icons.refresh_rounded, size: 17),
                    label: const Text('Try again'),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 4),
          // IPA + part of speech
          Row(
            children: [
              if (ipa.isNotEmpty)
                Text(
                  ipa,
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    color: AppColors.accent,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              if (ipa.isNotEmpty && partOfSpeech.isNotEmpty)
                const SizedBox(width: 8),
              if (partOfSpeech.isNotEmpty)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    partOfSpeech,
                    style: GoogleFonts.inter(
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                      color: AppColors.primary,
                    ),
                  ),
                ),
            ],
          ),
          if (translation.isNotEmpty) ...[
            const SizedBox(height: 10),
            // Translation
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: AppColors.accent.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: AppColors.accent.withValues(alpha: 0.2),
                ),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.translate_rounded,
                    color: AppColors.accent,
                    size: 14,
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      translation,
                      style: GoogleFonts.inter(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: AppColors.accentLight,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
          if (definition.isNotEmpty) ...[
            const SizedBox(height: 10),
            // Definition
            Text(
              definition,
              style: GoogleFonts.inter(
                fontSize: 12,
                color: AppColors.textSecondary,
                height: 1.5,
              ),
            ),
          ],
          if (example.isNotEmpty) ...[
            const SizedBox(height: 8),
            // Example
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppColors.surfaceElevated,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '"',
                    style: GoogleFonts.inter(
                      fontSize: 18,
                      color: AppColors.primary,
                      fontWeight: FontWeight.w700,
                      height: 1.2,
                    ),
                  ),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      example,
                      style: GoogleFonts.inter(
                        fontSize: 12,
                        color: AppColors.textSecondary,
                        fontStyle: FontStyle.italic,
                        height: 1.5,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// Mixin to add long-press dictionary feature to any text
mixin DictionaryMixin {
  void showDictionaryForWord(
    BuildContext context,
    String word,
    Offset position,
  ) {
    DictionaryPopup.show(context, word, position);
  }
}
