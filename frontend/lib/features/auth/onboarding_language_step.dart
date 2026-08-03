part of 'onboarding_screen.dart';

class _StepMotherTongue extends StatelessWidget {
  final String? selected;
  final ValueChanged<String?> onSelect;

  const _StepMotherTongue({required this.selected, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _StepHeader(
            emoji: '🌐',
            title: 'Mother tongue',
            subtitle: 'This helps us tailor explanations for you',
          ),
          const SizedBox(height: 32),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Select your native language',
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: _textSecondary,
                  ),
                ),
                const SizedBox(height: 12),
                Container(
                      decoration: BoxDecoration(
                        color: _surfaceElevated,
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(
                          color: selected != null ? _primary : _border,
                          width: selected != null ? 1.5 : 1.0,
                        ),
                        boxShadow: selected != null
                            ? [
                                BoxShadow(
                                  color: _primary.withValues(alpha: 0.15),
                                  blurRadius: 14,
                                ),
                              ]
                            : [],
                      ),
                      child: DropdownButtonFormField<String>(
                        initialValue: selected,
                        dropdownColor: const Color(0xFF151E30),
                        icon: const Icon(
                          Icons.keyboard_arrow_down_rounded,
                          color: _textSecondary,
                        ),
                        style: GoogleFonts.inter(
                          color: _textPrimary,
                          fontSize: 15,
                        ),
                        decoration: InputDecoration(
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 18,
                          ),
                          border: InputBorder.none,
                          hintText: 'Choose a language...',
                          hintStyle: GoogleFonts.inter(
                            color: _textMuted,
                            fontSize: 15,
                          ),
                        ),
                        items: _languages.map((lang) {
                          return DropdownMenuItem(
                            value: lang,
                            child: Text(
                              lang,
                              style: GoogleFonts.inter(
                                color: _textPrimary,
                                fontSize: 15,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          );
                        }).toList(),
                        onChanged: onSelect,
                      ),
                    )
                    .animate()
                    .fadeIn(delay: 200.ms, duration: 400.ms)
                    .slideY(begin: 0.3, end: 0, duration: 400.ms),
                const SizedBox(height: 32),
                // Info card
                Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: _primary.withValues(alpha: 0.06),
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(
                          color: _primary.withValues(alpha: 0.2),
                        ),
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(
                            Icons.info_outline_rounded,
                            color: _primary,
                            size: 20,
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              'We\'ll use your native language to explain grammar rules and new vocabulary in a way that makes sense to you.',
                              style: GoogleFonts.inter(
                                fontSize: 13,
                                color: _textSecondary,
                                height: 1.5,
                              ),
                            ),
                          ),
                        ],
                      ),
                    )
                    .animate()
                    .fadeIn(delay: 350.ms, duration: 400.ms)
                    .slideY(begin: 0.3, end: 0, duration: 400.ms),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
