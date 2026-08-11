final _typedEnglishLetter = RegExp(r'[A-Za-z]');
final _typedArabicLetter = RegExp(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]');

const roleplayEnglishTurnMessage =
    'Please write your roleplay turn in English. Use Language Help to translate Arabic first.';

String? roleplayTypedTurnError(String value) {
  final text = value.trim();
  if (text.isEmpty) return null;
  if (_typedArabicLetter.hasMatch(text) ||
      !_typedEnglishLetter.hasMatch(text)) {
    return roleplayEnglishTurnMessage;
  }
  return null;
}
