part of 'lesson_screens.dart';

extension _LessonContentWidgets on _InteractiveLessonScreenState {
  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 10, 18, 10),
      child: Row(
        children: [
          IconButton(
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.close, color: AppColors.textSecondary),
          ),
          const SizedBox(width: 4),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(10),
              child: LinearProgressIndicator(
                value: (_currentPage + 1) / _pageCount,
                minHeight: 12,
                color: _themeColor,
                backgroundColor: AppColors.surfaceElevated,
              ),
            ),
          ),
          const SizedBox(width: 14),
          Text(
            '$_currentPhase  •  ${_currentPage + 1}/$_pageCount',
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildIntroduction() {
    final goal =
        widget.lesson.canDoStatement ??
        (widget.lesson.objectives.isNotEmpty
            ? widget.lesson.objectives.first
            : 'Complete the lesson activities.');
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 48),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: _themeColor.withValues(alpha: 0.12),
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: _themeColor.withValues(alpha: 0.28),
                  ),
                ),
                child: Icon(
                  _lessonIcon(widget.lesson.type),
                  color: _themeColor,
                  size: 26,
                ),
              ),
              const SizedBox(width: 13),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _lessonTypeLabel(widget.lesson.type).toUpperCase(),
                      style: TextStyle(
                        color: _themeColor,
                        fontSize: 11,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 0.7,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      widget.lesson.title,
                      style: const TextStyle(
                        fontSize: 23,
                        height: 1.15,
                        fontWeight: FontWeight.w900,
                        color: AppColors.textPrimary,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          Text(
            widget.lesson.content!.intro,
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 15,
              height: 1.45,
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 18),
          _LessonGoalCard(color: _themeColor, goal: goal),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _MetaChip(
                icon: Icons.schedule,
                label: '${widget.lesson.estimatedMinutes} min',
              ),
              _MetaChip(
                icon: Icons.layers_outlined,
                label:
                    '${_activities.length} '
                    '${_activities.length == 1 ? 'step' : 'steps'}',
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(
                Icons.touch_app_outlined,
                size: 18,
                color: AppColors.textMuted,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  _questionCount > 0
                      ? 'Work through each step in order. Checks give you '
                            'feedback immediately.'
                      : 'Work through each short step in order, then finish '
                            'the lesson.',
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 13,
                    height: 1.4,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildActivity(PlpActivity activity) => switch (activity.type) {
    PlpActivityType.vocabularyCard => _buildVocabulary(activity),
    PlpActivityType.concept => _buildConcept(activity),
    PlpActivityType.pronunciationDrill => _buildPronunciation(activity),
    PlpActivityType.multipleChoice => _buildMultipleChoice(activity),
    PlpActivityType.fillBlank => _buildFillBlank(activity),
    PlpActivityType.readingComprehension => _buildReading(activity),
    PlpActivityType.listeningComprehension => _buildListening(activity),
    PlpActivityType.sentenceOrder => _buildSentenceOrder(activity),
    PlpActivityType.guidedSpeaking => _buildGuidedSpeaking(activity),
  };

  Widget _activityPage({
    required PlpActivity activity,
    required List<Widget> children,
  }) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(24, 18, 24, 48),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _ActivityPhaseBanner(
            key: ValueKey('activity-phase-${activity.id}'),
            phase: activity.phase,
          ),
          const SizedBox(height: 18),
          ...children,
        ],
      ),
    );
  }

  List<Widget> _nativeHintWidgets(JsonMap data) {
    final hint = data['native_hint'];
    if (hint is! String || hint.trim().isEmpty) return const [];
    return [
      const SizedBox(height: 18),
      _InfoPanel(
        color: AppColors.accentLight,
        icon: Icons.translate,
        title: 'Native-language hint',
        children: [hint.trim()],
      ),
    ];
  }

  Widget _buildVocabulary(PlpActivity activity) {
    final data = activity.data;
    final examples = (data['examples'] as List).cast<String>();
    final collocations = (data['collocations'] as List).cast<String>();
    return _activityPage(
      activity: activity,
      children: [
        const Text(
          'Vocabulary',
          style: TextStyle(
            color: AppColors.textSecondary,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 10),
        Card(
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(22),
            side: const BorderSide(color: AppColors.borderLight, width: 1.5),
          ),
          child: Padding(
            padding: const EdgeInsets.all(26),
            child: Column(
              children: [
                Text(
                  data['word'] as String,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: _themeColor,
                    fontSize: 34,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  '${data['part_of_speech']}  •  ${data['ipa']}',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 16,
                  ),
                ),
                const SizedBox(height: 22),
                const Divider(color: AppColors.border),
                const SizedBox(height: 18),
                Text(
                  data['definition'] as String,
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 18, height: 1.45),
                ),
              ],
            ),
          ),
        ),
        ..._nativeHintWidgets(data),
        const SizedBox(height: 22),
        const _SectionTitle('In context'),
        const SizedBox(height: 10),
        for (final example in examples)
          _ExampleCard(icon: Icons.format_quote, text: example),
        if (collocations.isNotEmpty) ...[
          const SizedBox(height: 12),
          const _SectionTitle('Natural combinations'),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: collocations
                .map(
                  (item) => Chip(
                    label: Text(item),
                    backgroundColor: _themeColor.withValues(alpha: 0.08),
                    side: BorderSide(
                      color: _themeColor.withValues(alpha: 0.18),
                    ),
                  ),
                )
                .toList(growable: false),
          ),
        ],
      ],
    );
  }

  Widget _buildConcept(PlpActivity activity) {
    final data = activity.data;
    final keyPoints = (data['key_points'] as List).cast<String>();
    final examples = (data['examples'] as List).cast<String>();
    return _activityPage(
      activity: activity,
      children: [
        Text(
          (data['title'] ?? 'Key idea') as String,
          style: const TextStyle(
            fontSize: 28,
            fontWeight: FontWeight.w900,
            color: AppColors.textPrimary,
          ),
        ),
        const SizedBox(height: 14),
        Text(
          data['explanation'] as String,
          style: const TextStyle(fontSize: 18, height: 1.5),
        ),
        ..._nativeHintWidgets(data),
        const SizedBox(height: 24),
        _InfoPanel(
          color: _themeColor,
          icon: Icons.rule,
          title: 'Key points',
          children: keyPoints,
        ),
        const SizedBox(height: 24),
        const _SectionTitle('Examples'),
        const SizedBox(height: 10),
        for (final example in examples)
          _ExampleCard(icon: Icons.chat_bubble_outline, text: example),
      ],
    );
  }
}
