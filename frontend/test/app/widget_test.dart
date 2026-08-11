import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:speakflow/app/providers.dart';

void main() {
  testWidgets('application state is observable through Riverpod', (
    tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          home: Consumer(
            builder: (context, ref, child) {
              final state = ref.watch(appStateProvider);
              return TextButton(
                onPressed: () => state.setCefrLevel('A2'),
                child: Text(state.cefrLevel),
              );
            },
          ),
        ),
      ),
    );

    expect(find.text('B1'), findsOneWidget);
    await tester.tap(find.byType(TextButton));
    await tester.pump();
    expect(find.text('A2'), findsOneWidget);
  });
}
