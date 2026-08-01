import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:speakflow/core/theme/local_fonts.dart';

import '../../app/providers.dart';
import 'data/roleplay_api.dart';
import 'roleplay_models.dart';

const _background = Color(0xFF090E1A);
const _surface = Color(0xFF111827);
const _card = Color(0xFF1A2235);
const _cardInner = Color(0xFF1E2D45);
const _primary = Color(0xFF4F7FFF);
const _accent = Color(0xFF8B5CF6);
const _warning = Color(0xFFF59E0B);
const _text = Color(0xFFF1F5FF);
const _muted = Color(0xFF8896B0);
const _border = Color(0xFF263550);

class ChatTab extends ConsumerStatefulWidget {
  const ChatTab({super.key});

  @override
  ConsumerState<ChatTab> createState() => _ChatTabState();
}

class _ChatTabState extends ConsumerState<ChatTab> {
  List<RoleplayScenario> _scenarios = const [];
  List<Map<String, dynamic>> _history = const [];
  final Set<String> _expanded = {'Travel'};
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final roleplay = ref.read(roleplayApiProvider);
      final results = await Future.wait([
        roleplay.scenarios(),
        roleplay.history(),
      ]);
      if (!mounted) return;
      setState(() {
        _scenarios = results[0]
            .map(RoleplayScenario.fromJson)
            .toList(growable: false);
        _history = results[1];
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = '$error';
        _loading = false;
      });
    }
  }

  Map<String, List<RoleplayScenario>> get _grouped {
    final result = <String, List<RoleplayScenario>>{};
    for (final scenario in _scenarios) {
      result.putIfAbsent(scenario.category, () => []).add(scenario);
    }
    return result;
  }

  int _sessionCount(RoleplayScenario scenario) {
    return _history.where((item) {
      if (item['status'] != 'complete') return false;
      final id = item['scenario_id']?.toString();
      if (id != null && id.isNotEmpty) return id == scenario.id;
      return item['scenario']?.toString().toLowerCase() ==
          scenario.title.toLowerCase();
    }).length;
  }

  Future<void> _showCreateScenario() async {
    final scenario = await showDialog<RoleplayScenario>(
      context: context,
      barrierDismissible: false,
      builder: (_) =>
          _ScenarioBuilderDialog(api: ref.read(roleplayApiProvider)),
    );
    if (!mounted || scenario == null) return;
    setState(() {
      _scenarios = [..._scenarios, scenario];
      _expanded.add(scenario.category);
    });
  }

  Future<void> _showHistory() async {
    final selected = await showModalBottomSheet<RoleplayHistoryArgs>(
      context: context,
      isScrollControlled: true,
      backgroundColor: _surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
      ),
      builder: (_) => FractionallySizedBox(
        heightFactor: .76,
        child: _HistorySheet(history: _history),
      ),
    );
    if (!mounted || selected == null) return;
    await context.push('/chat/history', extra: selected);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _background,
      body: SafeArea(
        child: _loading
            ? const Center(child: CircularProgressIndicator(color: _primary))
            : _error != null
            ? _ErrorState(message: _error!, onRetry: _load)
            : RefreshIndicator(
                color: _primary,
                onRefresh: _load,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(16, 18, 16, 112),
                  children: [
                    _IntroCard(),
                    const SizedBox(height: 16),
                    for (final entry in _grouped.entries)
                      _CategoryCard(
                        title: entry.key,
                        scenarios: entry.value,
                        expanded: _expanded.contains(entry.key),
                        sessionCount: _sessionCount,
                        onToggle: () => setState(() {
                          if (!_expanded.add(entry.key)) {
                            _expanded.remove(entry.key);
                          }
                        }),
                      ),
                  ],
                ),
              ),
      ),
      floatingActionButton: _loading || _error != null
          ? null
          : Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                FloatingActionButton.small(
                  heroTag: 'roleplay-history',
                  backgroundColor: _cardInner,
                  onPressed: _showHistory,
                  child: const Icon(Icons.history_rounded, color: _text),
                ),
                const SizedBox(height: 10),
                FloatingActionButton(
                  heroTag: 'roleplay-create',
                  onPressed: _showCreateScenario,
                  backgroundColor: _primary,
                  child: const Icon(Icons.add_rounded, color: Colors.white),
                ),
              ],
            ),
    );
  }
}

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

class _ScenarioBuilderDialogState extends State<_ScenarioBuilderDialog> {
  final _category = TextEditingController();
  final _title = TextEditingController();
  final _description = TextEditingController();
  final _aiRole = TextEditingController();
  final _learnerRole = TextEditingController();
  final _opening = TextEditingController();
  final List<_EditableObjective> _objectives = [];
  final List<TextEditingController> _phrases = [];
  final List<_EditableRubric> _rubric = [];

  bool _generating = false;
  bool _saving = false;
  String? _error;
  String? _level;
  String? _source;
  String _icon = '🎭';

  bool get _hasDraft => _level != null;

  @override
  void dispose() {
    _category.dispose();
    _title.dispose();
    _description.dispose();
    _aiRole.dispose();
    _learnerRole.dispose();
    _opening.dispose();
    _disposeDraftFields();
    super.dispose();
  }

  void _disposeDraftFields() {
    for (final item in _objectives) {
      item.dispose();
    }
    for (final item in _phrases) {
      item.dispose();
    }
    for (final item in _rubric) {
      item.dispose();
    }
    _objectives.clear();
    _phrases.clear();
    _rubric.clear();
  }

  Future<void> _generate() async {
    if (_category.text.trim().length < 2 ||
        _title.text.trim().length < 2 ||
        _description.text.trim().length < 8) {
      setState(
        () => _error = 'Add a category, name, and a clear situation first.',
      );
      return;
    }
    setState(() {
      _generating = true;
      _error = null;
    });
    try {
      final value = await widget.api.generateScenarioDraft(
        category: _category.text.trim(),
        title: _title.text.trim(),
        description: _description.text.trim(),
      );
      if (!mounted) return;
      _disposeDraftFields();
      _icon = value['icon']?.toString() ?? '🎭';
      _level = value['designed_cefr_level']?.toString() ?? 'B1';
      _source = value['draft_source']?.toString();
      _aiRole.text = value['ai_role']?.toString() ?? '';
      _learnerRole.text = value['learner_role']?.toString() ?? '';
      _opening.text = value['opening']?.toString() ?? '';
      final objectives = value['objectives'];
      if (objectives is List) {
        for (final raw in objectives.whereType<Map>()) {
          final item = Map<String, dynamic>.from(raw);
          _objectives.add(
            _EditableObjective(
              id: item['id']?.toString() ?? _newId('goal'),
              label: item['label']?.toString() ?? '',
              weight: (item['weight'] as num?)?.round().clamp(1, 3) ?? 1,
            ),
          );
        }
      }
      final phrases = value['target_language'];
      if (phrases is List) {
        _phrases.addAll(
          phrases.map((item) => TextEditingController(text: item.toString())),
        );
      }
      final rubric = value['evaluation_rubric'];
      if (rubric is List) {
        for (final raw in rubric.whereType<Map>()) {
          final item = Map<String, dynamic>.from(raw);
          _rubric.add(
            _EditableRubric(
              id: item['id']?.toString() ?? _newId('quality'),
              label: item['label']?.toString() ?? '',
              description: item['description']?.toString() ?? '',
            ),
          );
        }
      }
      setState(() => _generating = false);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _generating = false;
        _error = '$error';
      });
    }
  }

  Future<void> _save() async {
    final objectiveValues = _objectives
        .where((item) => item.label.text.trim().length >= 3)
        .toList();
    final phraseValues = _phrases
        .map((item) => item.text.trim())
        .where((item) => item.isNotEmpty)
        .toList();
    final rubricValues = _rubric
        .where(
          (item) =>
              item.label.text.trim().length >= 3 &&
              item.description.text.trim().length >= 8,
        )
        .toList();
    if (_aiRole.text.trim().length < 3 ||
        _learnerRole.text.trim().length < 3 ||
        _opening.text.trim().length < 3 ||
        objectiveValues.length < 3 ||
        phraseValues.length < 2 ||
        rubricValues.length < 2) {
      setState(
        () => _error =
            'Keep at least 3 goals, 2 useful phrases, and 2 complete evaluation criteria.',
      );
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final value = await widget.api.createScenario(
        category: _category.text.trim(),
        icon: _icon,
        title: _title.text.trim(),
        description: _description.text.trim(),
        aiRole: _aiRole.text.trim(),
        learnerRole: _learnerRole.text.trim(),
        opening: _opening.text.trim(),
        objectives: objectiveValues
            .map(
              (item) => {
                'id': item.id,
                'label': item.label.text.trim(),
                'weight': item.weight,
                'required': true,
              },
            )
            .toList(growable: false),
        targetLanguage: phraseValues,
        evaluationRubric: rubricValues
            .map(
              (item) => {
                'id': item.id,
                'label': item.label.text.trim(),
                'description': item.description.text.trim(),
                'weight': 1,
              },
            )
            .toList(growable: false),
        designedCefrLevel: _level!,
      );
      if (!mounted) return;
      Navigator.pop(context, RoleplayScenario.fromJson(value));
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = '$error';
      });
    }
  }

  String _newId(String prefix) =>
      '${prefix}_${DateTime.now().microsecondsSinceEpoch}_${_objectives.length + _rubric.length}';

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      insetPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 24),
      backgroundColor: _card,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
      title: Row(
        children: [
          Expanded(
            child: Text(
              _hasDraft ? 'Review your scenario' : 'Create a scenario',
              style: GoogleFonts.inter(
                color: _text,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          IconButton(
            onPressed: _saving ? null : () => Navigator.pop(context),
            icon: const Icon(Icons.close_rounded, color: _muted),
          ),
        ],
      ),
      content: SizedBox(
        width: 620,
        height: MediaQuery.sizeOf(context).height * .68,
        child: _hasDraft ? _draftEditor() : _briefForm(),
      ),
      actions: [
        if (_hasDraft)
          TextButton(
            onPressed: _saving
                ? null
                : () => setState(() {
                    _level = null;
                    _error = null;
                    _disposeDraftFields();
                  }),
            child: const Text('Edit brief'),
          ),
        FilledButton.icon(
          onPressed: _generating || _saving
              ? null
              : _hasDraft
              ? _save
              : _generate,
          style: FilledButton.styleFrom(backgroundColor: _primary),
          icon: _generating || _saving
              ? const SizedBox(
                  width: 17,
                  height: 17,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.white,
                  ),
                )
              : Icon(_hasDraft ? Icons.check_rounded : Icons.auto_awesome),
          label: Text(
            _generating
                ? 'Designing…'
                : _saving
                ? 'Saving…'
                : _hasDraft
                ? 'Save scenario'
                : 'Generate draft',
          ),
        ),
      ],
    );
  }

  Widget _briefForm() {
    return ListView(
      children: [
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: _primary.withValues(alpha: .09),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: _primary.withValues(alpha: .25)),
          ),
          child: Text(
            'Describe the situation. SpeakFlow will use your current CEFR level to draft the roles, goals, useful phrases, and evaluation criteria. You review everything before it is saved.',
            style: GoogleFonts.inter(color: _muted, fontSize: 12, height: 1.45),
          ),
        ),
        const SizedBox(height: 15),
        _DialogField(controller: _category, label: 'Category'),
        const SizedBox(height: 12),
        _DialogField(controller: _title, label: 'Scenario name'),
        const SizedBox(height: 12),
        _DialogField(
          controller: _description,
          label: 'What should happen?',
          lines: 4,
        ),
        _errorView(),
      ],
    );
  }

  Widget _draftEditor() {
    return ListView(
      children: [
        Row(
          children: [
            Text(_icon, style: const TextStyle(fontSize: 25)),
            const SizedBox(width: 9),
            _BuilderChip(label: 'Designed for $_level', color: _primary),
            const SizedBox(width: 7),
            if (_source == 'reviewable_fallback')
              const _BuilderChip(
                label: 'Fallback draft—review carefully',
                color: _warning,
              ),
          ],
        ),
        const SizedBox(height: 15),
        _sectionTitle('Roles and opening'),
        _DialogField(controller: _aiRole, label: 'AI partner role'),
        const SizedBox(height: 10),
        _DialogField(controller: _learnerRole, label: 'Learner role'),
        const SizedBox(height: 10),
        _DialogField(controller: _opening, label: 'Opening message', lines: 2),
        const SizedBox(height: 18),
        _sectionTitle('Conversation goals'),
        Text(
          'A goal is completed only when the learner’s own words provide evidence.',
          style: GoogleFonts.inter(color: _muted, fontSize: 10),
        ),
        const SizedBox(height: 8),
        for (var index = 0; index < _objectives.length; index++)
          _editableObjective(index),
        if (_objectives.length < 6)
          TextButton.icon(
            onPressed: () => setState(
              () => _objectives.add(
                _EditableObjective(id: _newId('goal'), label: '', weight: 1),
              ),
            ),
            icon: const Icon(Icons.add_rounded),
            label: const Text('Add goal'),
          ),
        const SizedBox(height: 15),
        _sectionTitle('Useful sentence starters'),
        for (var index = 0; index < _phrases.length; index++)
          _editablePhrase(index),
        if (_phrases.length < 10)
          TextButton.icon(
            onPressed: () =>
                setState(() => _phrases.add(TextEditingController())),
            icon: const Icon(Icons.add_rounded),
            label: const Text('Add phrase'),
          ),
        const SizedBox(height: 15),
        _sectionTitle('Scenario-specific evaluation'),
        Text(
          'These scores complement task, interaction, grammar, vocabulary, and spoken-delivery measures.',
          style: GoogleFonts.inter(color: _muted, fontSize: 10, height: 1.4),
        ),
        const SizedBox(height: 8),
        for (var index = 0; index < _rubric.length; index++)
          _editableRubric(index),
        if (_rubric.length < 4)
          TextButton.icon(
            onPressed: () => setState(
              () => _rubric.add(
                _EditableRubric(
                  id: _newId('quality'),
                  label: '',
                  description: '',
                ),
              ),
            ),
            icon: const Icon(Icons.add_rounded),
            label: const Text('Add evaluation criterion'),
          ),
        _errorView(),
      ],
    );
  }

  Widget _editableObjective(int index) {
    final item = _objectives[index];
    return Padding(
      padding: const EdgeInsets.only(bottom: 9),
      child: Row(
        children: [
          Expanded(
            child: _DialogField(
              controller: item.label,
              label: 'Goal ${index + 1}',
            ),
          ),
          const SizedBox(width: 7),
          _WeightMenu(
            value: item.weight,
            onChanged: (value) => setState(() => item.weight = value),
          ),
          IconButton(
            tooltip: 'Remove goal',
            onPressed: _objectives.length <= 3
                ? null
                : () => setState(() {
                    _objectives.removeAt(index).dispose();
                  }),
            icon: const Icon(Icons.close_rounded, color: _muted),
          ),
        ],
      ),
    );
  }

  Widget _editablePhrase(int index) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 9),
      child: Row(
        children: [
          Expanded(
            child: _DialogField(
              controller: _phrases[index],
              label: 'Starter ${index + 1}',
            ),
          ),
          IconButton(
            tooltip: 'Remove phrase',
            onPressed: _phrases.length <= 2
                ? null
                : () => setState(() {
                    _phrases.removeAt(index).dispose();
                  }),
            icon: const Icon(Icons.close_rounded, color: _muted),
          ),
        ],
      ),
    );
  }

  Widget _editableRubric(int index) {
    final item = _rubric[index];
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(11),
      decoration: BoxDecoration(
        color: _surface,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: _DialogField(
                  controller: item.label,
                  label: 'Criterion ${index + 1}',
                ),
              ),
              IconButton(
                tooltip: 'Remove criterion',
                onPressed: _rubric.length <= 2
                    ? null
                    : () => setState(() {
                        _rubric.removeAt(index).dispose();
                      }),
                icon: const Icon(Icons.close_rounded, color: _muted),
              ),
            ],
          ),
          const SizedBox(height: 9),
          _DialogField(
            controller: item.description,
            label: 'What good performance looks like',
            lines: 2,
          ),
        ],
      ),
    );
  }

  Widget _sectionTitle(String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        value,
        style: GoogleFonts.inter(
          color: _text,
          fontSize: 14,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }

  Widget _errorView() {
    if (_error == null) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Text(
        _error!,
        style: GoogleFonts.inter(color: const Color(0xFFF87171), fontSize: 11),
      ),
    );
  }
}

class _EditableObjective {
  final String id;
  final TextEditingController label;
  int weight;

  _EditableObjective({
    required this.id,
    required String label,
    required this.weight,
  }) : label = TextEditingController(text: label);

  void dispose() => label.dispose();
}

class _EditableRubric {
  final String id;
  final TextEditingController label;
  final TextEditingController description;

  _EditableRubric({
    required this.id,
    required String label,
    required String description,
  }) : label = TextEditingController(text: label),
       description = TextEditingController(text: description);

  void dispose() {
    label.dispose();
    description.dispose();
  }
}

class _WeightMenu extends StatelessWidget {
  final int value;
  final ValueChanged<int> onChanged;

  const _WeightMenu({required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return DropdownButton<int>(
      value: value,
      dropdownColor: _cardInner,
      underline: const SizedBox.shrink(),
      iconEnabledColor: _muted,
      style: GoogleFonts.inter(color: _text, fontSize: 11),
      items: const [
        DropdownMenuItem(value: 1, child: Text('1×')),
        DropdownMenuItem(value: 2, child: Text('2×')),
        DropdownMenuItem(value: 3, child: Text('3×')),
      ],
      onChanged: (value) {
        if (value != null) onChanged(value);
      },
    );
  }
}

class _BuilderChip extends StatelessWidget {
  final String label;
  final Color color;

  const _BuilderChip({required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Flexible(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
        decoration: BoxDecoration(
          color: color.withValues(alpha: .12),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          label,
          overflow: TextOverflow.ellipsis,
          style: GoogleFonts.inter(
            color: color,
            fontSize: 10,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}

class _DialogField extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final int lines;

  const _DialogField({
    required this.controller,
    required this.label,
    this.lines = 1,
  });

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      maxLines: lines,
      style: GoogleFonts.inter(color: _text),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: GoogleFonts.inter(color: _muted),
        filled: true,
        fillColor: _surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(13),
          borderSide: const BorderSide(color: _border),
        ),
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _ErrorState({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(28),
      children: [
        const SizedBox(height: 120),
        const Icon(Icons.cloud_off_rounded, color: _muted, size: 42),
        const SizedBox(height: 14),
        Text(
          'Could not load roleplays',
          textAlign: TextAlign.center,
          style: GoogleFonts.inter(
            color: _text,
            fontSize: 17,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          message,
          textAlign: TextAlign.center,
          style: GoogleFonts.inter(color: _muted, fontSize: 12),
        ),
        const SizedBox(height: 18),
        Center(
          child: FilledButton(
            onPressed: onRetry,
            style: FilledButton.styleFrom(backgroundColor: _primary),
            child: const Text('Try again'),
          ),
        ),
      ],
    );
  }
}
