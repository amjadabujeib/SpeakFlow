// lib/features/news/news_tab.dart
import 'dart:async';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:speakflow/core/theme/local_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../shared/widgets/dictionary_popup.dart';
import '../../core/providers/app_state.dart';
import '../../app/providers.dart';

part 'news_models.dart';
part 'news_article_widgets.dart';
part 'news_player_widgets.dart';

// ---------------------------------------------------------------------------
// Data model
// ---------------------------------------------------------------------------

class NewsTab extends StatefulWidget {
  final NewsLoader? loader;

  const NewsTab({super.key, this.loader});

  @override
  State<NewsTab> createState() => _NewsTabState();
}

class _NewsTabState extends State<NewsTab> with TickerProviderStateMixin {
  final AppState _appState = AppState();
  final AudioPlayer _audioPlayer = AudioPlayer();
  StreamSubscription<Duration>? _positionSubscription;
  StreamSubscription<Duration>? _durationSubscription;
  StreamSubscription<void>? _completionSubscription;
  List<_Article> _articles = const [];
  String? _playingArticleId;
  String? _error;
  bool _isLoading = true;
  int _requestSerial = 0;
  String _loadedLevel = '';
  _NewsCategory _selectedCategory = _newsCategories.first;
  final Map<String, int> _categoryPages = {};

  // Mini-player slide controller
  late final AnimationController _playerSlideController;
  late final Animation<Offset> _playerSlideAnim;

  // Equalizer animation controller
  late final AnimationController _eqController;

  double _progress = 0;
  Duration _audioDuration = Duration.zero;
  String? _bufferingArticleId;

  _Article? get _playingArticle {
    if (_playingArticleId == null) return null;
    try {
      return _articles.firstWhere((a) => a.id == _playingArticleId);
    } catch (_) {
      return null;
    }
  }

  void _onStateChange() {
    if (!mounted) return;
    if (_loadedLevel != _appState.cefrLevel) {
      _loadNews(resetPage: true);
    } else {
      setState(() {});
    }
  }

  @override
  void initState() {
    super.initState();
    _appState.addListener(_onStateChange);

    _playerSlideController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 380),
    );
    _playerSlideAnim =
        Tween<Offset>(begin: const Offset(0, 1), end: Offset.zero).animate(
          CurvedAnimation(
            parent: _playerSlideController,
            curve: Curves.easeOutCubic,
            reverseCurve: Curves.easeInCubic,
          ),
        );

    _eqController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    );
    _positionSubscription = _audioPlayer.onPositionChanged.listen((position) {
      if (!mounted || _audioDuration.inMilliseconds <= 0) return;
      setState(() {
        _progress = (position.inMilliseconds / _audioDuration.inMilliseconds)
            .clamp(0.0, 1.0);
      });
    });
    _durationSubscription = _audioPlayer.onDurationChanged.listen((duration) {
      _audioDuration = duration;
    });
    _completionSubscription = _audioPlayer.onPlayerComplete.listen((_) {
      if (mounted) _stopPlayer();
    });

    _loadNews(resetPage: true);
  }

  @override
  void dispose() {
    _appState.removeListener(_onStateChange);
    _positionSubscription?.cancel();
    _durationSubscription?.cancel();
    _completionSubscription?.cancel();
    _audioPlayer.dispose();
    _playerSlideController.dispose();
    _eqController.dispose();
    super.dispose();
  }

  Future<void> _togglePlay(String articleId) async {
    if (_playingArticleId == articleId) {
      await _stopPlayer();
      return;
    }
    if (_bufferingArticleId == articleId) return; // already fetching
    final article = _articles.where((item) => item.id == articleId).firstOrNull;
    if (article == null) return;
    await _audioPlayer.stop();
    if (!mounted) return;
    // Reset playing state and show buffering spinner — do NOT animate player yet
    setState(() {
      _playingArticleId = null;
      _bufferingArticleId = articleId;
      _progress = 0;
      _audioDuration = Duration.zero;
    });
    _playerSlideController.reverse();
    _eqController.stop();
    try {
      final audio = await AppDependencies.instance.languageTools
          .synthesizeSpeech(article.body);
      if (!mounted || _bufferingArticleId != articleId) return;
      // Audio is ready — now transition to playing state
      setState(() {
        _playingArticleId = articleId;
        _bufferingArticleId = null;
      });
      _playerSlideController.forward();
      _eqController.repeat(reverse: true);
      await _audioPlayer.play(BytesSource(audio));
    } catch (error) {
      if (mounted && _bufferingArticleId == articleId) {
        setState(() => _bufferingArticleId = null);
      }
      await _stopPlayer();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not play this article: $error')),
        );
      }
    }
  }

  Future<void> _stopPlayer() async {
    await _audioPlayer.stop();
    if (!mounted) return;
    _playerSlideController.reverse();
    _eqController.stop();
    setState(() {
      _playingArticleId = null;
      _bufferingArticleId = null;
      _progress = 0;
      _audioDuration = Duration.zero;
    });
  }

  Future<void> _seekPlayer(double value) async {
    if (_audioDuration.inMilliseconds <= 0) return;
    final target = Duration(
      milliseconds: (_audioDuration.inMilliseconds * value).round(),
    );
    await _audioPlayer.seek(target);
  }

  Future<void> _loadNews({
    bool resetPage = false,
    bool nextPage = false,
  }) async {
    final request = ++_requestSerial;
    final category = _selectedCategory;
    final previousPage = _categoryPages[category.value] ?? 1;
    final page = resetPage ? 1 : (nextPage ? previousPage + 1 : previousPage);
    final level = _appState.cefrLevel;
    setState(() {
      _isLoading = true;
      _error = null;
      _playingArticleId = null;
      _bufferingArticleId = null;
    });
    _audioPlayer.stop();
    _eqController.stop();
    _playerSlideController.reverse();
    try {
      final payload =
          await (widget.loader ?? AppDependencies.instance.news.articles)(
            category: category.value,
            level: level,
            page: page,
          );
      if (!mounted || request != _requestSerial) return;
      final rawArticles = payload['articles'] as List<dynamic>? ?? const [];
      final articles = rawArticles
          .whereType<Map>()
          .map(
            (item) => _Article.fromJson(
              Map<String, dynamic>.from(item),
              category: category.label,
              level: level,
            ),
          )
          .where(
            (article) => article.title.isNotEmpty && article.body.isNotEmpty,
          )
          .toList(growable: false);
      if (articles.isEmpty && nextPage && _articles.isNotEmpty) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'No more ${category.label.toLowerCase()} stories right now.',
            ),
          ),
        );
        return;
      }
      setState(() {
        _articles = articles;
        _categoryPages[category.value] = page;
        _loadedLevel = level;
        _isLoading = false;
      });
    } catch (error) {
      if (!mounted || request != _requestSerial) return;
      if (_articles.isNotEmpty && nextPage) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not refresh the news: $error')),
        );
      } else {
        setState(() {
          _articles = const [];
          _error = '$error';
          _isLoading = false;
        });
      }
    }
  }

  void _selectCategory(_NewsCategory category) {
    if (category.value == _selectedCategory.value) return;
    setState(() => _selectedCategory = category);
    _loadNews(resetPage: true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _kBackground,
      body: Stack(
        children: [
          // ── Main scrollable content ──────────────────────────────────────
          CustomScrollView(
            physics: const BouncingScrollPhysics(),
            slivers: [
              // Filter chips
              SliverToBoxAdapter(
                child: SafeArea(
                  bottom: false,
                  child: Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: _buildFilterChips(),
                  ),
                ),
              ),

              const SliverToBoxAdapter(child: SizedBox(height: 8)),

              if (_isLoading)
                const SliverToBoxAdapter(
                  child: Padding(
                    padding: EdgeInsets.only(top: 80),
                    child: Center(child: CircularProgressIndicator()),
                  ),
                )
              else if (_error != null)
                SliverToBoxAdapter(child: _buildErrorState())
              else if (_articles.isEmpty)
                const SliverToBoxAdapter(
                  child: Padding(
                    padding: EdgeInsets.fromLTRB(28, 80, 28, 0),
                    child: Text(
                      'No stories are available in this category right now.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: _kTextSecondary, height: 1.4),
                    ),
                  ),
                ),

              SliverList(
                delegate: SliverChildBuilderDelegate(
                  (context, index) {
                    final article = _articles[index];
                    return _ArticleCard(
                          key: ValueKey(article.id),
                          article: article,
                          isPlaying: _playingArticleId == article.id,
                          isBuffering: _bufferingArticleId == article.id,
                          onPlayToggle: () => _togglePlay(article.id),
                        )
                        .animate()
                        .fadeIn(
                          delay: Duration(milliseconds: 60 * index),
                          duration: const Duration(milliseconds: 400),
                        )
                        .slideY(
                          begin: 0.12,
                          end: 0,
                          delay: Duration(milliseconds: 60 * index),
                          duration: const Duration(milliseconds: 400),
                          curve: Curves.easeOutCubic,
                        );
                  },
                  childCount: _isLoading || _error != null
                      ? 0
                      : _articles.length,
                ),
              ),

              // Bottom spacing so mini-player doesn't cover last card
              const SliverToBoxAdapter(child: SizedBox(height: 100)),
            ],
          ),

          // ── Mini Player ──────────────────────────────────────────────────
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: SlideTransition(
              position: _playerSlideAnim,
              child: _MiniPlayer(
                article: _playingArticle,
                progress: _progress,
                eqController: _eqController,
                onProgressChanged: _seekPlayer,
                onStop: () => _stopPlayer(),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── Filter chips ─────────────────────────────────────────────────────────

  Widget _buildFilterChips() {
    return Row(
      children: [
        Expanded(
          child: SizedBox(
            height: 44,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.only(left: 20),
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemCount: _newsCategories.length,
              itemBuilder: (context, i) {
                final category = _newsCategories[i];
                final selected = category.value == _selectedCategory.value;
                return GestureDetector(
                  onTap: () => _selectCategory(category),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 220),
                    curve: Curves.easeOut,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 18,
                      vertical: 8,
                    ),
                    decoration: BoxDecoration(
                      gradient: selected
                          ? const LinearGradient(
                              colors: [_kPrimary, _kAccent],
                              begin: Alignment.centerLeft,
                              end: Alignment.centerRight,
                            )
                          : null,
                      color: selected ? null : _kSurface,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: selected ? Colors.transparent : _kBorder,
                        width: 1,
                      ),
                      boxShadow: selected
                          ? [
                              BoxShadow(
                                color: _kPrimary.withValues(alpha: 0.35),
                                blurRadius: 10,
                                offset: const Offset(0, 3),
                              ),
                            ]
                          : null,
                    ),
                    child: Text(
                      category.label,
                      style: GoogleFonts.inter(
                        fontSize: 13,
                        fontWeight: selected
                            ? FontWeight.w600
                            : FontWeight.w500,
                        color: selected ? Colors.white : _kTextSecondary,
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ),
        const SizedBox(width: 8),
        IconButton(
          tooltip: 'More ${_selectedCategory.label.toLowerCase()} news',
          onPressed: _isLoading ? null : () => _loadNews(nextPage: true),
          icon: _isLoading
              ? const SizedBox(
                  width: 19,
                  height: 19,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.refresh_rounded),
          color: _kTextPrimary,
        ),
        const SizedBox(width: 8),
      ],
    );
  }

  Widget _buildErrorState() {
    final message = (_error ?? 'Could not load live news.').replaceFirst(
      'Bad state: ',
      '',
    );
    return Padding(
      padding: const EdgeInsets.fromLTRB(28, 64, 28, 0),
      child: Column(
        children: [
          const Icon(Icons.cloud_off_rounded, color: _kTextSecondary, size: 42),
          const SizedBox(height: 14),
          Text(
            message,
            textAlign: TextAlign.center,
            style: GoogleFonts.inter(color: _kTextSecondary, height: 1.4),
          ),
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: () => _loadNews(),
            icon: const Icon(Icons.refresh_rounded),
            label: const Text('Try again'),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Article Card
// ---------------------------------------------------------------------------
