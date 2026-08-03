// lib/core/theme/app_colors.dart
import 'package:flutter/material.dart';

class AppColors {
  // Primary palette — deep navy + electric blue/purple
  static const Color background = Color(0xFF090E1A);
  static const Color surface = Color(0xFF111827);
  static const Color surfaceElevated = Color(0xFF1A2235);
  static const Color surfaceCard = Color(0xFF1E2D45);

  static const Color primary = Color(0xFF4F7FFF);
  static const Color primaryLight = Color(0xFF7B9FFF);
  static const Color accent = Color(0xFF8B5CF6);
  static const Color accentLight = Color(0xFFA78BFA);

  static const Color gradientStart = Color(0xFF4F7FFF);
  static const Color gradientEnd = Color(0xFF8B5CF6);

  // Text
  static const Color textPrimary = Color(0xFFF1F5FF);
  static const Color textSecondary = Color(0xFF8896B0);
  static const Color textMuted = Color(0xFF4A5568);

  // Semantic
  static const Color success = Color(0xFF22C55E);
  static const Color warning = Color(0xFFF59E0B);
  static const Color error = Color(0xFFEF4444);
  // Border
  static const Color border = Color(0xFF1E2D45);
  static const Color borderLight = Color(0xFF2A3A55);

  // Bottom nav
  static const Color navBackground = Color(0xFF0D1526);

  // Gradients
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [gradientStart, gradientEnd],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
}
