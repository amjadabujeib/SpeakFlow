part of 'news_tab.dart';

class _ArticleCard extends StatefulWidget {
  final _Article article;
  final bool isPlaying;
  final bool isBuffering;
  final VoidCallback onPlayToggle;

  const _ArticleCard({
    super.key,
    required this.article,
    required this.isPlaying,
    required this.isBuffering,
    required this.onPlayToggle,
  });

  @override
  State<_ArticleCard> createState() => _ArticleCardState();
}

class _ArticleCardState extends State<_ArticleCard> {
  bool _expanded = false;

  void _handleWordLongPress(String word, Offset position) {
    DictionaryPopup.show(context, word, position);
  }

  @override
  Widget build(BuildContext context) {
    final article = widget.article;
    final catColor = _categoryColor(article.category);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: GestureDetector(
        onTap: () => setState(() => _expanded = !_expanded),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          decoration: BoxDecoration(
            color: _kSurface,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: _kBorder, width: 1),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.30),
                blurRadius: 18,
                offset: const Offset(0, 6),
              ),
              if (widget.isPlaying || widget.isBuffering)
                BoxShadow(
                  color: _kPrimary.withValues(alpha: 0.18),
                  blurRadius: 22,
                  spreadRadius: 2,
                ),
            ],
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Top accent line
                Container(
                  height: 3,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [catColor, catColor.withValues(alpha: 0.3)],
                    ),
                  ),
                ),

                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Top meta row
                      _buildMetaRow(article, catColor),

                      const SizedBox(height: 10),

                      // Title
                      Text(
                        article.title,
                        style: GoogleFonts.inter(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                          color: _kTextPrimary,
                          height: 1.25,
                          letterSpacing: -0.2,
                        ),
                      ),

                      // Expandable body
                      AnimatedSize(
                        duration: const Duration(milliseconds: 300),
                        curve: Curves.easeInOutCubic,
                        child: _expanded
                            ? _buildExpandedBody(article)
                            : const SizedBox.shrink(),
                      ),

                      const SizedBox(height: 12),

                      // Bottom row
                      _buildBottomRow(article),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildMetaRow(_Article article, Color catColor) {
    return Row(
      children: [
        // Category chip
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
          decoration: BoxDecoration(
            color: catColor.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: catColor.withValues(alpha: 0.35),
              width: 1,
            ),
          ),
          child: Text(
            article.category,
            style: GoogleFonts.inter(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: catColor,
            ),
          ),
        ),

        const SizedBox(width: 8),

        // Level badge
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: _kPrimary.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: _kPrimary.withValues(alpha: 0.30),
              width: 1,
            ),
          ),
          child: Text(
            article.level,
            style: GoogleFonts.inter(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: _kPrimary,
            ),
          ),
        ),

        const Spacer(),

        AnimatedRotation(
          turns: _expanded ? 0.5 : 0,
          duration: const Duration(milliseconds: 260),
          child: const Icon(
            Icons.keyboard_arrow_down_rounded,
            size: 18,
            color: _kTextSecondary,
          ),
        ),
      ],
    );
  }

  Widget _buildExpandedBody(_Article article) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 12),

        // Divider
        Container(
          height: 1,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [Colors.transparent, _kBorder, Colors.transparent],
            ),
          ),
        ),

        const SizedBox(height: 10),

        // Hint
        Row(
          children: [
            const Icon(Icons.touch_app_rounded, size: 13, color: _kAccent),
            const SizedBox(width: 5),
            Text(
              'Tap any word to look it up',
              style: GoogleFonts.inter(
                fontSize: 11,
                color: _kAccent,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),

        const SizedBox(height: 10),

        // Selectable body with per-word long-press
        _WordTapText(text: article.body, onWordLongPress: _handleWordLongPress),
      ],
    );
  }

  Widget _buildBottomRow(_Article article) {
    return Row(
      children: [
        // Play / Pause / Buffer button
        GestureDetector(
          onTap: widget.isBuffering ? null : widget.onPlayToggle,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 220),
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                colors: (widget.isPlaying || widget.isBuffering)
                    ? [_kAccent, _kPrimary]
                    : [_kPrimary, _kAccent],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              boxShadow: [
                BoxShadow(
                  color: _kPrimary.withValues(alpha: 0.4),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: widget.isBuffering
                ? const Padding(
                    padding: EdgeInsets.all(10),
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : Icon(
                    widget.isPlaying
                        ? Icons.pause_rounded
                        : Icons.play_arrow_rounded,
                    color: Colors.white,
                    size: 22,
                  ),
          ),
        ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Word-tap text widget (long-press individual word → dictionary)
// ---------------------------------------------------------------------------

class _WordTapText extends StatelessWidget {
  final String text;
  final void Function(String word, Offset globalPosition) onWordLongPress;

  const _WordTapText({required this.text, required this.onWordLongPress});

  @override
  Widget build(BuildContext context) {
    final words = text.split(' ');
    return SelectableText.rich(
      TextSpan(
        children: words.asMap().entries.map((entry) {
          final i = entry.key;
          final word = entry.value;
          return WidgetSpan(
            child: GestureDetector(
              onTapUp: (details) {
                final clean = _cleanLookupWord(word);
                if (clean.isNotEmpty) {
                  onWordLongPress(clean, details.globalPosition);
                }
              },
              onLongPressStart: (details) {
                final clean = _cleanLookupWord(word);
                if (clean.isNotEmpty) {
                  onWordLongPress(clean, details.globalPosition);
                }
              },
              child: Text(
                i == words.length - 1 ? word : '$word ',
                style: GoogleFonts.inter(
                  fontSize: 14,
                  color: _kTextPrimary.withValues(alpha: 0.88),
                  height: 1.65,
                ),
              ),
            ),
          );
        }).toList(),
      ),
      enableInteractiveSelection: true,
    );
  }

  String _cleanLookupWord(String value) =>
      value.replaceAll(RegExp(r"^[^A-Za-z']+|[^A-Za-z']+$"), '').trim();
}

// ---------------------------------------------------------------------------
// Mini Player
// ---------------------------------------------------------------------------
