part of 'onboarding_screen.dart';

class _StepInterests extends StatelessWidget {
  final Set<String> selected;
  final List<String> allInterests;
  final TextEditingController controller;
  final ValueChanged<String> onToggle;
  final ValueChanged<String> onAdd;

  const _StepInterests({
    required this.selected,
    required this.allInterests,
    required this.controller,
    required this.onToggle,
    required this.onAdd,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _StepHeader(
          emoji: '✨',
          title: 'Your interests',
          subtitle: 'Pick topics you love — we\'ll tailor your content',
        ),
        const SizedBox(height: 24),
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: allInterests.asMap().entries.map((entry) {
                    final index = entry.key;
                    final interest = entry.value;
                    final isSelected = selected.contains(interest);
                    return _InterestChip(
                          label: interest,
                          isSelected: isSelected,
                          onTap: () => onToggle(interest),
                        )
                        .animate()
                        .fadeIn(delay: (index * 40).ms, duration: 300.ms)
                        .scale(
                          begin: const Offset(0.85, 0.85),
                          duration: 300.ms,
                          curve: Curves.easeOutBack,
                        );
                  }).toList(),
                ),
                const SizedBox(height: 24),
                Text(
                  'Add your own',
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: _textSecondary,
                  ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: controller,
                        style: GoogleFonts.inter(
                          color: _textPrimary,
                          fontSize: 14,
                        ),
                        decoration: InputDecoration(
                          hintText: 'e.g. Cooking, Anime...',
                          hintStyle: GoogleFonts.inter(
                            color: _textMuted,
                            fontSize: 14,
                          ),
                          filled: true,
                          fillColor: _surfaceElevated,
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 14,
                          ),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: const BorderSide(color: _border),
                          ),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: const BorderSide(color: _border),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: const BorderSide(
                              color: _primary,
                              width: 1.5,
                            ),
                          ),
                        ),
                        onSubmitted: onAdd,
                      ),
                    ),
                    const SizedBox(width: 10),
                    GestureDetector(
                      onTap: () => onAdd(controller.text.trim()),
                      child: Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [_primary, _accent],
                          ),
                          borderRadius: BorderRadius.circular(12),
                          boxShadow: [
                            BoxShadow(
                              color: _primary.withValues(alpha: 0.3),
                              blurRadius: 12,
                              offset: const Offset(0, 4),
                            ),
                          ],
                        ),
                        child: const Icon(
                          Icons.add,
                          color: Colors.white,
                          size: 22,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _InterestChip extends StatefulWidget {
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const _InterestChip({
    required this.label,
    required this.isSelected,
    required this.onTap,
  });

  @override
  State<_InterestChip> createState() => _InterestChipState();
}

class _InterestChipState extends State<_InterestChip> {
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
        scale: _pressed ? 0.94 : 1.0,
        duration: const Duration(milliseconds: 100),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
          decoration: BoxDecoration(
            color: widget.isSelected
                ? _primary.withValues(alpha: 0.12)
                : _surfaceElevated,
            borderRadius: BorderRadius.circular(100),
            border: Border.all(
              color: widget.isSelected ? _primary : _border,
              width: widget.isSelected ? 1.5 : 1.0,
            ),
            boxShadow: widget.isSelected
                ? [
                    BoxShadow(
                      color: _primary.withValues(alpha: 0.15),
                      blurRadius: 10,
                    ),
                  ]
                : [],
          ),
          child: Text(
            widget.isSelected ? '✓  ${widget.label}' : widget.label,
            style: GoogleFonts.inter(
              fontSize: 13,
              fontWeight: widget.isSelected ? FontWeight.w700 : FontWeight.w500,
              color: widget.isSelected ? _primary : _textSecondary,
            ),
          ),
        ),
      ),
    );
  }
}

// ─── Step 4: Mother Tongue ─────────────────────────────────────────────────
