import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import 'plp_repository.dart';

class PlpOnboardingScreen extends StatefulWidget {
  final PlpRepository repository;
  final ValueChanged<String>? onGenerationStarted;
  final bool allowBack;

  const PlpOnboardingScreen({
    super.key,
    required this.repository,
    this.onGenerationStarted,
    this.allowBack = true,
  });

  @override
  State<PlpOnboardingScreen> createState() => _PlpOnboardingScreenState();
}

class _PlpOnboardingScreenState extends State<PlpOnboardingScreen> {
  String _level = 'B1';
  String _nativeLanguage = 'Arabic';
  final Set<String> _goals = {'Speak confidently'};
  final Set<String> _interests = {'Technology'};
  bool _submitting = false;
  String? _error;

  static const _goalOptions = [
    'Speak confidently',
    'Travel independently',
    'Communicate at work',
    'Study in English',
    'Prepare for exams',
  ];
  static const _interestOptions = [
    'Technology',
    'Travel',
    'Business',
    'Education',
    'Culture',
    'Science',
    'Sports',
    'Daily life',
    'Entertainment',
    'Music',
    'History',
  ];
  static const _nativeLanguageOptions = [
    'Arabic',
    'Kurdish',
    'Turkish',
    'French',
    'Spanish',
  ];

  Future<void> _submit() async {
    if (_goals.isEmpty || _interests.isEmpty) {
      setState(() => _error = 'Choose at least one goal and one interest.');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.repository.saveProfile({
        'cefr_level': _level,
        'native_language': _nativeLanguage,
        'learning_goals': _goals.toList(),
        'interests': _interests.toList(),
      });
      final jobId = await widget.repository.generatePlan();
      if (!mounted) return;
      final callback = widget.onGenerationStarted;
      if (callback != null) {
        callback(jobId);
      } else {
        Navigator.pop(context, jobId);
      }
    } catch (error) {
      if (mounted) setState(() => _error = '$error');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        automaticallyImplyLeading: widget.allowBack,
        title: const Text('Build your learning path'),
        backgroundColor: AppColors.surface,
        foregroundColor: AppColors.textPrimary,
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
        children: [
          const Text(
            'A useful plan in four quick choices',
            style: TextStyle(fontSize: 26, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 8),
          const Text(
            'Choose your level, native language, goals, and interests. The app '
            'handles the schedule and pronunciation focus for you.',
            style: TextStyle(
              fontSize: 16,
              height: 1.4,
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 24),
          _title('Current CEFR level'),
          DropdownButtonFormField<String>(
            initialValue: _level,
            items: ['A1', 'A2', 'B1', 'B2']
                .map(
                  (value) => DropdownMenuItem(value: value, child: Text(value)),
                )
                .toList(),
            onChanged: (value) => setState(() => _level = value!),
          ),
          const SizedBox(height: 24),
          _title('Native language'),
          DropdownButtonFormField<String>(
            initialValue: _nativeLanguage,
            decoration: const InputDecoration(
              helperText: 'Used for helpful hints and pronunciation focus.',
            ),
            items: _nativeLanguageOptions
                .map(
                  (value) => DropdownMenuItem(value: value, child: Text(value)),
                )
                .toList(),
            onChanged: (value) => setState(() => _nativeLanguage = value!),
          ),
          const SizedBox(height: 24),
          _title('Main goals (choose up to 2)'),
          _chips(_goalOptions, _goals, maximum: 2),
          const SizedBox(height: 24),
          _title('Topics you enjoy (choose up to 3)'),
          _chips(_interestOptions, _interests, maximum: 3),
          const SizedBox(height: 24),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.surfaceElevated,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: AppColors.primary.withValues(alpha: 0.3),
              ),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.calendar_month, color: AppColors.primary),
                const SizedBox(width: 12),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Simple fixed rhythm',
                        style: TextStyle(fontWeight: FontWeight.w900),
                      ),
                      SizedBox(height: 4),
                      Text(
                        '5 days per week • about 20 minutes per day\n'
                        'Four skill days and one cumulative checkpoint.',
                        style: TextStyle(
                          height: 1.4,
                          color: AppColors.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 20),
            Text(_error!, style: const TextStyle(color: AppColors.error)),
          ],
          const SizedBox(height: 26),
          FilledButton.icon(
            onPressed: _submitting ? null : _submit,
            icon: _submitting
                ? const SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.auto_awesome),
            label: Text(_submitting ? 'STARTING…' : 'GENERATE MY PLAN'),
            style: FilledButton.styleFrom(
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              minimumSize: const Size.fromHeight(54),
            ),
          ),
        ],
      ),
    );
  }

  Widget _title(String value) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Text(
      value,
      style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
    ),
  );

  Widget _chips(
    List<String> options,
    Set<String> selected, {
    required int maximum,
  }) => Wrap(
    spacing: 8,
    runSpacing: 6,
    children: options.map((value) {
      final active = selected.contains(value);
      return FilterChip(
        selected: active,
        label: Text(value),
        selectedColor: AppColors.primary.withValues(alpha: 0.22),
        backgroundColor: AppColors.surfaceElevated,
        side: BorderSide(
          color: active ? AppColors.primary : AppColors.borderLight,
        ),
        checkmarkColor: AppColors.primaryLight,
        onSelected: (choose) => setState(() {
          if (choose) {
            if (selected.length < maximum) selected.add(value);
          } else if (selected.length > 1) {
            selected.remove(value);
          }
        }),
      );
    }).toList(),
  );
}
