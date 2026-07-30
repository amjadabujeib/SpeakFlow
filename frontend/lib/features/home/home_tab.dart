import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:speakflow/core/theme/local_fonts.dart';

import '../../core/theme/app_colors.dart';
import '../../core/providers/app_state.dart';
import '../../plp/learning_plan_screen.dart';
import '../../plp/plp_repository.dart';

class HomeTab extends StatelessWidget {
  final PlpRepository? repository;

  const HomeTab({super.key, this.repository});

  @override
  Widget build(BuildContext context) {
    return LearningPlanScreen(
      key: ValueKey(AppState().planRefreshToken),
      repository: repository,
      embedded: true,
      embeddedTop: Row(
        children: [
          _HomeTool(
            icon: Icons.spellcheck_rounded,
            label: 'Fix grammar',
            gradientColors: const [AppColors.primary, AppColors.accent],
            onTap: () => context.push('/grammar-check'),
          ),
          _HomeTool(
            icon: Icons.graphic_eq_rounded,
            label: 'Practice speech',
            gradientColors: const [AppColors.success, Color(0xFF06B6D4)],
            onTap: () => context.push('/pronunciation'),
          ),
          _HomeTool(
            icon: Icons.menu_book_rounded,
            label: 'Look up words',
            gradientColors: const [Color(0xFFF59E0B), Color(0xFFEC4899)],
            onTap: () => context.push('/dictionary'),
          ),
        ],
      ),
    );
  }
}

class _HomeTool extends StatelessWidget {
  final IconData icon;
  final String label;
  final List<Color> gradientColors;
  final VoidCallback onTap;

  const _HomeTool({
    required this.icon,
    required this.label,
    required this.gradientColors,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Semantics(
        button: true,
        label: label,
        child: InkWell(
          key: ValueKey('home-tool-$label'),
          onTap: onTap,
          borderRadius: BorderRadius.circular(18),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  key: ValueKey('home-action-icon-$label'),
                  width: 72,
                  height: 72,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(colors: gradientColors),
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: gradientColors.first.withValues(alpha: 0.22),
                        blurRadius: 16,
                        offset: const Offset(0, 7),
                      ),
                    ],
                  ),
                  child: Icon(icon, color: Colors.white, size: 31),
                ),
                const SizedBox(height: 9),
                Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.center,
                  style: GoogleFonts.inter(
                    color: AppColors.textPrimary,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
