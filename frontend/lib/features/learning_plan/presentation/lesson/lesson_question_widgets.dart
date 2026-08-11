part of 'lesson_screens.dart';

extension _LessonQuestionWidgets on _InteractiveLessonScreenState {
  Widget _buildMultipleChoice(PlpActivity activity) {
    final data = activity.data;
    final options = (data['options'] as List).cast<Map<String, dynamic>>();
    final selected = _answers[activity.id];
    final checked = _checkedQuestionIds.contains(activity.id);
    final correctId =
        data['correct_option_id'] as String? ??
        _serverCorrectResponses[activity.id]?['selected_option_id'] as String?;
    return _activityPage(
      activity: activity,
      children: [
        const _QuestionLabel(hint: 'Choose one answer.'),
        const SizedBox(height: 16),
        Text(
          data['prompt'] as String,
          style: const TextStyle(
            fontSize: 23,
            height: 1.35,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 24),
        for (final option in options)
          _AnswerOption(
            label: option['text'] as String,
            selected: selected == option['id'],
            correct:
                checked &&
                ((correctId != null && option['id'] == correctId) ||
                    (correctId == null &&
                        selected == option['id'] &&
                        _correctQuestionIds.contains(activity.id))),
            incorrect:
                checked &&
                selected == option['id'] &&
                !_correctQuestionIds.contains(activity.id),
            enabled: !checked,
            themeColor: _themeColor,
            onTap: () =>
                _update(() => _answers[activity.id] = option['id'] as String),
          ),
        if (checked)
          _AnswerExplanation(
            isCorrect: _correctQuestionIds.contains(activity.id),
            text:
                _serverExplanations[activity.id] ??
                data['explanation'] as String,
          ),
      ],
    );
  }

  Widget _buildFillBlank(PlpActivity activity) {
    final data = activity.data;
    final checked = _checkedQuestionIds.contains(activity.id);
    final isCorrect = _correctQuestionIds.contains(activity.id);
    final controller = _textControllers.putIfAbsent(
      activity.id,
      () => TextEditingController(text: _answers[activity.id]),
    );
    final explanation =
        _serverExplanations[activity.id] ?? data['explanation'] as String;
    final expectedAnswer =
        _serverCorrectResponses[activity.id]?['text_answer'] ??
        (data['accepted_answers'] is List &&
                (data['accepted_answers'] as List).isNotEmpty
            ? (data['accepted_answers'] as List).first
            : null);
    return _activityPage(
      activity: activity,
      children: [
        const _QuestionLabel(hint: 'Complete the one missing answer.'),
        const SizedBox(height: 16),
        Text(
          key: const ValueKey('lesson-fill-blank-prompt'),
          data['prompt'] as String,
          style: const TextStyle(
            fontSize: 23,
            height: 1.4,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 26),
        TextField(
          key: const ValueKey('lesson-fill-blank-answer'),
          controller: controller,
          enabled: !checked,
          autocorrect: false,
          textInputAction: TextInputAction.done,
          scrollPadding: const EdgeInsets.only(bottom: 72),
          style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w700),
          decoration: InputDecoration(
            hintText: 'Type the missing word or phrase',
            filled: true,
            fillColor: checked
                ? (isCorrect
                      ? Colors.green.withValues(alpha: 0.12)
                      : Colors.red.withValues(alpha: 0.12))
                : AppColors.surfaceElevated,
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(16)),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: const BorderSide(
                color: AppColors.borderLight,
                width: 1.5,
              ),
            ),
            disabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: BorderSide(
                color: isCorrect ? Colors.green : Colors.red,
                width: 2,
              ),
            ),
            contentPadding: const EdgeInsets.all(19),
          ),
          onChanged: (value) => _update(() => _answers[activity.id] = value),
          onSubmitted: (_) => FocusScope.of(context).unfocus(),
        ),
        if (checked)
          _AnswerExplanation(
            isCorrect: isCorrect,
            text: !isCorrect && expectedAnswer != null
                ? 'Expected answer: $expectedAnswer\n\n$explanation'
                : explanation,
          ),
      ],
    );
  }

  Widget _buildReading(PlpActivity activity) {
    final data = activity.data;
    return _activityPage(
      activity: activity,
      children: [
        Text(
          data['title'] as String,
          style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 14),
        Container(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            color: AppColors.surfaceCard,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.borderLight),
          ),
          child: Text(
            data['passage'] as String,
            style: const TextStyle(fontSize: 17, height: 1.55),
          ),
        ),
        const SizedBox(height: 22),
        ..._nestedQuestionWidgets(activity, data['question'] as JsonMap),
      ],
    );
  }

  Widget _buildListening(PlpActivity activity) {
    final data = activity.data;
    return _activityPage(
      activity: activity,
      children: [
        Text(
          data['title'] as String,
          style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: data['transcript'] is String
              ? () async {
                  final audio = await ref
                      .read(languageToolsApiProvider)
                      .synthesizeSpeech(data['transcript'] as String);
                  await _audioPlayer.play(BytesSource(audio));
                }
              : null,
          icon: const Icon(Icons.play_arrow),
          label: const Text('PLAY LISTENING'),
        ),
        const SizedBox(height: 22),
        ..._nestedQuestionWidgets(activity, data['question'] as JsonMap),
      ],
    );
  }

  List<Widget> _nestedQuestionWidgets(PlpActivity activity, JsonMap question) {
    final options = (question['options'] as List).cast<JsonMap>();
    final selected = _answers[activity.id];
    final checked = _checkedQuestionIds.contains(activity.id);
    final isCorrect = _correctQuestionIds.contains(activity.id);
    final correctId =
        question['correct_option_id'] as String? ??
        _serverCorrectResponses[activity.id]?['selected_option_id'] as String?;
    return [
      const _QuestionLabel(hint: 'Choose one answer from the text.'),
      const SizedBox(height: 12),
      Text(
        question['prompt'] as String,
        style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
      ),
      const SizedBox(height: 18),
      for (final option in options)
        _AnswerOption(
          label: option['text'] as String,
          selected: selected == option['id'],
          correct: checked && correctId == option['id'],
          incorrect: checked && !isCorrect && selected == option['id'],
          enabled: !checked,
          themeColor: _themeColor,
          onTap: () =>
              _update(() => _answers[activity.id] = option['id'] as String),
        ),
      if (checked)
        _AnswerExplanation(
          isCorrect: isCorrect,
          text:
              _serverExplanations[activity.id] ??
              question['explanation'] as String,
        ),
    ];
  }

  Widget _buildSentenceOrder(PlpActivity activity) {
    final data = activity.data;
    final tokens = (data['tokens'] as List).cast<JsonMap>();
    final selected = _orderedAnswers.putIfAbsent(activity.id, () => []);
    final checked = _checkedQuestionIds.contains(activity.id);
    final serverCorrectOrder =
        _serverCorrectResponses[activity.id]?['ordered_token_ids'];
    String textFor(String id) =>
        tokens.firstWhere((item) => item['id'] == id)['text'] as String;
    return _activityPage(
      activity: activity,
      children: [
        const _QuestionLabel(hint: 'Use every chunk once.'),
        const SizedBox(height: 14),
        Text(
          data['prompt'] as String,
          style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 18),
        Container(
          constraints: const BoxConstraints(minHeight: 70),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppColors.surfaceCard,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: AppColors.borderLight),
          ),
          child: Wrap(
            spacing: 7,
            runSpacing: 7,
            children: selected
                .map((id) => Chip(label: Text(textFor(id))))
                .toList(),
          ),
        ),
        const SizedBox(height: 14),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: tokens
              .where((item) => !selected.contains(item['id']))
              .map(
                (item) => ActionChip(
                  label: Text(item['text'] as String),
                  onPressed: checked
                      ? null
                      : () => _update(() {
                          selected.add(item['id'] as String);
                          _answers[activity.id] = 'ordered';
                        }),
                ),
              )
              .toList(),
        ),
        if (!checked && selected.isNotEmpty)
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton(
              onPressed: () => _update(() {
                selected.clear();
                _answers.remove(activity.id);
              }),
              child: const Text('RESET ORDER'),
            ),
          ),
        if (checked)
          _AnswerExplanation(
            isCorrect: _correctQuestionIds.contains(activity.id),
            text:
                _serverExplanations[activity.id] ??
                data['explanation'] as String,
          ),
        if (checked && serverCorrectOrder is List<dynamic>)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: _InfoPanel(
              color: Colors.green,
              icon: Icons.check_circle_outline,
              title: 'Correct order',
              children: [
                serverCorrectOrder.map((id) => textFor(id as String)).join(' '),
              ],
            ),
          ),
      ],
    );
  }
}
