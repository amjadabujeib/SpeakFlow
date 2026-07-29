import 'package:flutter/material.dart';
import 'package:speakflow/core/theme/local_fonts.dart';

import 'roleplay_models.dart';

const _card = Color(0xFF1A2235);
const _cardInner = Color(0xFF1E2D45);
const _primary = Color(0xFF4F7FFF);
const _success = Color(0xFF22C55E);
const _error = Color(0xFFEF4444);
const _text = Color(0xFFF1F5FF);
const _muted = Color(0xFF8896B0);
const _border = Color(0xFF263550);

class RoleplayGoalProgressCard extends StatelessWidget {
  final RoleplayScenario scenario;
  final Map<String, dynamic> objectiveState;
  final int progress;
  final bool complete;

  const RoleplayGoalProgressCard({
    super.key,
    required this.scenario,
    required this.objectiveState,
    required this.progress,
    required this.complete,
  });

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      collapsedBackgroundColor: _card,
      backgroundColor: _card,
      iconColor: _primary,
      collapsedIconColor: _muted,
      tilePadding: const EdgeInsets.symmetric(horizontal: 16),
      childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
      title: Row(
        children: [
          Icon(
            complete ? Icons.verified_rounded : Icons.route_rounded,
            color: complete ? _success : _primary,
            size: 20,
          ),
          const SizedBox(width: 9),
          Expanded(
            child: Text(
              complete ? 'All goals complete' : 'Your goals',
              style: GoogleFonts.inter(
                color: _text,
                fontWeight: FontWeight.w700,
                fontSize: 13,
              ),
            ),
          ),
          Text(
            '$progress%',
            style: GoogleFonts.inter(
              color: complete ? _success : _primary,
              fontWeight: FontWeight.w800,
              fontSize: 13,
            ),
          ),
        ],
      ),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 8),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: progress / 100,
            minHeight: 5,
            color: complete ? _success : _primary,
            backgroundColor: _border,
          ),
        ),
      ),
      children: [
        for (final objective in scenario.objectives)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  _completed(objective.id)
                      ? Icons.check_circle_rounded
                      : Icons.radio_button_unchecked_rounded,
                  size: 17,
                  color: _completed(objective.id) ? _success : _muted,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    objective.label,
                    style: GoogleFonts.inter(
                      color: _completed(objective.id) ? _text : _muted,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }

  bool _completed(String id) {
    final value = objectiveState[id];
    return value is Map && value['completed'] == true;
  }
}

class RoleplayThinkingBubble extends StatelessWidget {
  const RoleplayThinkingBubble({super.key});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 14, right: 120),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        decoration: BoxDecoration(
          color: _card,
          borderRadius: BorderRadius.circular(15),
        ),
        child: Text(
          'Responding…',
          style: GoogleFonts.inter(color: _muted, fontSize: 12),
        ),
      ),
    );
  }
}

class RoleplayRoundAction extends StatelessWidget {
  final IconData icon;
  final String tooltip;
  final VoidCallback? onTap;
  final bool active;

  const RoleplayRoundAction({
    super.key,
    required this.icon,
    required this.tooltip,
    required this.onTap,
    this.active = false,
  });

  @override
  Widget build(BuildContext context) {
    return IconButton(
      tooltip: tooltip,
      onPressed: onTap,
      style: IconButton.styleFrom(
        backgroundColor: active ? _error : _cardInner,
        foregroundColor: onTap == null ? _muted : Colors.white,
        fixedSize: const Size(46, 46),
      ),
      icon: Icon(icon),
    );
  }
}

class RoleplayRecordingState extends StatelessWidget {
  final Animation<double> animation;

  const RoleplayRecordingState({super.key, required this.animation});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 48,
      padding: const EdgeInsets.symmetric(horizontal: 15),
      decoration: BoxDecoration(
        color: _error.withValues(alpha: .1),
        borderRadius: BorderRadius.circular(15),
        border: Border.all(color: _error.withValues(alpha: .35)),
      ),
      child: Row(
        children: [
          FadeTransition(
            opacity: animation,
            child: const Icon(Icons.circle, color: _error, size: 10),
          ),
          const SizedBox(width: 9),
          Text(
            'Recording your turn…',
            style: GoogleFonts.inter(
              color: _text,
              fontSize: 13,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class RoleplayStartError extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const RoleplayStartError({
    super.key,
    required this.message,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off_rounded, color: _muted, size: 42),
            const SizedBox(height: 14),
            Text(
              'Could not start the roleplay',
              style: GoogleFonts.inter(
                color: _text,
                fontSize: 17,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 7),
            Text(
              message,
              textAlign: TextAlign.center,
              style: GoogleFonts.inter(color: _muted, fontSize: 12),
            ),
            const SizedBox(height: 18),
            FilledButton(
              onPressed: onRetry,
              style: FilledButton.styleFrom(backgroundColor: _primary),
              child: const Text('Try again'),
            ),
          ],
        ),
      ),
    );
  }
}
