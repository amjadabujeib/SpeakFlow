// lib/features/shell/main_shell.dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../core/theme/app_colors.dart';
import '../../core/providers/app_state.dart';
import '../../shared/widgets/settings_drawer.dart';

class MainShell extends StatefulWidget {
  final Widget child;
  const MainShell({super.key, required this.child});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  final AppState _appState = AppState();
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();

  int _selectedIndex = 0;

  @override
  void initState() {
    super.initState();
    _appState.addListener(_onStateChanged);
  }

  @override
  void dispose() {
    _appState.removeListener(_onStateChanged);
    _appState.dispose();
    super.dispose();
  }

  void _onStateChanged() {
    setState(() {});
  }

  static const _tabs = ['/home', '/practice', '/chat', '/news'];

  void _onTabTapped(int index) {
    setState(() => _selectedIndex = index);
    context.go(_tabs[index]);
  }

  void _openSettings() {
    _scaffoldKey.currentState?.openEndDrawer();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = _appState.isDarkMode;
    final bg = isDark ? AppColors.background : AppColors.lightBackground;
    final navBg = isDark ? AppColors.navBackground : AppColors.lightSurface;
    final textPrimary = isDark ? AppColors.textPrimary : AppColors.lightTextPrimary;
    final textSecondary = isDark ? AppColors.textSecondary : AppColors.lightTextSecondary;

    return AnimatedTheme(
      data: isDark
          ? ThemeData.dark().copyWith(
              scaffoldBackgroundColor: bg,
            )
          : ThemeData.light().copyWith(
              scaffoldBackgroundColor: bg,
            ),
      child: Scaffold(
        key: _scaffoldKey,
        backgroundColor: bg,
        endDrawer: SettingsDrawer(appState: _appState),
        endDrawerEnableOpenDragGesture: false,
        appBar: PreferredSize(
          preferredSize: const Size.fromHeight(60),
          child: _buildAppBar(textPrimary, textSecondary, isDark),
        ),
        body: MediaQuery(
          data: MediaQuery.of(context).copyWith(
            textScaler: TextScaler.linear(_appState.fontSize),
          ),
          child: widget.child,
        ),
        bottomNavigationBar: _buildBottomNav(navBg, isDark),
      ),
    );
  }

  Widget _buildAppBar(Color textPrimary, Color textSecondary, bool isDark) {
    final titles = ['JustTalk', 'Practice', 'Chat', 'News'];
    return Container(
      decoration: BoxDecoration(
        color: isDark ? AppColors.background : AppColors.lightBackground,
        border: Border(
          bottom: BorderSide(
            color: isDark ? AppColors.border : AppColors.lightBorder,
            width: 0.5,
          ),
        ),
      ),
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            children: [
              if (_selectedIndex == 0) ...[
                Container(
                  width: 30,
                  height: 30,
                  decoration: BoxDecoration(
                    gradient: AppColors.primaryGradient,
                    borderRadius: BorderRadius.circular(8),
                    boxShadow: [
                      BoxShadow(
                        color: AppColors.primary.withOpacity(0.35),
                        blurRadius: 8,
                        offset: const Offset(0, 3),
                      ),
                    ],
                  ),
                  child: const Icon(
                    Icons.record_voice_over_rounded,
                    color: Colors.white,
                    size: 16,
                  ),
                ),
                const SizedBox(width: 8),
              ],
              Text(
                titles[_selectedIndex],
                style: GoogleFonts.inter(
                  fontSize: 20,
                  fontWeight: FontWeight.w800,
                  color: textPrimary,
                  letterSpacing: -0.3,
                ),
              ),
              const Spacer(),
              IconButton(
                onPressed: _openSettings,
                icon: Icon(
                  Icons.tune_rounded,
                  color: textSecondary,
                  size: 22,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBottomNav(Color navBg, bool isDark) {
    return Container(
      decoration: BoxDecoration(
        color: navBg,
        border: Border(
          top: BorderSide(
            color: isDark ? AppColors.border : AppColors.lightBorder,
            width: 0.5,
          ),
        ),
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 64,
          child: Row(
            children: [
              _NavItem(
                icon: Icons.home_rounded,
                label: 'Home',
                isSelected: _selectedIndex == 0,
                onTap: () => _onTabTapped(0),
                isDark: isDark,
              ),
              _NavItem(
                icon: Icons.mic_rounded,
                label: 'Practice',
                isSelected: _selectedIndex == 1,
                onTap: () => _onTabTapped(1),
                isDark: isDark,
              ),
              _NavItem(
                icon: Icons.chat_bubble_rounded,
                label: 'Chat',
                isSelected: _selectedIndex == 2,
                onTap: () => _onTabTapped(2),
                isDark: isDark,
              ),
              _NavItem(
                icon: Icons.newspaper_rounded,
                label: 'News',
                isSelected: _selectedIndex == 3,
                onTap: () => _onTabTapped(3),
                isDark: isDark,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool isSelected;
  final VoidCallback onTap;
  final bool isDark;

  const _NavItem({
    required this.icon,
    required this.label,
    required this.isSelected,
    required this.onTap,
    required this.isDark,
  });

  @override
  Widget build(BuildContext context) {
    final activeColor = AppColors.primary;
    final inactiveColor = isDark ? AppColors.textSecondary : AppColors.lightTextSecondary;

    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                width: 40,
                height: 32,
                decoration: BoxDecoration(
                  color: isSelected
                      ? AppColors.primary.withOpacity(0.15)
                      : Colors.transparent,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Icon(
                  icon,
                  color: isSelected ? activeColor : inactiveColor,
                  size: 22,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                label,
                style: GoogleFonts.inter(
                  fontSize: 10,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                  color: isSelected ? activeColor : inactiveColor,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
