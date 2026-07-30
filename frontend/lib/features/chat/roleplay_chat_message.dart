import 'dart:typed_data';

class RoleplayChatMessage {
  final String id;
  final bool isUser;
  final String text;
  final String? correctedText;
  final String? grammarFeedback;
  final List<Map<String, dynamic>> wordConfidence;
  final Uint8List? audio;
  final String? localAudioPath;

  const RoleplayChatMessage({
    required this.id,
    required this.isUser,
    required this.text,
    this.correctedText,
    this.grammarFeedback,
    this.wordConfidence = const [],
    this.audio,
    this.localAudioPath,
  });

  RoleplayChatMessage withAudio(Uint8List value) {
    return RoleplayChatMessage(
      id: id,
      isUser: isUser,
      text: text,
      correctedText: correctedText,
      grammarFeedback: grammarFeedback,
      wordConfidence: wordConfidence,
      audio: value,
      localAudioPath: localAudioPath,
    );
  }
}
