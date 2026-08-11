part of 'settings_drawer.dart';

extension _SettingsDrawerBody on _SettingsDrawerState {
  Widget _buildDrawer(BuildContext context) {
    final auth = ref.watch(authSessionStoreProvider);
    const bg = AppColors.surface;
    const textPrimary = AppColors.textPrimary;
    const textSecondary = AppColors.textSecondary;
    const cardBg = AppColors.surfaceElevated;
    const border = AppColors.border;

    return Drawer(
      width: MediaQuery.of(context).size.width * 0.85,
      backgroundColor: bg,
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _settingsHeader(context, textPrimary, textSecondary),

            const SizedBox(height: 24),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                children: [
                  _SectionLabel(label: 'Appearance', textColor: textSecondary),
                  const SizedBox(height: 8),
                  // Font size
                  _SettingsCard(
                    bg: cardBg,
                    border: border,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Icon(
                              Icons.text_fields_rounded,
                              color: AppColors.primary,
                              size: 20,
                            ),
                            const SizedBox(width: 12),
                            Text(
                              'Font Size',
                              style: GoogleFonts.inter(
                                fontSize: 14,
                                fontWeight: FontWeight.w500,
                                color: textPrimary,
                              ),
                            ),
                            const Spacer(),
                            Text(
                              _fontSize == 0.85
                                  ? 'Small'
                                  : _fontSize == 1.0
                                  ? 'Medium'
                                  : _fontSize == 1.15
                                  ? 'Large'
                                  : 'X-Large',
                              style: GoogleFonts.inter(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: AppColors.primary,
                              ),
                            ),
                          ],
                        ),
                        Slider(
                          value: _fontSize,
                          min: 0.85,
                          max: 1.3,
                          divisions: 3,
                          activeColor: AppColors.primary,
                          inactiveColor: AppColors.border,
                          onChanged: (v) {
                            _update(() => _fontSize = v);
                            widget.appState.setFontSize(v);
                          },
                        ),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              'A',
                              style: GoogleFonts.inter(
                                fontSize: 11,
                                color: textSecondary,
                              ),
                            ),
                            Text(
                              'A',
                              style: GoogleFonts.inter(
                                fontSize: 14,
                                color: textSecondary,
                              ),
                            ),
                            Text(
                              'A',
                              style: GoogleFonts.inter(
                                fontSize: 17,
                                color: textSecondary,
                              ),
                            ),
                            Text(
                              'A',
                              style: GoogleFonts.inter(
                                fontSize: 20,
                                color: textSecondary,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 24),
                  _SectionLabel(label: 'Learning', textColor: textSecondary),

                  // Mother tongue
                  _SettingsCard(
                    bg: cardBg,
                    border: border,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Icon(
                              Icons.translate_rounded,
                              color: AppColors.accent,
                              size: 20,
                            ),
                            const SizedBox(width: 12),
                            Text(
                              'Mother Tongue',
                              style: GoogleFonts.inter(
                                fontSize: 14,
                                fontWeight: FontWeight.w500,
                                color: textPrimary,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        DropdownButtonFormField<String>(
                          initialValue: _selectedMotherTongue,
                          dropdownColor: cardBg,
                          style: GoogleFonts.inter(
                            fontSize: 14,
                            color: textPrimary,
                          ),
                          decoration: InputDecoration(
                            contentPadding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 10,
                            ),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(10),
                              borderSide: BorderSide(color: border),
                            ),
                            enabledBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(10),
                              borderSide: BorderSide(color: border),
                            ),
                            filled: true,
                            fillColor: AppColors.surface,
                          ),
                          items: _SettingsDrawerState._languages
                              .map(
                                (l) =>
                                    DropdownMenuItem(value: l, child: Text(l)),
                              )
                              .toList(),
                          onChanged: (v) {
                            if (v != null) {
                              _update(() => _selectedMotherTongue = v);
                              widget.appState.setMotherTongue(v);
                            }
                          },
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),

                  // CEFR Level
                  _SettingsCard(
                    bg: cardBg,
                    border: border,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Icon(
                              Icons.bar_chart_rounded,
                              color: AppColors.accent,
                              size: 20,
                            ),
                            const SizedBox(width: 12),
                            Text(
                              'CEFR Level',
                              style: GoogleFonts.inter(
                                fontSize: 14,
                                fontWeight: FontWeight.w500,
                                color: textPrimary,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: _SettingsDrawerState._levels.map((level) {
                            final isSelected = _selectedCefrLevel == level;
                            return GestureDetector(
                              onTap: () {
                                _update(() => _selectedCefrLevel = level);
                              },
                              child: AnimatedContainer(
                                duration: const Duration(milliseconds: 200),
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 16,
                                  vertical: 8,
                                ),
                                decoration: BoxDecoration(
                                  gradient: isSelected
                                      ? AppColors.primaryGradient
                                      : null,
                                  color: isSelected ? null : AppColors.surface,
                                  borderRadius: BorderRadius.circular(8),
                                  border: Border.all(
                                    color: isSelected
                                        ? Colors.transparent
                                        : border,
                                  ),
                                ),
                                child: Text(
                                  level,
                                  style: GoogleFonts.inter(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w600,
                                    color: isSelected
                                        ? Colors.white
                                        : textSecondary,
                                  ),
                                ),
                              ),
                            );
                          }).toList(),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),

                  // Interests
                  _SettingsCard(
                    bg: cardBg,
                    border: border,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Icon(
                              Icons.interests_rounded,
                              color: AppColors.accent,
                              size: 20,
                            ),
                            const SizedBox(width: 12),
                            Text(
                              'Interests',
                              style: GoogleFonts.inter(
                                fontSize: 14,
                                fontWeight: FontWeight.w500,
                                color: textPrimary,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: _SettingsDrawerState._interests.map((
                            interest,
                          ) {
                            final isSelected = _selectedInterests.contains(
                              interest,
                            );
                            return GestureDetector(
                              onTap: () {
                                _update(() {
                                  if (isSelected) {
                                    _selectedInterests.remove(interest);
                                  } else if (_selectedInterests.length < 3) {
                                    _selectedInterests.add(interest);
                                  }
                                });
                              },
                              child: AnimatedContainer(
                                duration: const Duration(milliseconds: 200),
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 12,
                                  vertical: 6,
                                ),
                                decoration: BoxDecoration(
                                  gradient: isSelected
                                      ? AppColors.primaryGradient
                                      : null,
                                  color: isSelected ? null : AppColors.surface,
                                  borderRadius: BorderRadius.circular(20),
                                  border: Border.all(
                                    color: isSelected
                                        ? Colors.transparent
                                        : border,
                                  ),
                                ),
                                child: Text(
                                  interest,
                                  style: GoogleFonts.inter(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w500,
                                    color: isSelected
                                        ? Colors.white
                                        : textSecondary,
                                  ),
                                ),
                              ),
                            );
                          }).toList(),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 24),

                  // Regenerate plan button
                  GestureDetector(
                    onTap: _loadingProfile || _regenerating
                        ? null
                        : _regeneratePlan,
                    child: Opacity(
                      opacity: _loadingProfile || _regenerating ? 0.65 : 1,
                      child: Container(
                        width: double.infinity,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        decoration: BoxDecoration(
                          gradient: AppColors.primaryGradient,
                          borderRadius: BorderRadius.circular(12),
                          boxShadow: [
                            BoxShadow(
                              color: AppColors.primary.withValues(alpha: 0.35),
                              blurRadius: 16,
                              offset: const Offset(0, 6),
                            ),
                          ],
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            if (_regenerating)
                              const SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.white,
                                ),
                              )
                            else
                              const Icon(
                                Icons.auto_awesome_rounded,
                                color: Colors.white,
                                size: 18,
                              ),
                            const SizedBox(width: 8),
                            Text(
                              _regenerating
                                  ? 'Creating your roadmap...'
                                  : 'Apply changes & build plan',
                              style: GoogleFonts.inter(
                                fontSize: 14,
                                fontWeight: FontWeight.w600,
                                color: Colors.white,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),
                  _SectionLabel(label: 'Account', textColor: textSecondary),
                  const SizedBox(height: 8),
                  _SettingsCard(
                    bg: cardBg,
                    border: border,
                    child: Row(
                      children: [
                        CircleAvatar(
                          backgroundColor: AppColors.primary.withValues(
                            alpha: 0.16,
                          ),
                          foregroundColor: AppColors.primary,
                          child: Icon(
                            auth.isGuest
                                ? Icons.bolt_rounded
                                : Icons.person_rounded,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                auth.user?['display_name']?.toString() ??
                                    'Learner',
                                style: GoogleFonts.inter(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w700,
                                  color: textPrimary,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                auth.isGuest
                                    ? 'Temporary guest'
                                    : auth.user?['email']?.toString() ??
                                          'Registered account',
                                overflow: TextOverflow.ellipsis,
                                style: GoogleFonts.inter(
                                  fontSize: 11,
                                  color: textSecondary,
                                ),
                              ),
                            ],
                          ),
                        ),
                        TextButton(
                          onPressed: _signingOut ? null : _signOut,
                          child: _signingOut
                              ? const SizedBox.square(
                                  dimension: 16,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : const Text('Sign out'),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
