part of 'chat_screen.dart';

extension _ChatInputWidgets on _ChatScreenState {
  Widget _messageList() {
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 20),
      itemCount: _messages.length + (_waiting ? 1 : 0),
      itemBuilder: (context, index) {
        if (index == _messages.length) {
          return const RoleplayThinkingBubble();
        }
        final message = _messages[index];
        return message.isUser
            ? RoleplayUserMessageBubble(
                text: message.text,
                correctedText: message.correctedText,
                grammarFeedback: message.grammarFeedback,
                wordConfidence: message.wordConfidence,
                hasReplay: message.localAudioPath != null,
                onReplay: () => _play(message),
                transcriptKey: const ValueKey('roleplay-confidence-transcript'),
              )
            : RoleplayPartnerMessageBubble(
                text: message.text,
                hasAudio: message.audio != null,
                onPlay: () => _play(message),
              );
      },
    );
  }

  Widget _inputBar() {
    final disabled = !_socketReady || _waiting || _ending || _starting;
    return Container(
      color: _surface,
      padding: EdgeInsets.fromLTRB(
        12,
        10,
        12,
        MediaQuery.paddingOf(context).bottom + 10,
      ),
      child: Row(
        children: [
          RoleplayRoundAction(
            icon: Icons.translate_rounded,
            tooltip: 'Say it in English',
            onTap: disabled ? null : _openHelp,
          ),
          const SizedBox(width: 9),
          Expanded(
            child: _recording
                ? RoleplayRecordingState(animation: _recordingAnimation)
                : TextField(
                    controller: _textController,
                    enabled: !disabled,
                    onSubmitted: (_) => _sendText(),
                    style: GoogleFonts.inter(color: _text),
                    decoration: InputDecoration(
                      hintText: !_socketReady
                          ? 'Connecting…'
                          : _waiting
                          ? 'Waiting for a reply…'
                          : 'Your response…',
                      hintStyle: GoogleFonts.inter(color: _muted, fontSize: 13),
                      filled: true,
                      fillColor: _card,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(15),
                        borderSide: BorderSide.none,
                      ),
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 15,
                        vertical: 12,
                      ),
                      suffixIcon: IconButton(
                        onPressed: _canSubmit ? _sendText : null,
                        icon: const Icon(Icons.send_rounded),
                        color: _primary,
                      ),
                    ),
                  ),
          ),
          const SizedBox(width: 9),
          RoleplayRoundAction(
            icon: _recording ? Icons.stop_rounded : Icons.mic_rounded,
            tooltip: _recording ? 'Stop recording' : 'Speak',
            active: _recording,
            onTap: (_socketReady && !_waiting && !_ending)
                ? _toggleRecording
                : null,
          ),
        ],
      ),
    );
  }
}
