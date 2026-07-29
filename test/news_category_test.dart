import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:speakflow/features/news/news_tab.dart';

void main() {
  testWidgets('news category selection and refresh request the selected feed', (
    tester,
  ) async {
    final requests = <String>[];

    Future<Map<String, dynamic>> loader({
      required String category,
      required String level,
      int page = 1,
    }) async {
      requests.add('$category:$page');
      return {
        'articles': [
          {
            'id': '$category-$page',
            'title': '$category page $page',
            'simplified_summary': 'A level-adjusted $category story.',
            'read_time_minutes': 1,
          },
        ],
      };
    }

    await tester.pumpWidget(MaterialApp(home: NewsTab(loader: loader)));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));

    await tester.scrollUntilVisible(
      find.text('Sports'),
      220,
      scrollable: find.byType(Scrollable).at(1),
    );
    await tester.tap(find.text('Sports'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));

    expect(requests, contains('sports:1'));
    expect(find.text('sports page 1'), findsOneWidget);

    await tester.tap(find.byTooltip('More sports news'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));

    expect(requests, contains('sports:2'));
    expect(find.text('sports page 2'), findsOneWidget);
  });
}
