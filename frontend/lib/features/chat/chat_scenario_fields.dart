part of 'chat_tab.dart';

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
  int weight;

  _EditableRubric({
    required this.id,
    required String label,
    required String description,
    required this.weight,
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
        DropdownMenuItem(value: 4, child: Text('4×')),
        DropdownMenuItem(value: 5, child: Text('5×')),
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
