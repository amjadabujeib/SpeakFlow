import 'package:flutter_test/flutter_test.dart';
import 'package:speakflow/core/data/practice_word_store.dart';

void main() {
  test('a manual word can be promoted to a scored roleplay word', () {
    final manual = PracticeWord(
      word: 'comfortable',
      ipa: '',
      score: 0,
      source: 'Added by you',
      addedAt: DateTime.utc(2026, 1, 1),
      occurrences: 1,
      addedManually: true,
    );

    final reviewed = manual.copyWith(
      score: 58,
      source: 'Hotel Check-in roleplay',
      occurrences: 2,
      addedManually: false,
    );

    expect(reviewed.score, 58);
    expect(reviewed.source, 'Hotel Check-in roleplay');
    expect(reviewed.occurrences, 2);
    expect(reviewed.addedManually, isFalse);
  });

  test('practice words survive JSON persistence', () {
    final original = PracticeWord(
      word: 'particularly',
      ipa: '',
      score: 61,
      source: 'Coffee Shop roleplay',
      addedAt: DateTime.utc(2026, 7, 24),
      occurrences: 3,
      addedManually: false,
    );

    final restored = PracticeWord.fromJson(original.toJson());

    expect(restored.word, original.word);
    expect(restored.score, original.score);
    expect(restored.source, original.source);
    expect(restored.addedAt, original.addedAt);
    expect(restored.occurrences, original.occurrences);
    expect(restored.addedManually, isFalse);
  });

  test('mastered state survives persistence and can be reactivated', () {
    final masteredAt = DateTime.utc(2026, 7, 29, 12);
    final mastered = PracticeWord(
      word: 'tough',
      ipa: '/tʌf/',
      score: 72,
      source: 'Added by you',
      addedAt: DateTime.utc(2026, 7, 28),
      masteredAt: masteredAt,
      occurrences: 1,
      addedManually: true,
    );

    final restored = PracticeWord.fromJson(mastered.toJson());
    final reactivated = restored.copyWith(masteredAt: null);

    expect(restored.isMastered, isTrue);
    expect(restored.masteredAt, masteredAt);
    expect(reactivated.isMastered, isFalse);
  });
}
