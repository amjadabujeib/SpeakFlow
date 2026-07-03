// lib/features/news/news_tab.dart
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../shared/widgets/dictionary_popup.dart';
import '../../core/providers/app_state.dart';

// ---------------------------------------------------------------------------
// Data model
// ---------------------------------------------------------------------------

class _Article {
  final String id;
  final String title;
  final String summary;
  final String category;
  final String level;
  final String readTime;
  final String body;

  const _Article({
    required this.id,
    required this.title,
    required this.summary,
    required this.category,
    required this.level,
    required this.readTime,
    required this.body,
  });
}

const List<_Article> _allArticles = [
  _Article(
    id: 'n1',
    title: 'Scientists Discover New Deep-Sea Species',
    summary:
        'Marine biologists found a remarkable new species 3km below the ocean.',
    category: 'Science',
    level: 'B1',
    readTime: '3 min',
    body:
        'A team of marine biologists working in the Pacific Ocean has made an exciting discovery. '
        'At a depth of nearly 3 kilometres, they encountered a creature unlike anything previously documented. '
        'The species, tentatively named Luminos profundus, emits a soft bioluminescent glow that pulses in a regular rhythm, '
        'possibly used for communication or predator deterrence. Scientists used a remotely operated vehicle (ROV) equipped '
        'with high-definition cameras to film the creature over a period of six hours. '
        'Further samples are being analysed at the Woods Hole Oceanographic Institution. '
        'Researchers believe the discovery underscores how much of the deep ocean remains unexplored and full of wonder.',
  ),
  _Article(
    id: 'n2',
    title: 'Global Travel Rebounds to Pre-Pandemic Levels',
    summary:
        'International tourism has fully recovered with record numbers this summer.',
    category: 'Travel',
    level: 'B2',
    readTime: '4 min',
    body:
        'The tourism industry has officially bounced back. According to the United Nations World Tourism Organization, '
        'international tourist arrivals surpassed pre-pandemic figures for the first time this summer, reaching 1.4 billion trips globally. '
        'Europe remains the most visited region, accounting for over half of all arrivals. '
        'Southeast Asia and the Middle East are among the fastest-growing destinations, driven by improved air connectivity and visa relaxation policies. '
        'Airlines have responded by reinstating long-haul routes that were suspended during COVID-19. '
        'However, the surge has reignited debates about overtourism, particularly in cities like Venice, Barcelona, and Kyoto, '
        'where local governments are introducing new visitor caps and tourist taxes.',
  ),
  _Article(
    id: 'n3',
    title: 'AI Tools Are Changing Language Learning',
    summary:
        'Artificial intelligence is revolutionizing education, making personalized learning accessible.',
    category: 'Technology',
    level: 'A2',
    readTime: '2 min',
    body:
        'Learning a new language is now easier than ever. New AI tools can listen to you speak and tell you what to improve. '
        'They can also create lessons just for you, based on what you already know. '
        'Many apps now use AI to make conversations feel real. You can practise talking with a computer that answers like a person. '
        'Teachers say these tools help students feel less nervous. Students can make mistakes and learn from them without feeling embarrassed. '
        'Experts believe AI will not replace human teachers but will help them. '
        'In the future, everyone might have a personal AI language coach in their pocket.',
  ),
  _Article(
    id: 'n4',
    title: 'Plant-Based Foods Rise in Global Restaurants',
    summary:
        'More restaurants are adding vegan options as demand grows worldwide.',
    category: 'Food',
    level: 'A2',
    readTime: '3 min',
    body:
        'Plant-based food is becoming very popular. Restaurants around the world are adding more vegan options to their menus. '
        'Big fast-food chains now sell burgers made from plants instead of meat. Many people say they taste just like real meat. '
        'Why are people choosing plant-based food? Some do it for their health. Others do it to help the environment. '
        'Growing plants uses less water and produces less pollution than raising animals. '
        'Chefs are getting creative with ingredients like tofu, lentils, jackfruit, and chickpeas. '
        'Even in countries where meat is very traditional, plant-based options are growing fast. '
        'Industry experts predict the plant-based market will double in size over the next five years.',
  ),
  _Article(
    id: 'n5',
    title: 'Record Heatwave Hits Southern Europe',
    summary:
        'Spain, Italy and Greece reach all-time high temperatures with health warnings issued.',
    category: 'Environment',
    level: 'B1',
    readTime: '4 min',
    body:
        'Southern Europe is experiencing its hottest summer on record. Temperatures in Spain, Italy, and Greece have broken previous highs, '
        'with some cities recording over 47 degrees Celsius. Authorities have issued health warnings urging residents to stay indoors during peak hours. '
        'Hospitals have reported a rise in heat-related illnesses, particularly among the elderly. '
        'Wildfires have broken out in several regions, forcing evacuations in coastal tourist areas. '
        'Climate scientists say this heatwave is consistent with predictions for a warming planet. '
        'The EU has activated its emergency coordination mechanism, releasing funds for firefighting and cooling centres. '
        'Environmental groups are calling on governments to accelerate the transition to renewable energy and reduce carbon emissions.',
  ),
];

// ---------------------------------------------------------------------------
// Colour constants (local, mirrors the spec)
// ---------------------------------------------------------------------------

const _kBackground = Color(0xFF090E1A);
const _kSurface = Color(0xFF1E2D45);
const _kBorder = Color(0xFF2A3A55);
const _kPrimary = Color(0xFF4F7FFF);
const _kAccent = Color(0xFF8B5CF6);
const _kTextPrimary = Color(0xFFF1F5FF);
const _kTextSecondary = Color(0xFF8896B0);
const _kSuccess = Color(0xFF22C55E);
const _kWarning = Color(0xFFF59E0B);

// Category colours
Color _categoryColor(String category) {
  switch (category) {
    case 'Science':
      return _kSuccess; // green
    case 'Travel':
      return _kWarning; // orange
    case 'Technology':
      return _kPrimary; // blue
    case 'Food':
      return const Color(0xFFFBBF24); // amber
    case 'Environment':
      return const Color(0xFF14B8A6); // teal
    default:
      return _kPrimary;
  }
}

// ---------------------------------------------------------------------------
// Main screen widget
// ---------------------------------------------------------------------------

class NewsTab extends StatefulWidget {
  const NewsTab({super.key});

  @override
  State<NewsTab> createState() => _NewsTabState();
}

class _NewsTabState extends State<NewsTab> with TickerProviderStateMixin {
  final AppState _appState = AppState();
  String? _playingArticleId;

  // Mini-player slide controller
  late final AnimationController _playerSlideController;
  late final Animation<Offset> _playerSlideAnim;

  // Equalizer animation controller
  late final AnimationController _eqController;

  // Progress value for fake slider
  double _progress = 0.35;

  String _selectedFilter = 'All';
  final List<String> _filters = [
    'All',
    'Science',
    'Travel',
    'Technology',
    'Food',
    'Environment',
  ];

  List<_Article> get _filteredArticles {
    return _allArticles.where((a) {
      final matchesLevel = a.level == _appState.cefrLevel;
      bool matchesFilter = false;
      if (_selectedFilter == 'All') {
        matchesFilter = true;
      } else {
        matchesFilter = a.category.toLowerCase() == _selectedFilter.toLowerCase();
      }
      return matchesLevel && matchesFilter;
    }).toList();
  }

  _Article? get _playingArticle {
    if (_playingArticleId == null) return null;
    try {
      return _allArticles.firstWhere((a) => a.id == _playingArticleId);
    } catch (_) {
      return null;
    }
  }

  void _onStateChange() {
    if (mounted) setState(() {});
  }

  @override
  void initState() {
    super.initState();
    _appState.addListener(_onStateChange);

    _playerSlideController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 380),
    );
    _playerSlideAnim = Tween<Offset>(
      begin: const Offset(0, 1),
      end: Offset.zero,
    ).animate(
      CurvedAnimation(
        parent: _playerSlideController,
        curve: Curves.easeOutCubic,
        reverseCurve: Curves.easeInCubic,
      ),
    );

    _eqController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _appState.removeListener(_onStateChange);
    _playerSlideController.dispose();
    _eqController.dispose();
    super.dispose();
  }

  void _togglePlay(String articleId) {
    setState(() {
      if (_playingArticleId == articleId) {
        // Pause / stop
        _playingArticleId = null;
        _playerSlideController.reverse();
        _eqController.stop();
      } else {
        _playingArticleId = articleId;
        _playerSlideController.forward();
        _eqController.repeat(reverse: true);
      }
    });
  }

  void _stopPlayer() {
    setState(() {
      _playingArticleId = null;
      _playerSlideController.reverse();
      _eqController.stop();
    });
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
              // Header
              SliverToBoxAdapter(
                child: _buildHeader(),
              ),

              // Filter chips
              SliverToBoxAdapter(
                child: _buildFilterChips(),
              ),

              const SliverToBoxAdapter(child: SizedBox(height: 8)),

              // Article cards
              SliverList(
                delegate: SliverChildBuilderDelegate(
                  (context, index) {
                    final article = _filteredArticles[index];
                    return _ArticleCard(
                      key: ValueKey(article.id),
                      article: article,
                      isPlaying: _playingArticleId == article.id,
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
                  childCount: _filteredArticles.length,
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
                onProgressChanged: (v) => setState(() => _progress = v),
                onStop: _stopPlayer,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── Header ───────────────────────────────────────────────────────────────

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Daily News 📰',
            style: GoogleFonts.inter(
              fontSize: 22,
              fontWeight: FontWeight.w700,
              color: _kTextPrimary,
              letterSpacing: -0.3,
            ),
          ).animate().fadeIn(duration: 300.ms).slideY(begin: -0.1, end: 0),
          const SizedBox(height: 4),
          Text(
            'Tailored to your level & interests',
            style: GoogleFonts.inter(
              fontSize: 13,
              color: _kTextSecondary,
              fontWeight: FontWeight.w400,
            ),
          ).animate().fadeIn(delay: 80.ms, duration: 300.ms),
        ],
      ),
    );
  }

  // ── Filter chips ─────────────────────────────────────────────────────────

  Widget _buildFilterChips() {
    return SizedBox(
      height: 44,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 20),
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemCount: _filters.length,
        itemBuilder: (context, i) {
          final filter = _filters[i];
          final selected = filter == _selectedFilter;
          return GestureDetector(
            onTap: () => setState(() => _selectedFilter = filter),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 220),
              curve: Curves.easeOut,
              padding:
                  const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
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
                  color: selected
                      ? Colors.transparent
                      : _kBorder,
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
                filter,
                style: GoogleFonts.inter(
                  fontSize: 13,
                  fontWeight:
                      selected ? FontWeight.w600 : FontWeight.w500,
                  color:
                      selected ? Colors.white : _kTextSecondary,
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Article Card
// ---------------------------------------------------------------------------

class _ArticleCard extends StatefulWidget {
  final _Article article;
  final bool isPlaying;
  final VoidCallback onPlayToggle;

  const _ArticleCard({
    super.key,
    required this.article,
    required this.isPlaying,
    required this.onPlayToggle,
  });

  @override
  State<_ArticleCard> createState() => _ArticleCardState();
}

class _ArticleCardState extends State<_ArticleCard> {
  bool _expanded = false;

  void _handleWordLongPress(String word, Offset position) {
    DictionaryPopup.show(context, word, position);
  }

  @override
  Widget build(BuildContext context) {
    final article = widget.article;
    final catColor = _categoryColor(article.category);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: GestureDetector(
        onTap: () => setState(() => _expanded = !_expanded),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          decoration: BoxDecoration(
            color: _kSurface,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: _kBorder, width: 1),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.30),
                blurRadius: 18,
                offset: const Offset(0, 6),
              ),
              if (widget.isPlaying)
                BoxShadow(
                  color: _kPrimary.withValues(alpha: 0.18),
                  blurRadius: 22,
                  spreadRadius: 2,
                ),
            ],
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Top accent line
                Container(
                  height: 3,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [catColor, catColor.withValues(alpha: 0.3)],
                    ),
                  ),
                ),

                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Top meta row
                      _buildMetaRow(article, catColor),

                      const SizedBox(height: 10),

                      // Title
                      Text(
                        article.title,
                        style: GoogleFonts.inter(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                          color: _kTextPrimary,
                          height: 1.25,
                          letterSpacing: -0.2,
                        ),
                      ),

                      const SizedBox(height: 6),

                      // Summary (2 lines max)
                      Text(
                        article.summary,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: GoogleFonts.inter(
                          fontSize: 13,
                          color: _kTextSecondary,
                          height: 1.5,
                        ),
                      ),

                      // Expandable body
                      AnimatedSize(
                        duration: const Duration(milliseconds: 300),
                        curve: Curves.easeInOutCubic,
                        child: _expanded
                            ? _buildExpandedBody(article)
                            : const SizedBox.shrink(),
                      ),

                      const SizedBox(height: 12),

                      // Bottom row
                      _buildBottomRow(article),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildMetaRow(_Article article, Color catColor) {
    return Row(
      children: [
        // Category chip
        Container(
          padding:
              const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
          decoration: BoxDecoration(
            color: catColor.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: catColor.withValues(alpha: 0.35),
              width: 1,
            ),
          ),
          child: Text(
            article.category,
            style: GoogleFonts.inter(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: catColor,
            ),
          ),
        ),

        const SizedBox(width: 8),

        // Level badge
        Container(
          padding:
              const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: _kPrimary.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: _kPrimary.withValues(alpha: 0.30),
              width: 1,
            ),
          ),
          child: Text(
            article.level,
            style: GoogleFonts.inter(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: _kPrimary,
            ),
          ),
        ),

        const Spacer(),

        // Reading time
        Icon(
          Icons.access_time_rounded,
          size: 13,
          color: _kTextSecondary,
        ),
        const SizedBox(width: 4),
        Text(
          article.readTime,
          style: GoogleFonts.inter(
            fontSize: 12,
            color: _kTextSecondary,
          ),
        ),

        // Expand indicator
        const SizedBox(width: 8),
        AnimatedRotation(
          turns: _expanded ? 0.5 : 0,
          duration: const Duration(milliseconds: 260),
          child: const Icon(
            Icons.keyboard_arrow_down_rounded,
            size: 18,
            color: _kTextSecondary,
          ),
        ),
      ],
    );
  }

  Widget _buildExpandedBody(_Article article) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 12),

        // Divider
        Container(
          height: 1,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                Colors.transparent,
                _kBorder,
                Colors.transparent,
              ],
            ),
          ),
        ),

        const SizedBox(height: 10),

        // Hint
        Row(
          children: [
            const Icon(
              Icons.touch_app_rounded,
              size: 13,
              color: _kAccent,
            ),
            const SizedBox(width: 5),
            Text(
              'Tap any word to look it up',
              style: GoogleFonts.inter(
                fontSize: 11,
                color: _kAccent,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),

        const SizedBox(height: 10),

        // Selectable body with per-word long-press
        _WordTapText(
          text: article.body,
          onWordLongPress: _handleWordLongPress,
        ),
      ],
    );
  }

  Widget _buildBottomRow(_Article article) {
    return Row(
      children: [
        const Icon(
          Icons.menu_book_rounded,
          size: 14,
          color: _kTextSecondary,
        ),
        const SizedBox(width: 5),
        Text(
          '${article.readTime} read',
          style: GoogleFonts.inter(
            fontSize: 12,
            color: _kTextSecondary,
          ),
        ),

        const Spacer(),

        // Play / Pause button
        GestureDetector(
          onTap: widget.onPlayToggle,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 220),
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                colors: widget.isPlaying
                    ? [_kAccent, _kPrimary]
                    : [_kPrimary, _kAccent],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              boxShadow: [
                BoxShadow(
                  color: _kPrimary.withValues(alpha: 0.4),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Icon(
              widget.isPlaying
                  ? Icons.pause_rounded
                  : Icons.play_arrow_rounded,
              color: Colors.white,
              size: 22,
            ),
          ),
        ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Word-tap text widget (long-press individual word → dictionary)
// ---------------------------------------------------------------------------

class _WordTapText extends StatelessWidget {
  final String text;
  final void Function(String word, Offset globalPosition) onWordLongPress;

  const _WordTapText({
    required this.text,
    required this.onWordLongPress,
  });

  @override
  Widget build(BuildContext context) {
    final words = text.split(' ');
    return SelectableText.rich(
      TextSpan(
        children: words.asMap().entries.map((entry) {
          final i = entry.key;
          final word = entry.value;
          return WidgetSpan(
            child: GestureDetector(
              onLongPressStart: (details) {
                // Strip punctuation for lookup
                final clean =
                    word.replaceAll(RegExp(r'[^\w]'), '');
                if (clean.isNotEmpty) {
                  onWordLongPress(
                    clean,
                    details.globalPosition,
                  );
                }
              },
              child: Text(
                i == words.length - 1 ? word : '$word ',
                style: GoogleFonts.inter(
                  fontSize: 14,
                  color: _kTextPrimary.withValues(alpha: 0.88),
                  height: 1.65,
                ),
              ),
            ),
          );
        }).toList(),
      ),
      enableInteractiveSelection: true,
    );
  }
}

// ---------------------------------------------------------------------------
// Mini Player
// ---------------------------------------------------------------------------

class _MiniPlayer extends StatelessWidget {
  final _Article? article;
  final double progress;
  final AnimationController eqController;
  final ValueChanged<double> onProgressChanged;
  final VoidCallback onStop;

  const _MiniPlayer({
    required this.article,
    required this.progress,
    required this.eqController,
    required this.onProgressChanged,
    required this.onStop,
  });

  @override
  Widget build(BuildContext context) {
    if (article == null) return const SizedBox.shrink();

    return Container(
      height: 86,
      decoration: BoxDecoration(
        color: const Color(0xFF1A2235),
        border: Border(
          top: BorderSide(
            color: Colors.transparent,
            width: 0,
          ),
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.6),
            blurRadius: 24,
            offset: const Offset(0, -4),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Top gradient border
          Container(
            height: 2,
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [_kPrimary, _kAccent, _kPrimary],
              ),
            ),
          ),

          Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  // Equalizer animation
                  _EqualizerBars(controller: eqController),

                  const SizedBox(width: 14),

                  // Title + label + slider
                  Expanded(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Now Playing',
                          style: GoogleFonts.inter(
                            fontSize: 10,
                            color: _kPrimary,
                            fontWeight: FontWeight.w600,
                            letterSpacing: 0.5,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          article!.title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: GoogleFonts.inter(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: _kTextPrimary,
                          ),
                        ),
                        const SizedBox(height: 2),
                        SliderTheme(
                          data: SliderThemeData(
                            trackHeight: 2.5,
                            thumbShape: const RoundSliderThumbShape(
                              enabledThumbRadius: 5,
                            ),
                            overlayShape: const RoundSliderOverlayShape(
                              overlayRadius: 10,
                            ),
                            activeTrackColor: _kPrimary,
                            inactiveTrackColor: _kBorder,
                            thumbColor: _kPrimary,
                            overlayColor: _kPrimary.withValues(alpha: 0.15),
                          ),
                          child: Slider(
                            value: progress,
                            onChanged: onProgressChanged,
                            min: 0,
                            max: 1,
                          ),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(width: 8),

                  // Pause / stop button
                  GestureDetector(
                    onTap: onStop,
                    child: Container(
                      width: 38,
                      height: 38,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: const LinearGradient(
                          colors: [_kPrimary, _kAccent],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: _kPrimary.withValues(alpha: 0.4),
                            blurRadius: 10,
                            offset: const Offset(0, 3),
                          ),
                        ],
                      ),
                      child: const Icon(
                        Icons.pause_rounded,
                        color: Colors.white,
                        size: 20,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Animated equalizer bars
// ---------------------------------------------------------------------------

class _EqualizerBars extends StatelessWidget {
  final AnimationController controller;

  const _EqualizerBars({required this.controller});

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        final t = controller.value;
        // Stagger each bar with a different phase
        final h1 = _barHeight(t, 0.0);
        final h2 = _barHeight(t, 0.33);
        final h3 = _barHeight(t, 0.66);

        return Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            _Bar(height: h1, color: _kPrimary),
            const SizedBox(width: 3),
            _Bar(height: h2, color: _kAccent),
            const SizedBox(width: 3),
            _Bar(height: h3, color: _kPrimary),
          ],
        );
      },
    );
  }

  double _barHeight(double t, double phase) {
    final shifted = (t + phase) % 1.0;
    // Simple sine-like interpolation using lerp
    final sin = (shifted < 0.5) ? shifted * 2 : (1 - shifted) * 2;
    return 8 + sin * 20;
  }
}

class _Bar extends StatelessWidget {
  final double height;
  final Color color;

  const _Bar({required this.height, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 4,
      height: height,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(2),
      ),
    );
  }
}
