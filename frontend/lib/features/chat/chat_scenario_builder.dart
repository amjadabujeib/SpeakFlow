part of 'chat_tab.dart';

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
