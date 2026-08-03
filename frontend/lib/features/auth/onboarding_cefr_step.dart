part of 'onboarding_screen.dart';

class _StepCefr extends StatelessWidget {
  final String? selected;
  final ValueChanged<String> onSelect;

  const _StepCefr({required this.selected, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _StepHeader(
          emoji: '📊',
          title: "What's your level?",
          subtitle: 'Choose the option that best describes you',
        ),
        const SizedBox(height: 24),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: GridView.builder(
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                childAspectRatio: 1.15,
              ),
              itemCount: _levels.length,
              itemBuilder: (context, index) {
                final item = _levels[index];
                final level = item['level']!;
                final isSelected = selected == level;
                return _CefrCard(
                      level: level,
                      title: item['title']!,
                      desc: item['desc']!,
                      isSelected: isSelected,
                      onTap: () => onSelect(level),
                    )
                    .animate()
                    .fadeIn(delay: (index * 60).ms, duration: 350.ms)
                    .slideY(begin: 0.25, end: 0, duration: 350.ms);
              },
            ),
          ),
        ),
      ],
    );
  }
}

class _CefrCard extends StatefulWidget {
  final String level;
  final String title;
  final String desc;
  final bool isSelected;
  final VoidCallback onTap;

  const _CefrCard({
    required this.level,
    required this.title,
    required this.desc,
    required this.isSelected,
    required this.onTap,
  });

  @override
  State<_CefrCard> createState() => _CefrCardState();
}

class _CefrCardState extends State<_CefrCard> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) {
        setState(() => _pressed = false);
        widget.onTap();
      },
      onTapCancel: () => setState(() => _pressed = false),
      child: AnimatedScale(
        scale: _pressed ? 0.96 : 1.0,
        duration: const Duration(milliseconds: 100),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 250),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: widget.isSelected
                ? _primary.withValues(alpha: 0.08)
                : _surfaceElevated,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: widget.isSelected ? _primary : _border,
              width: widget.isSelected ? 1.5 : 1.0,
            ),
            boxShadow: widget.isSelected
                ? [
                    BoxShadow(
                      color: _primary.withValues(alpha: 0.2),
                      blurRadius: 16,
                      spreadRadius: 1,
                    ),
                    BoxShadow(
                      color: _accent.withValues(alpha: 0.1),
                      blurRadius: 12,
                    ),
                  ]
                : [],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              // Level badge
              ShaderMask(
                shaderCallback: (bounds) => const LinearGradient(
                  colors: [_primary, _accent],
                ).createShader(bounds),
                child: Text(
                  widget.level,
                  style: GoogleFonts.inter(
                    fontSize: 28,
                    fontWeight: FontWeight.w900,
                    color: Colors.white,
                  ),
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    widget.title,
                    style: GoogleFonts.inter(
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: _textPrimary,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    widget.desc,
                    style: GoogleFonts.inter(
                      fontSize: 11,
                      color: _textSecondary,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ─── Step 2: Learning Goal ─────────────────────────────────────────────────
