part of 'news_tab.dart';

class _MiniPlayer extends StatelessWidget {
  final _Article? article;
  final double progress;
  final AnimationController eqController;
  final ValueChanged<double> onProgressChanged;
  final VoidCallback onStop;

  const _MiniPlayer({
    required this.article,
    required this.progress,
    required this.eqController,
    required this.onProgressChanged,
    required this.onStop,
  });

  @override
  Widget build(BuildContext context) {
    if (article == null) return const SizedBox.shrink();

    return Container(
      height: 86,
      decoration: BoxDecoration(
        color: const Color(0xFF1A2235),
        border: Border(top: BorderSide(color: Colors.transparent, width: 0)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.6),
            blurRadius: 24,
            offset: const Offset(0, -4),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Top gradient border
          Container(
            height: 2,
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [_kPrimary, _kAccent, _kPrimary],
              ),
            ),
          ),

          Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  // Equalizer animation
                  _EqualizerBars(controller: eqController),

                  const SizedBox(width: 14),

                  // Title + label + slider
                  Expanded(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Now Playing',
                          style: GoogleFonts.inter(
                            fontSize: 10,
                            color: _kPrimary,
                            fontWeight: FontWeight.w600,
                            letterSpacing: 0.5,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          article!.title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: GoogleFonts.inter(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: _kTextPrimary,
                          ),
                        ),
                        const SizedBox(height: 2),
                        SliderTheme(
                          data: SliderThemeData(
                            trackHeight: 2.5,
                            thumbShape: const RoundSliderThumbShape(
                              enabledThumbRadius: 5,
                            ),
                            overlayShape: const RoundSliderOverlayShape(
                              overlayRadius: 10,
                            ),
                            activeTrackColor: _kPrimary,
                            inactiveTrackColor: _kBorder,
                            thumbColor: _kPrimary,
                            overlayColor: _kPrimary.withValues(alpha: 0.15),
                          ),
                          child: Slider(
                            value: progress,
                            onChanged: onProgressChanged,
                            min: 0,
                            max: 1,
                          ),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(width: 8),

                  // Pause / stop button
                  GestureDetector(
                    onTap: onStop,
                    child: Container(
                      width: 38,
                      height: 38,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: const LinearGradient(
                          colors: [_kPrimary, _kAccent],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: _kPrimary.withValues(alpha: 0.4),
                            blurRadius: 10,
                            offset: const Offset(0, 3),
                          ),
                        ],
                      ),
                      child: const Icon(
                        Icons.pause_rounded,
                        color: Colors.white,
                        size: 20,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Animated equalizer bars
// ---------------------------------------------------------------------------

class _EqualizerBars extends StatelessWidget {
  final AnimationController controller;

  const _EqualizerBars({required this.controller});

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        final t = controller.value;
        // Stagger each bar with a different phase
        final h1 = _barHeight(t, 0.0);
        final h2 = _barHeight(t, 0.33);
        final h3 = _barHeight(t, 0.66);

        return Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            _Bar(height: h1, color: _kPrimary),
            const SizedBox(width: 3),
            _Bar(height: h2, color: _kAccent),
            const SizedBox(width: 3),
            _Bar(height: h3, color: _kPrimary),
          ],
        );
      },
    );
  }

  double _barHeight(double t, double phase) {
    final shifted = (t + phase) % 1.0;
    // Simple sine-like interpolation using lerp
    final sin = (shifted < 0.5) ? shifted * 2 : (1 - shifted) * 2;
    return 8 + sin * 20;
  }
}

class _Bar extends StatelessWidget {
  final double height;
  final Color color;

  const _Bar({required this.height, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 4,
      height: height,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(2),
      ),
    );
  }
}
