// lib/features/shell/main_shell.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:speakflow/core/theme/local_fonts.dart';
import '../../core/theme/app_colors.dart';
import '../../app/providers.dart';
import 'settings/settings_drawer.dart';

class MainShell extends ConsumerStatefulWidget {
  final String location;
  final Widget child;
  const MainShell({super.key, required this.location, required this.child});

  @override
  ConsumerState<MainShell> createState() => _MainShellState();
}

class _MainShellState extends ConsumerState<MainShell> {
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();

  static const _tabs = ['/home', '/practice', '/chat', '/news'];

  int get _selectedIndex {
    final index = _tabs.indexWhere(
      (tab) => widget.location == tab || widget.location.startsWith('$tab/'),
    );
    return index < 0 ? 0 : index;
  }

  void _onTabTapped(int index) {
    context.go(_tabs[index]);
  }

  void _openSettings() {
    _scaffoldKey.currentState?.openEndDrawer();
  }

  @override
  Widget build(BuildContext context) {
    final appState = ref.watch(appStateProvider);
    return Scaffold(
      key: _scaffoldKey,
      backgroundColor: AppColors.background,
      endDrawer: SettingsDrawer(appState: appState),
      endDrawerEnableOpenDragGesture: false,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            SizedBox(
              height: 48,
              child: Align(
                alignment: Alignment.centerRight,
                child: IconButton(
                  tooltip: 'Settings',
                  onPressed: _openSettings,
                  icon: const Icon(
                    Icons.tune_rounded,
                    color: AppColors.textSecondary,
                  ),
                ),
              ),
            ),
            Expanded(
              child: MediaQuery.removePadding(
                context: context,
                removeTop: true,
                child: KeyedSubtree(
                  key: ValueKey(appState.planRefreshToken),
                  child: widget.child,
                ),
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: _buildBottomNav(),
    );
  }

  Widget _buildBottomNav() {
    return Container(
      decoration: const BoxDecoration(
        color: AppColors.navBackground,
        border: Border(top: BorderSide(color: AppColors.border, width: 0.5)),
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 64,
          child: LayoutBuilder(
            builder: (context, constraints) {
              final availableWidth = constraints.maxWidth - 8;
              final candidateWidth = availableWidth / _tabs.length;
              final itemWidth = candidateWidth < 88 ? candidateWidth : 88.0;
              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 4),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _NavItem(
                      width: itemWidth,
                      icon: Icons.home_rounded,
                      label: 'Home',
                      isSelected: _selectedIndex == 0,
                      onTap: () => _onTabTapped(0),
                    ),
                    _NavItem(
                      width: itemWidth,
                      icon: Icons.mic_rounded,
                      label: 'Practice',
                      isSelected: _selectedIndex == 1,
                      onTap: () => _onTabTapped(1),
                    ),
                    _NavItem(
                      width: itemWidth,
                      icon: Icons.chat_bubble_rounded,
                      label: 'Chat',
                      isSelected: _selectedIndex == 2,
                      onTap: () => _onTabTapped(2),
                    ),
                    _NavItem(
                      width: itemWidth,
                      icon: Icons.newspaper_rounded,
                      label: 'News',
                      isSelected: _selectedIndex == 3,
                      onTap: () => _onTabTapped(3),
                    ),
                  ],
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  final double width;
  final IconData icon;
  final String label;
  final bool isSelected;
  final VoidCallback onTap;
  const _NavItem({
    required this.width,
    required this.icon,
    required this.label,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final activeColor = AppColors.primary;
    const inactiveColor = AppColors.textSecondary;

    return SizedBox(
      width: width,
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
                      ? AppColors.primary.withValues(alpha: 0.15)
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
