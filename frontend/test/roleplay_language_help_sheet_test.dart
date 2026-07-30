import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:speakflow/features/chat/roleplay_language_help_sheet.dart';

void main() {
  testWidgets('language help can insert a configured sentence starter', (
    tester,
  ) async {
    String? selected;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: RoleplayLanguageHelpSheet(
            objectives: const [],
            phrases: const ['Could you help me with'],
            onSelect: (value) => selected = value,
          ),
        ),
      ),
    );

    expect(find.text('Say what you mean'), findsOneWidget);
    expect(find.text('Could you help me with'), findsOneWidget);

    await tester.tap(find.text('Could you help me with'));
    await tester.pump();

    expect(selected, 'Could you help me with ');
  });
}
