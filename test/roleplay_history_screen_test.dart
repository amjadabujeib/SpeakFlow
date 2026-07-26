import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:just_talk/features/chat/roleplay_history_screen.dart';
import 'package:just_talk/features/chat/roleplay_models.dart';

void main() {
  testWidgets('saved conversation is displayed without live chat controls', (
    tester,
  ) async {
    Future<Map<String, dynamic>> loader(String _) async => {
      'read_only': true,
      'session': {
        'client_session_id': 'roleplay-history-1234',
        'scenario': 'Airport Check-in',
        'duration_seconds': 44,
      },
      'scenario': {
        'id': 'airport_check_in',
        'version': 1,
        'category': 'Travel',
        'icon': '✈️',
        'title': 'Airport Check-in',
        'description': 'Check in for a flight.',
        'ai_role': 'check-in agent',
        'learner_role': 'passenger',
        'opening': 'Where are you flying today?',
        'objectives': const [],
      },
      'turns': [
        {
          'turn_id': 'turn-history-0001',
          'sequence': 1,
          'input_mode': 'text',
          'user_text': 'I am flying to Paris.',
          'assistant_text': 'May I see your passport?',
          'created_at': '2026-07-26T07:00:00Z',
        },
      ],
    };

    await tester.pumpWidget(
      MaterialApp(
        home: RoleplayHistoryScreen(
          args: const RoleplayHistoryArgs(
            clientSessionId: 'roleplay-history-1234',
            title: 'Airport Check-in',
          ),
          loader: loader,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Saved conversation · Read-only'), findsOneWidget);
    expect(find.text('Where are you flying today?'), findsOneWidget);
    expect(find.text('I am flying to Paris.'), findsOneWidget);
    expect(find.text('May I see your passport?'), findsOneWidget);
    expect(find.byType(TextField), findsNothing);
    expect(find.byIcon(Icons.send_rounded), findsNothing);
    expect(find.byIcon(Icons.mic_rounded), findsNothing);
  });
}
