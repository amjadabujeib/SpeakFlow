// lib/shared/widgets/app_header.dart
import 'package:flutter/material.dart';
import 'package:just_talk/core/theme/local_fonts.dart';
import '../../core/theme/app_colors.dart';

class AppHeader extends StatelessWidget implements PreferredSizeWidget {
  final VoidCallback onSettingsTap;
  final String? title;
  final List<Widget>? actions;
  final Widget? leading;

  const AppHeader({
    super.key,
    required this.onSettingsTap,
    this.title,
    this.actions,
    this.leading,
  });

  @override
  Size get preferredSize => const Size.fromHeight(60);

  @override
  Widget build(BuildContext context) {
    return AppBar(
      backgroundColor: Colors.transparent,
      elevation: 0,
      leading: leading,
      centerTitle: true,
      title: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 30,
            height: 30,
            decoration: BoxDecoration(
              gradient: AppColors.primaryGradient,
              borderRadius: BorderRadius.circular(8),
              boxShadow: [
                BoxShadow(
                  color: AppColors.primary.withOpacity(0.4),
                  blurRadius: 10,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: const Icon(Icons.record_voice_over_rounded, color: Colors.white, size: 16),
          ),
          const SizedBox(width: 8),
          Text(
            title ?? 'JustTalk',
            style: GoogleFonts.inter(
              fontSize: 20,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
              letterSpacing: -0.3,
            ),
          ),
        ],
      ),
      actions: [
        if (actions != null) ...actions!,
        IconButton(
          onPressed: onSettingsTap,
          icon: const Icon(Icons.tune_rounded, color: AppColors.textSecondary),
        ),
      ],
    );
  }
}
