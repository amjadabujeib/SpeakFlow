part of 'news_tab.dart';

class _Article {
  final String id;
  final String title;
  final String summary;
  final String category;
  final String level;
  final String body;

  const _Article({
    required this.id,
    required this.title,
    required this.summary,
    required this.category,
    required this.level,
    required this.body,
  });

  factory _Article.fromJson(
    Map<String, dynamic> json, {
    required String category,
    required String level,
  }) {
    final summary = json['simplified_summary']?.toString().trim() ?? '';
    return _Article(
      id:
          json['id']?.toString() ??
          json['url']?.toString() ??
          json['title'].toString(),
      title: json['title']?.toString().trim() ?? '',
      summary: summary,
      category: category,
      level: level,
      body: summary,
    );
  }
}

class _NewsCategory {
  final String label;
  final String value;

  const _NewsCategory(this.label, this.value);
}

const _newsCategories = [
  _NewsCategory('Top', 'general'),
  _NewsCategory('Business', 'business'),
  _NewsCategory('Entertainment', 'entertainment'),
  _NewsCategory('Health', 'health'),
  _NewsCategory('Science', 'science'),
  _NewsCategory('Sports', 'sports'),
  _NewsCategory('Technology', 'technology'),
];

typedef NewsLoader =
    Future<Map<String, dynamic>> Function({
      required String category,
      required String level,
      int page,
    });

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
    case 'Sports':
      return _kWarning; // orange
    case 'Technology':
      return _kPrimary; // blue
    case 'Business':
      return const Color(0xFFFBBF24); // amber
    case 'Health':
      return const Color(0xFF14B8A6); // teal
    case 'Entertainment':
      return _kAccent;
    default:
      return _kPrimary;
  }
}

// ---------------------------------------------------------------------------
// Main screen widget
// ---------------------------------------------------------------------------
