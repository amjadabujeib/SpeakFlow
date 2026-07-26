import 'dart:async';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:just_talk/core/theme/local_fonts.dart';

import '../../core/services/api_service.dart';
import '../../core/theme/app_colors.dart';

typedef WordLookup = Future<Map<String, dynamic>> Function(String word);

class DictionaryScreen extends StatefulWidget {
  final WordLookup? lookup;

  const DictionaryScreen({super.key, this.lookup});

  @override
  State<DictionaryScreen> createState() => _DictionaryScreenState();
}

class _DictionaryScreenState extends State<DictionaryScreen> {
  final _controller = TextEditingController();
  final _audioPlayer = AudioPlayer();
  StreamSubscription<void>? _playerCompleteSubscription;
  Map<String, dynamic>? _entry;
  String? _error;
  bool _loading = false;
  bool _playing = false;

  @override
  void initState() {
    super.initState();
    _playerCompleteSubscription = _audioPlayer.onPlayerComplete.listen((_) {
      if (mounted) setState(() => _playing = false);
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _playerCompleteSubscription?.cancel();
    _audioPlayer.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    final word = _controller.text.trim();
    if (word.isEmpty) {
      setState(() => _error = 'Enter an English word.');
      return;
    }
    if (!RegExp(r"^[A-Za-z]+(?:['’-][A-Za-z]+)*$").hasMatch(word)) {
      setState(() => _error = 'Enter one English word.');
      return;
    }

    FocusScope.of(context).unfocus();
    setState(() {
      _loading = true;
      _entry = null;
      _error = null;
    });
    final result = await (widget.lookup ?? ApiService.lookupWord)(word);
    if (!mounted) return;
    setState(() {
      _loading = false;
      if (result['error'] != null) {
        _error = result['error'].toString();
      } else {
        _entry = {...result, 'word': word};
      }
    });
  }

  Future<void> _listen() async {
    final word = _entry?['word']?.toString().trim() ?? '';
    if (word.isEmpty) return;
    if (_playing) {
      await _audioPlayer.stop();
      if (mounted) setState(() => _playing = false);
      return;
    }
    setState(() {
      _playing = true;
      _error = null;
    });
    try {
      await _audioPlayer.play(UrlSource(ApiService.ttsUri(word).toString()));
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Could not play the pronunciation.');
      }
      if (mounted) setState(() => _playing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded),
          onPressed: () =>
              context.canPop() ? context.pop() : context.go('/home'),
        ),
        title: Text(
          'Dictionary',
          style: GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.w700),
        ),
        centerTitle: true,
        bottom: const PreferredSize(
          preferredSize: Size.fromHeight(1),
          child: Divider(height: 1, color: AppColors.border),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 40),
        children: [
          TextField(
            key: const ValueKey('dictionary-input'),
            controller: _controller,
            enabled: !_loading,
            autofocus: true,
            textInputAction: TextInputAction.search,
            inputFormatters: [LengthLimitingTextInputFormatter(60)],
            onSubmitted: (_) => _search(),
            decoration: InputDecoration(
              hintText: 'Enter an English word',
              prefixIcon: const Icon(Icons.search_rounded),
              suffixIcon: _controller.text.isEmpty
                  ? null
                  : IconButton(
                      tooltip: 'Clear',
                      onPressed: () {
                        _controller.clear();
                        setState(() {
                          _entry = null;
                          _error = null;
                        });
                      },
                      icon: const Icon(Icons.close_rounded),
                    ),
            ),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 12),
          FilledButton.icon(
            key: const ValueKey('dictionary-search'),
            onPressed: _loading ? null : _search,
            icon: _loading
                ? const SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.menu_book_rounded),
            label: Text(_loading ? 'Looking up…' : 'Look up word'),
          ),
          if (_error case final error?) ...[
            const SizedBox(height: 14),
            _MessageCard(message: error, isError: true),
          ],
          if (_entry case final entry?) ...[
            const SizedBox(height: 20),
            _DictionaryEntry(
              entry: entry,
              playing: _playing,
              onListen: _listen,
            ),
          ] else if (!_loading && _error == null) ...[
            const SizedBox(height: 64),
            const _EmptyDictionary(),
          ],
        ],
      ),
    );
  }
}

class _DictionaryEntry extends StatelessWidget {
  final Map<String, dynamic> entry;
  final bool playing;
  final VoidCallback onListen;

  const _DictionaryEntry({
    required this.entry,
    required this.playing,
    required this.onListen,
  });

  String _text(String key) => entry[key]?.toString().trim() ?? '';

  List<String> _list(String key) {
    final value = entry[key];
    if (value is! List) return const [];
    return value
        .map((item) => item.toString().trim())
        .where((item) => item.isNotEmpty)
        .toList(growable: false);
  }

  @override
  Widget build(BuildContext context) {
    final word = _text('word');
    final phonetic = _text('phonetic').isNotEmpty
        ? _text('phonetic')
        : _text('ipa');
    final partOfSpeech = _text('part_of_speech');
    final translation = _text('translation').isNotEmpty
        ? _text('translation')
        : _text('arabic_translation');
    final language = _text('translation_language');
    final definition = _text('definition');
    final examples = _list('examples').isNotEmpty
        ? _list('examples')
        : [_text('example_sentence')].where((item) => item.isNotEmpty).toList();

    return Container(
      key: ValueKey('dictionary-entry-$word'),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surfaceElevated,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.borderLight),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  word,
                  style: GoogleFonts.inter(
                    color: AppColors.textPrimary,
                    fontSize: 26,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              IconButton.filled(
                key: const ValueKey('dictionary-listen'),
                tooltip: playing ? 'Stop' : 'Listen with Kokoro',
                onPressed: onListen,
                icon: Icon(
                  playing ? Icons.stop_rounded : Icons.volume_up_rounded,
                ),
              ),
            ],
          ),
          if (phonetic.isNotEmpty || partOfSpeech.isNotEmpty) ...[
            const SizedBox(height: 4),
            Wrap(
              spacing: 10,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                if (phonetic.isNotEmpty)
                  Text(
                    phonetic,
                    style: GoogleFonts.inter(
                      color: AppColors.accentLight,
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                if (partOfSpeech.isNotEmpty) _Tag(text: partOfSpeech),
              ],
            ),
          ],
          if (translation.isNotEmpty) ...[
            const SizedBox(height: 22),
            _SectionLabel(language.isEmpty ? 'Translation' : language),
            const SizedBox(height: 7),
            Text(
              translation,
              style: GoogleFonts.inter(
                color: AppColors.textPrimary,
                fontSize: 20,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
          if (definition.isNotEmpty) ...[
            const SizedBox(height: 22),
            const _SectionLabel('Meaning'),
            const SizedBox(height: 7),
            Text(
              definition,
              style: GoogleFonts.inter(
                color: AppColors.textSecondary,
                fontSize: 14,
                height: 1.5,
              ),
            ),
          ],
          if (examples.isNotEmpty) ...[
            const SizedBox(height: 22),
            const _SectionLabel('Examples'),
            const SizedBox(height: 7),
            ...examples.indexed.map(
              (item) => Padding(
                padding: const EdgeInsets.only(bottom: 9),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${item.$1 + 1}.',
                      style: const TextStyle(color: AppColors.primaryLight),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        item.$2,
                        style: GoogleFonts.inter(
                          color: AppColors.textSecondary,
                          fontSize: 14,
                          height: 1.45,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  final String text;

  const _SectionLabel(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text.toUpperCase(),
      style: GoogleFonts.inter(
        color: AppColors.primaryLight,
        fontSize: 11,
        fontWeight: FontWeight.w700,
        letterSpacing: 0.8,
      ),
    );
  }
}

class _Tag extends StatelessWidget {
  final String text;

  const _Tag({required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        text,
        style: const TextStyle(
          color: AppColors.primaryLight,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _MessageCard extends StatelessWidget {
  final String message;
  final bool isError;

  const _MessageCard({required this.message, required this.isError});

  @override
  Widget build(BuildContext context) {
    final color = isError ? AppColors.error : AppColors.primary;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Text(
        message,
        style: const TextStyle(color: AppColors.textPrimary),
      ),
    );
  }
}

class _EmptyDictionary extends StatelessWidget {
  const _EmptyDictionary();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          width: 72,
          height: 72,
          decoration: BoxDecoration(
            color: AppColors.primary.withValues(alpha: 0.12),
            shape: BoxShape.circle,
          ),
          child: const Icon(
            Icons.menu_book_rounded,
            color: AppColors.primaryLight,
            size: 32,
          ),
        ),
        const SizedBox(height: 14),
        Text(
          'Find the right word',
          style: GoogleFonts.inter(
            color: AppColors.textPrimary,
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          'See its meaning, translation, and examples.',
          textAlign: TextAlign.center,
          style: GoogleFonts.inter(
            color: AppColors.textSecondary,
            fontSize: 13,
          ),
        ),
      ],
    );
  }
}
