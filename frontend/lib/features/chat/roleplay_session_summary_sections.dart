part of 'roleplay_session_summary_screen.dart';

class _EvidenceNotice extends StatelessWidget {
  final RoleplayFeedbackData feedback;

  const _EvidenceNotice({required this.feedback});

  @override
  Widget build(BuildContext context) {
    final ready = feedback.eligible;
    final color = ready ? _success : _warning;
    return Container(
      key: const ValueKey('roleplay-evidence-notice'),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withValues(alpha: .09),
        borderRadius: BorderRadius.circular(15),
        border: Border.all(color: color.withValues(alpha: .3)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            ready ? Icons.fact_check_outlined : Icons.info_outline_rounded,
            color: color,
            size: 20,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  ready ? 'Evidence quality' : 'More evidence needed',
                  style: GoogleFonts.inter(
                    color: _text,
                    fontWeight: FontWeight.w700,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  feedback.evidenceNote,
                  style: GoogleFonts.inter(
                    color: _muted,
                    fontSize: 11,
                    height: 1.4,
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

class _ScenarioEvidenceSection extends StatelessWidget {
  final List<Map<String, dynamic>> items;

  const _ScenarioEvidenceSection({required this.items});

  @override
  Widget build(BuildContext context) {
    return Column(
      key: const ValueKey('roleplay-scenario-evidence'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Scenario-specific feedback',
          style: GoogleFonts.inter(
            color: _text,
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 10),
        for (final item in items) ...[
          _ScenarioEvidenceCard(item: item),
          const SizedBox(height: 9),
        ],
      ],
    );
  }
}

class _ScenarioEvidenceCard extends StatelessWidget {
  final Map<String, dynamic> item;

  const _ScenarioEvidenceCard({required this.item});

  @override
  Widget build(BuildContext context) {
    final score = (item['score'] as num?)?.round().clamp(0, 100);
    final evidence = item['evidence'] is List
        ? (item['evidence'] as List)
              .whereType<Map>()
              .map((entry) => entry['reason']?.toString().trim() ?? '')
              .where((reason) => reason.isNotEmpty)
              .take(3)
              .toList(growable: false)
        : const <String>[];
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(15),
        border: Border.all(color: _border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  item['label']?.toString() ?? 'Scenario skill',
                  style: GoogleFonts.inter(
                    color: _text,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              if (score != null)
                Text(
                  '$score/100',
                  style: GoogleFonts.inter(
                    color: _primary,
                    fontWeight: FontWeight.w800,
                  ),
                ),
            ],
          ),
          if (evidence.isNotEmpty) ...[
            const SizedBox(height: 8),
            for (final reason in evidence)
              Padding(
                padding: const EdgeInsets.only(top: 3),
                child: Text(
                  '• $reason',
                  style: GoogleFonts.inter(
                    color: _muted,
                    fontSize: 11,
                    height: 1.35,
                  ),
                ),
              ),
          ],
        ],
      ),
    );
  }
}

class _CorrectionSection extends StatelessWidget {
  final List<RoleplayCorrection> corrections;

  const _CorrectionSection({required this.corrections});

  @override
  Widget build(BuildContext context) {
    return Column(
      key: const ValueKey('roleplay-correction-review'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Language refinements',
          style: GoogleFonts.inter(
            color: _text,
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 10),
        for (final correction in corrections) ...[
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: _card,
              borderRadius: BorderRadius.circular(15),
              border: Border.all(color: _border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  correction.original,
                  style: GoogleFonts.inter(
                    color: _muted,
                    decoration: TextDecoration.lineThrough,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  correction.corrected,
                  style: GoogleFonts.inter(
                    color: _text,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (correction.feedback?.trim().isNotEmpty == true) ...[
                  const SizedBox(height: 6),
                  Text(
                    correction.feedback!.trim(),
                    style: GoogleFonts.inter(
                      color: _muted,
                      fontSize: 11,
                      height: 1.35,
                    ),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 9),
        ],
      ],
    );
  }
}
