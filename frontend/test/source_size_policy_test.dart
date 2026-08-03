import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('hand-written Flutter source files stay at or below 500 lines', () {
    final violations = <String>[];
    for (final root in ['lib', 'test']) {
      for (final entity in Directory(root).listSync(recursive: true)) {
        if (entity is! File || !entity.path.endsWith('.dart')) continue;
        final lineCount = entity.readAsLinesSync().length;
        if (lineCount > 500) {
          violations.add('${entity.path}: $lineCount lines');
        }
      }
    }
    expect(
      violations,
      isEmpty,
      reason:
          'Split oversized files into cohesive library parts:\n'
          '${violations.join('\n')}',
    );
  });
}
