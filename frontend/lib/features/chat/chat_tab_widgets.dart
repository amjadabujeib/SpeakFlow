part of 'chat_tab.dart';

class _IntroCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            _primary.withValues(alpha: .18),
            _accent.withValues(alpha: .13),
          ],
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _primary.withValues(alpha: .28)),
      ),
      child: Row(
        children: [
          const Icon(Icons.forum_rounded, color: _primary, size: 28),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Practice a real conversation',
                  style: GoogleFonts.inter(
                    color: _text,
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Choose a situation, complete its goals, and get feedback based on what you actually said.',
                  style: GoogleFonts.inter(
                    color: _muted,
                    fontSize: 12,
                    height: 1.45,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _CategoryCard extends StatelessWidget {
  final String title;
  final List<RoleplayScenario> scenarios;
  final bool expanded;
  final int Function(RoleplayScenario) sessionCount;
  final VoidCallback onToggle;

  const _CategoryCard({
    required this.title,
    required this.scenarios,
    required this.expanded,
    required this.sessionCount,
    required this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _border),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          InkWell(
            onTap: onToggle,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 15),
              child: Row(
                children: [
                  Text(
                    scenarios.first.icon,
                    style: const TextStyle(fontSize: 21),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      title,
                      style: GoogleFonts.inter(
                        color: _text,
                        fontWeight: FontWeight.w700,
                        fontSize: 16,
                      ),
                    ),
                  ),
                  Text(
                    '${scenarios.length}',
                    style: GoogleFonts.inter(color: _muted, fontSize: 12),
                  ),
                  const SizedBox(width: 6),
                  AnimatedRotation(
                    turns: expanded ? .5 : 0,
                    duration: const Duration(milliseconds: 220),
                    child: const Icon(
                      Icons.keyboard_arrow_down_rounded,
                      color: _muted,
                    ),
                  ),
                ],
              ),
            ),
          ),
          AnimatedCrossFade(
            firstChild: const SizedBox(width: double.infinity),
            secondChild: Column(
              children: [
                const Divider(height: 1, color: _border),
                const SizedBox(height: 7),
                for (final scenario in scenarios)
                  _ScenarioCard(
                    scenario: scenario,
                    sessions: sessionCount(scenario),
                  ),
                const SizedBox(height: 7),
              ],
            ),
            crossFadeState: expanded
                ? CrossFadeState.showSecond
                : CrossFadeState.showFirst,
            duration: const Duration(milliseconds: 220),
          ),
        ],
      ),
    );
  }
}

class _ScenarioCard extends StatelessWidget {
  final RoleplayScenario scenario;
  final int sessions;

  const _ScenarioCard({required this.scenario, required this.sessions});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 11, vertical: 5),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: _cardInner,
        borderRadius: BorderRadius.circular(15),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  scenario.title,
                  style: GoogleFonts.inter(
                    color: _text,
                    fontWeight: FontWeight.w700,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  scenario.description,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    color: _muted,
                    fontSize: 12,
                    height: 1.4,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  sessions == 0
                      ? scenario.designedCefrLevel == null
                            ? '${scenario.objectives.length} conversation goals'
                            : '${scenario.designedCefrLevel} design · ${scenario.objectives.length} goals'
                      : '$sessions previous session${sessions == 1 ? '' : 's'}',
                  style: GoogleFonts.inter(
                    color: _primary,
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          IconButton.filled(
            tooltip: 'Start ${scenario.title}',
            style: IconButton.styleFrom(
              backgroundColor: _primary,
              foregroundColor: Colors.white,
            ),
            onPressed: () => context.push(
              '/chat/roleplay',
              extra: RoleplayLaunchArgs(scenario),
            ),
            icon: const Icon(Icons.arrow_forward_rounded),
          ),
        ],
      ),
    );
  }
}

class _HistorySheet extends StatelessWidget {
  final List<Map<String, dynamic>> history;

  const _HistorySheet({required this.history});

  @override
  Widget build(BuildContext context) {
    final completed = history
        .where((item) => item['status'] == 'complete')
        .toList(growable: false);
    return SafeArea(
      top: false,
      child: Column(
        children: [
          Container(
            width: 42,
            height: 4,
            margin: const EdgeInsets.only(top: 10, bottom: 18),
            decoration: BoxDecoration(
              color: _muted.withValues(alpha: .45),
              borderRadius: BorderRadius.circular(4),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Row(
              children: [
                Text(
                  'Roleplay history',
                  style: GoogleFonts.inter(
                    color: _text,
                    fontSize: 19,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: completed.isEmpty
                ? Center(
                    child: Text(
                      'Your completed sessions will appear here.',
                      style: GoogleFonts.inter(color: _muted),
                    ),
                  )
                : ListView.separated(
                    padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
                    itemCount: completed.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 9),
                    itemBuilder: (_, index) {
                      final item = completed[index];
                      final evaluation = Map<String, dynamic>.from(
                        item['evaluation'] as Map? ?? {},
                      );
                      final scores = Map<String, dynamic>.from(
                        evaluation['scores'] as Map? ?? {},
                      );
                      final task = scores['task_achievement'];
                      return ListTile(
                        onTap: () => Navigator.pop(
                          context,
                          RoleplayHistoryArgs(
                            clientSessionId:
                                item['client_session_id']?.toString() ?? '',
                            title: item['scenario']?.toString() ?? 'Roleplay',
                          ),
                        ),
                        tileColor: _card,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(15),
                        ),
                        title: Text(
                          item['scenario']?.toString() ?? 'Roleplay',
                          style: GoogleFonts.inter(
                            color: _text,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        subtitle: Text(
                          '${item['message_count'] ?? 0} turns · ${item['duration_seconds'] ?? 0}s · View transcript',
                          style: GoogleFonts.inter(color: _muted, fontSize: 12),
                        ),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Text(
                                  task is num ? '${task.round()}' : '—',
                                  style: GoogleFonts.inter(
                                    color: _primary,
                                    fontWeight: FontWeight.w800,
                                    fontSize: 18,
                                  ),
                                ),
                                Text(
                                  'task',
                                  style: GoogleFonts.inter(
                                    color: _muted,
                                    fontSize: 9,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(width: 8),
                            const Icon(
                              Icons.chevron_right_rounded,
                              color: _muted,
                            ),
                          ],
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

class _ScenarioBuilderDialog extends StatefulWidget {
  final RoleplayApi api;

  const _ScenarioBuilderDialog({required this.api});

  @override
  State<_ScenarioBuilderDialog> createState() => _ScenarioBuilderDialogState();
}
