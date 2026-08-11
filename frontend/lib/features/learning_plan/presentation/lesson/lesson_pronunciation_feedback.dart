import 'package:flutter/material.dart';

import '../../domain/plp_models.dart';

class LessonScoreBar extends StatelessWidget {
  final String label;
  final int score;

  const LessonScoreBar({super.key, required this.label, required this.score});

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [Text(label), Text('$score%')],
        ),
        const SizedBox(height: 5),
        LinearProgressIndicator(value: score.clamp(0, 100) / 100),
      ],
    ),
  );
}

class LessonPhoneChip extends StatelessWidget {
  final JsonMap data;

  const LessonPhoneChip({super.key, required this.data});

  @override
  Widget build(BuildContext context) {
    final status =
        data['display_status']?.toString() ?? data['status']?.toString();
    final color = switch (status) {
      'correct' => Colors.green,
      'warning' => Colors.orange,
      'omitted' => Colors.grey,
      _ => Colors.red,
    };
    final label = data['char']?.toString().replaceAll('_', '').trim();
    return Chip(
      backgroundColor: color.withValues(alpha: 0.12),
      side: BorderSide(color: color.withValues(alpha: 0.55)),
      label: Text(
        label?.isNotEmpty == true ? label! : '?',
        style: TextStyle(color: color.shade300, fontWeight: FontWeight.w800),
      ),
    );
  }
}

class LessonPracticeMessage extends StatelessWidget {
  final MaterialColor color;
  final IconData icon;
  final String text;

  const LessonPracticeMessage({
    super.key,
    required this.color,
    required this.icon,
    required this.text,
  });

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.1),
      border: Border.all(color: color.withValues(alpha: 0.38)),
      borderRadius: BorderRadius.circular(12),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: color.shade300),
        const SizedBox(width: 10),
        Expanded(child: Text(text, style: const TextStyle(height: 1.4))),
      ],
    ),
  );
}
