part of 'onboarding_screen.dart';

class _StepGoal extends StatelessWidget {
  final String? selected;
  final ValueChanged<String> onSelect;

  const _StepGoal({required this.selected, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _StepHeader(
          emoji: '🎯',
          title: 'What\'s your goal?',
          subtitle: 'Pick your primary reason for learning',
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
                childAspectRatio: 1.7,
              ),
              itemCount: _goals.length,
              itemBuilder: (context, index) {
                final item = _goals[index];
                final label = item['label']!;
                final isSelected = selected == label;
                return _GoalCard(
                      icon: item['icon']!,
                      label: label,
                      isSelected: isSelected,
                      onTap: () => onSelect(label),
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

class _GoalCard extends StatefulWidget {
  final String icon;
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const _GoalCard({
    required this.icon,
    required this.label,
    required this.isSelected,
    required this.onTap,
  });

  @override
  State<_GoalCard> createState() => _GoalCardState();
}

class _GoalCardState extends State<_GoalCard> {
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
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            color: widget.isSelected
                ? _primary.withValues(alpha: 0.1)
                : _surfaceElevated,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: widget.isSelected ? _primary : _border,
              width: widget.isSelected ? 1.5 : 1.0,
            ),
            boxShadow: widget.isSelected
                ? [
                    BoxShadow(
                      color: _primary.withValues(alpha: 0.18),
                      blurRadius: 14,
                      spreadRadius: 1,
                    ),
                  ]
                : [],
          ),
          child: Row(
            children: [
              Text(widget.icon, style: const TextStyle(fontSize: 22)),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  widget.label,
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: widget.isSelected
                        ? FontWeight.w700
                        : FontWeight.w500,
                    color: widget.isSelected ? _textPrimary : _textSecondary,
                  ),
                ),
              ),
              if (widget.isSelected)
                Container(
                  width: 20,
                  height: 20,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: const LinearGradient(colors: [_primary, _accent]),
                  ),
                  child: const Icon(Icons.check, color: Colors.white, size: 12),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

// ─── Step 3: Interests ─────────────────────────────────────────────────────
