import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:speakflow/core/theme/local_fonts.dart';

import '../../app/providers.dart';
import 'data/roleplay_api.dart';
import 'roleplay_models.dart';

part 'chat_tab_widgets.dart';
part 'chat_scenario_builder.dart';
part 'chat_scenario_editor.dart';
part 'chat_scenario_fields.dart';

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

  Future<void> _showEditScenario(RoleplayScenario current) async {
    final updated = await showDialog<RoleplayScenario>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _ScenarioBuilderDialog(
        api: ref.read(roleplayApiProvider),
        initialScenario: current,
      ),
    );
    if (!mounted || updated == null) return;
    setState(() {
      _scenarios = [
        for (final scenario in _scenarios)
          if (scenario.id == updated.id) updated else scenario,
      ];
      _expanded.add(updated.category);
    });
  }

  Future<void> _deleteScenario(RoleplayScenario scenario) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Delete custom scenario?'),
        content: Text(
          '“${scenario.title}” will be removed from your scenario list. '
          'Past and currently active sessions keep their saved scenario snapshot.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: const Color(0xFFDC2626),
            ),
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    try {
      await ref.read(roleplayApiProvider).deleteScenario(scenario.id);
      if (!mounted) return;
      setState(() {
        _scenarios = _scenarios
            .where((item) => item.id != scenario.id)
            .toList(growable: false);
      });
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Custom scenario deleted.')));
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('$error')));
    }
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
                        onEdit: _showEditScenario,
                        onDelete: _deleteScenario,
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
