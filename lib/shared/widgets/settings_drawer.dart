// lib/shared/widgets/settings_drawer.dart
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../core/theme/app_colors.dart';
import '../../core/providers/app_state.dart';
import '../../core/data/mock_data.dart';

class SettingsDrawer extends StatefulWidget {
  final AppState appState;

  const SettingsDrawer({super.key, required this.appState});

  @override
  State<SettingsDrawer> createState() => _SettingsDrawerState();
}

class _SettingsDrawerState extends State<SettingsDrawer> {
  late String _selectedMotherTongue;
  late String _selectedCefrLevel;
  late double _fontSize;

  @override
  void initState() {
    super.initState();
    _selectedMotherTongue = widget.appState.motherTongue;
    _selectedCefrLevel = widget.appState.cefrLevel;
    _fontSize = widget.appState.fontSize;
  }

  @override
  Widget build(BuildContext context) {
    final isDark = widget.appState.isDarkMode;
    final bg = isDark ? AppColors.surface : AppColors.lightSurface;
    final textPrimary = isDark ? AppColors.textPrimary : AppColors.lightTextPrimary;
    final textSecondary = isDark ? AppColors.textSecondary : AppColors.lightTextSecondary;
    final cardBg = isDark ? AppColors.surfaceElevated : AppColors.lightSurfaceElevated;
    final border = isDark ? AppColors.border : AppColors.lightBorder;

    return Drawer(
      width: MediaQuery.of(context).size.width * 0.85,
      backgroundColor: bg,
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
              child: Row(
                children: [
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      gradient: AppColors.primaryGradient,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Icon(Icons.tune_rounded, color: Colors.white, size: 18),
                  ),
                  const SizedBox(width: 12),
                  Text(
                    'Settings',
                    style: GoogleFonts.inter(
                      fontSize: 22,
                      fontWeight: FontWeight.w700,
                      color: textPrimary,
                    ),
                  ),
                  const Spacer(),
                  IconButton(
                    onPressed: () => Navigator.pop(context),
                    icon: Icon(Icons.close_rounded, color: textSecondary),
                  ),
                ],
              ),
            ),

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
                            const Icon(Icons.text_fields_rounded,
                                color: AppColors.primary, size: 20),
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
                            setState(() => _fontSize = v);
                            widget.appState.setFontSize(v);
                          },
                        ),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text('A', style: GoogleFonts.inter(fontSize: 11, color: textSecondary)),
                            Text('A', style: GoogleFonts.inter(fontSize: 14, color: textSecondary)),
                            Text('A', style: GoogleFonts.inter(fontSize: 17, color: textSecondary)),
                            Text('A', style: GoogleFonts.inter(fontSize: 20, color: textSecondary)),
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
                            const Icon(Icons.translate_rounded,
                                color: AppColors.accent, size: 20),
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
                          value: _selectedMotherTongue,
                          dropdownColor: cardBg,
                          style: GoogleFonts.inter(fontSize: 14, color: textPrimary),
                          decoration: InputDecoration(
                            contentPadding:
                                const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(10),
                              borderSide: BorderSide(color: border),
                            ),
                            enabledBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(10),
                              borderSide: BorderSide(color: border),
                            ),
                            filled: true,
                            fillColor: isDark ? AppColors.surface : AppColors.lightBackground,
                          ),
                          items: MockData.languages
                              .map((l) => DropdownMenuItem(value: l, child: Text(l)))
                              .toList(),
                          onChanged: (v) {
                            if (v != null) {
                              setState(() => _selectedMotherTongue = v);
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
                            const Icon(Icons.bar_chart_rounded,
                                color: AppColors.accent, size: 20),
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
                          children: MockData.cefrLevels.map((l) {
                            final isSelected = _selectedCefrLevel == l['level'];
                            return GestureDetector(
                              onTap: () {
                                setState(() => _selectedCefrLevel = l['level']!);
                                widget.appState.setCefrLevel(l['level']!);
                              },
                              child: AnimatedContainer(
                                duration: const Duration(milliseconds: 200),
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 16, vertical: 8),
                                decoration: BoxDecoration(
                                  gradient: isSelected ? AppColors.primaryGradient : null,
                                  color: isSelected ? null : (isDark ? AppColors.surface : AppColors.lightBackground),
                                  borderRadius: BorderRadius.circular(8),
                                  border: Border.all(
                                    color: isSelected ? Colors.transparent : border,
                                  ),
                                ),
                                child: Text(
                                  l['level']!,
                                  style: GoogleFonts.inter(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w600,
                                    color: isSelected ? Colors.white : textSecondary,
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
                            const Icon(Icons.interests_rounded,
                                color: AppColors.accent, size: 20),
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
                          children: MockData.interests.map((interest) {
                            final isSelected = widget.appState.interests.contains(interest);
                            return GestureDetector(
                              onTap: () {
                                final updated =
                                    List<String>.from(widget.appState.interests);
                                if (isSelected) {
                                  updated.remove(interest);
                                } else {
                                  updated.add(interest);
                                }
                                widget.appState.setInterests(updated);
                              },
                              child: AnimatedContainer(
                                duration: const Duration(milliseconds: 200),
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 12, vertical: 6),
                                decoration: BoxDecoration(
                                  gradient: isSelected ? AppColors.primaryGradient : null,
                                  color: isSelected ? null : (isDark ? AppColors.surface : AppColors.lightBackground),
                                  borderRadius: BorderRadius.circular(20),
                                  border: Border.all(
                                    color: isSelected ? Colors.transparent : border,
                                  ),
                                ),
                                child: Text(
                                  interest,
                                  style: GoogleFonts.inter(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w500,
                                    color: isSelected ? Colors.white : textSecondary,
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
                    onTap: () {
                      Navigator.pop(context);
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text(
                            'Regenerating your learning plan...',
                            style: GoogleFonts.inter(fontSize: 13),
                          ),
                          backgroundColor: AppColors.primary,
                          behavior: SnackBarBehavior.floating,
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(10)),
                        ),
                      );
                    },
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      decoration: BoxDecoration(
                        gradient: AppColors.primaryGradient,
                        borderRadius: BorderRadius.circular(12),
                        boxShadow: [
                          BoxShadow(
                            color: AppColors.primary.withOpacity(0.35),
                            blurRadius: 16,
                            offset: const Offset(0, 6),
                          ),
                        ],
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.auto_awesome_rounded,
                              color: Colors.white, size: 18),
                          const SizedBox(width: 8),
                          Text(
                            'Regenerate Learning Plan',
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

class _SectionLabel extends StatelessWidget {
  final String label;
  final Color textColor;
  const _SectionLabel({required this.label, required this.textColor});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Text(
        label.toUpperCase(),
        style: GoogleFonts.inter(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          color: textColor,
          letterSpacing: 1.2,
        ),
      ),
    );
  }
}

class _SettingsCard extends StatelessWidget {
  final Widget child;
  final Color bg;
  final Color border;
  const _SettingsCard({required this.child, required this.bg, required this.border});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: border),
      ),
      child: child,
    );
  }
}
