part of 'chat_tab.dart';

extension _ScenarioBuilderEditor on _ScenarioBuilderDialogState {
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
        _sectionTitle('Scenario details'),
        _DialogField(controller: _category, label: 'Category'),
        const SizedBox(height: 10),
        _DialogField(controller: _title, label: 'Scenario name'),
        const SizedBox(height: 10),
        _DialogField(
          controller: _description,
          label: 'What should happen?',
          lines: 3,
        ),
        const SizedBox(height: 18),
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
            onPressed: () => _mutate(
              () => _objectives.add(
                _EditableObjective(id: _newId('goal'), label: '', weight: 1),
              ),
            ),
            icon: const Icon(Icons.add_rounded),
            label: const Text('Add goal'),
          ),
        _errorView(),
      ],
    );
  }
}
