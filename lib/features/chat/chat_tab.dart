import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:go_router/go_router.dart';

// ─────────────────────────────────────────────
// Data models
// ─────────────────────────────────────────────

class RoleplayItem {
  final String id;
  final String title;
  final String desc;
  int sessions;

  RoleplayItem({
    required this.id,
    required this.title,
    required this.desc,
    required this.sessions,
  });
}

class SectionItem {
  final String id;
  final String title;
  final String icon;
  final List<RoleplayItem> roleplays;

  SectionItem({
    required this.id,
    required this.title,
    required this.icon,
    required this.roleplays,
  });
}

// ─────────────────────────────────────────────
// Mock data
// ─────────────────────────────────────────────

final List<SectionItem> _mockSections = [
  SectionItem(
    id: 's1',
    title: 'Travel',
    icon: '✈️',
    roleplays: [
      RoleplayItem(id: 'r1', title: 'Airport Check-in', desc: 'Check in for a flight', sessions: 3),
      RoleplayItem(id: 'r2', title: 'Hotel Check-in', desc: 'Book a room', sessions: 1),
      RoleplayItem(id: 'r3', title: 'Asking for Directions', desc: 'Navigate a city', sessions: 0),
    ],
  ),
  SectionItem(
    id: 's2',
    title: 'Food & Dining',
    icon: '🍽️',
    roleplays: [
      RoleplayItem(id: 'r4', title: 'Ordering at Restaurant', desc: 'Order food and handle bill', sessions: 2),
      RoleplayItem(id: 'r5', title: 'Café Small Talk', desc: 'Casual conversation', sessions: 0),
    ],
  ),
  SectionItem(
    id: 's3',
    title: 'Business',
    icon: '💼',
    roleplays: [
      RoleplayItem(id: 'r6', title: 'Job Interview', desc: 'Practice interview questions', sessions: 4),
      RoleplayItem(id: 'r7', title: 'Business Meeting', desc: 'Present ideas in meetings', sessions: 1),
    ],
  ),
];

// ─────────────────────────────────────────────
// Colors
// ─────────────────────────────────────────────

const _background   = Color(0xFF090E1A);
const _surface      = Color(0xFF111827);
const _surfaceCard  = Color(0xFF1A2235);
const _surfaceCard2 = Color(0xFF1E2D45);
const _primary      = Color(0xFF4F7FFF);
const _accent       = Color(0xFF8B5CF6);
const _success      = Color(0xFF22C55E);
const _warning      = Color(0xFFF59E0B);
const _textPrimary  = Color(0xFFF1F5FF);
const _textSecondary= Color(0xFF8896B0);
const _border       = Color(0xFF1E2D45);

// ─────────────────────────────────────────────
// Chat Tab
// ─────────────────────────────────────────────

class ChatTab extends StatefulWidget {
  const ChatTab({super.key});

  @override
  State<ChatTab> createState() => _ChatTabState();
}

class _ChatTabState extends State<ChatTab> {
  late List<SectionItem> _sections;
  final Set<String> _expanded = {'s1'};

  @override
  void initState() {
    super.initState();
    _sections = List.from(_mockSections);
  }

  // ── History bottom sheet ──────────────────

  void _openHistory() {
    showModalBottomSheet(
      context: context,
      backgroundColor: _surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => _HistorySheet(),
    );
  }

  // ── Add section dialog ────────────────────

  void _showAddSectionDialog() {
    final nameCtrl = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _surfaceCard,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text(
          'New Section',
          style: GoogleFonts.inter(color: _textPrimary, fontWeight: FontWeight.bold),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _DialogTextField(controller: nameCtrl, hint: 'Section name (e.g. Shopping)'),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('Cancel', style: GoogleFonts.inter(color: _textSecondary)),
          ),
          _GradientButton(
            label: 'Create',
            onTap: () {
              final name = nameCtrl.text.trim();
              if (name.isNotEmpty) {
                setState(() {
                  final id = 's${_sections.length + 1}';
                  _sections.add(SectionItem(id: id, title: name, icon: '📌', roleplays: []));
                  _expanded.add(id);
                });
              }
              Navigator.pop(ctx);
            },
          ),
        ],
      ),
    );
  }

  // ── Add roleplay dialog ───────────────────

  void _showAddRoleplayDialog(SectionItem section) {
    final nameCtrl   = TextEditingController();
    final promptCtrl = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _surfaceCard,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text(
          'Add Roleplay to ${section.title}',
          style: GoogleFonts.inter(color: _textPrimary, fontWeight: FontWeight.bold, fontSize: 16),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _DialogTextField(controller: nameCtrl, hint: 'Roleplay name'),
            const SizedBox(height: 12),
            _DialogTextField(controller: promptCtrl, hint: 'AI prompt / scenario description', maxLines: 3),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('Cancel', style: GoogleFonts.inter(color: _textSecondary)),
          ),
          _GradientButton(
            label: 'Add',
            onTap: () {
              final name   = nameCtrl.text.trim();
              final prompt = promptCtrl.text.trim();
              if (name.isNotEmpty) {
                setState(() {
                  section.roleplays.add(
                    RoleplayItem(
                      id: 'r_new_${DateTime.now().millisecondsSinceEpoch}',
                      title: name,
                      desc: prompt.isEmpty ? 'Custom roleplay' : prompt,
                      sessions: 0,
                    ),
                  );
                });
              }
              Navigator.pop(ctx);
            },
          ),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _background,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            Expanded(
              child: ListView.builder(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 100),
                itemCount: _sections.length,
                itemBuilder: (context, index) {
                  return _SectionCard(
                    section: _sections[index],
                    isExpanded: _expanded.contains(_sections[index].id),
                    onToggle: () => setState(() {
                      if (_expanded.contains(_sections[index].id)) {
                        _expanded.remove(_sections[index].id);
                      } else {
                        _expanded.add(_sections[index].id);
                      }
                    }),
                    onAddRoleplay: () => _showAddRoleplayDialog(_sections[index]),
                  ).animate().fadeIn(delay: Duration(milliseconds: index * 80)).slideY(begin: 0.06, end: 0);
                },
              ),
            ),
          ],
        ),
      ),
      floatingActionButton: _buildFAB(),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 20, 12, 4),
      child: Row(
        children: [
          ShaderMask(
            shaderCallback: (b) => const LinearGradient(
              colors: [_primary, _accent],
            ).createShader(b),
            child: Text(
              'Conversations',
              style: GoogleFonts.inter(
                fontSize: 26,
                fontWeight: FontWeight.w800,
                color: Colors.white,
              ),
            ),
          ),
          const Spacer(),
          _IconBtn(
            icon: Icons.history_rounded,
            onTap: _openHistory,
          ),
        ],
      ),
    );
  }

  Widget _buildFAB() {
    return GestureDetector(
      onTap: _showAddSectionDialog,
      child: Container(
        width: 60,
        height: 60,
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [_primary, _accent],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(18),
          boxShadow: [
            BoxShadow(
              color: _primary.withOpacity(0.4),
              blurRadius: 16,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: const Icon(Icons.add_rounded, color: Colors.white, size: 30),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Section card
// ─────────────────────────────────────────────

class _SectionCard extends StatelessWidget {
  final SectionItem section;
  final bool isExpanded;
  final VoidCallback onToggle;
  final VoidCallback onAddRoleplay;

  const _SectionCard({
    required this.section,
    required this.isExpanded,
    required this.onToggle,
    required this.onAddRoleplay,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      decoration: BoxDecoration(
        color: _surfaceCard,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _border, width: 1),
      ),
      child: Column(
        children: [
          // Header row
          InkWell(
            onTap: onToggle,
            borderRadius: isExpanded
                ? const BorderRadius.vertical(top: Radius.circular(20))
                : BorderRadius.circular(20),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              child: Row(
                children: [
                  Text(section.icon, style: const TextStyle(fontSize: 22)),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      section.title,
                      style: GoogleFonts.inter(
                        color: _textPrimary,
                        fontWeight: FontWeight.w700,
                        fontSize: 16,
                      ),
                    ),
                  ),
                  // Add roleplay button
                  GestureDetector(
                    onTap: onAddRoleplay,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                      decoration: BoxDecoration(
                        border: Border.all(color: _primary.withOpacity(0.6)),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        '+ Add Roleplay',
                        style: GoogleFonts.inter(
                          color: _primary,
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  AnimatedRotation(
                    turns: isExpanded ? 0.5 : 0,
                    duration: const Duration(milliseconds: 250),
                    child: const Icon(Icons.keyboard_arrow_down_rounded,
                        color: _textSecondary, size: 22),
                  ),
                ],
              ),
            ),
          ),
          // Expanded roleplays
          AnimatedCrossFade(
            duration: const Duration(milliseconds: 280),
            crossFadeState: isExpanded ? CrossFadeState.showSecond : CrossFadeState.showFirst,
            firstChild: const SizedBox.shrink(),
            secondChild: Column(
              children: [
                const Divider(color: _border, height: 1),
                const SizedBox(height: 8),
                if (section.roleplays.isEmpty)
                  Padding(
                    padding: const EdgeInsets.all(16),
                    child: Text(
                      'No roleplays yet. Tap "+ Add Roleplay" to create one.',
                      style: GoogleFonts.inter(color: _textSecondary, fontSize: 13),
                      textAlign: TextAlign.center,
                    ),
                  )
                else
                  ...section.roleplays.map((r) => _RoleplayCard(roleplay: r)),
                const SizedBox(height: 8),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Roleplay card
// ─────────────────────────────────────────────

class _RoleplayCard extends StatelessWidget {
  final RoleplayItem roleplay;
  const _RoleplayCard({required this.roleplay});

  Color get _borderColor {
    final colors = [_primary, _accent, _success, _warning];
    final idx = roleplay.id.hashCode.abs() % colors.length;
    return colors[idx];
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
      decoration: BoxDecoration(
        color: _surfaceCard2,
        borderRadius: BorderRadius.circular(14),
        border: Border(left: BorderSide(color: _borderColor, width: 3)),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 12, 12, 12),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    roleplay.title,
                    style: GoogleFonts.inter(
                      color: _textPrimary,
                      fontWeight: FontWeight.w600,
                      fontSize: 14,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    roleplay.desc,
                    style: GoogleFonts.inter(color: _textSecondary, fontSize: 12),
                  ),
                  const SizedBox(height: 7),
                  // Session count badge
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: _primary.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      roleplay.sessions == 0
                          ? 'No sessions yet'
                          : '${roleplay.sessions} session${roleplay.sessions == 1 ? '' : 's'}',
                      style: GoogleFonts.inter(
                        color: _primary,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 10),
            // Start button
            GestureDetector(
              onTap: () => context.push('/chat/roleplay', extra: roleplay.title),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [_primary, _accent],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(10),
                  boxShadow: [
                    BoxShadow(
                      color: _primary.withOpacity(0.3),
                      blurRadius: 8,
                      offset: const Offset(0, 3),
                    ),
                  ],
                ),
                child: Text(
                  'Start',
                  style: GoogleFonts.inter(
                    color: Colors.white,
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// History bottom sheet
// ─────────────────────────────────────────────

class _HistorySheet extends StatelessWidget {
  final List<Map<String, String>> _history = const [
    {'title': 'Airport Check-in', 'date': 'Jun 24, 2026', 'score': '82'},
    {'title': 'Job Interview', 'date': 'Jun 22, 2026', 'score': '76'},
    {'title': 'Ordering at Restaurant', 'date': 'Jun 20, 2026', 'score': '91'},
    {'title': 'Hotel Check-in', 'date': 'Jun 18, 2026', 'score': '68'},
    {'title': 'Business Meeting', 'date': 'Jun 15, 2026', 'score': '85'},
  ];

  const _HistorySheet();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Handle
          Center(
            child: Container(
              width: 40,
              height: 4,
              margin: const EdgeInsets.only(bottom: 16),
              decoration: BoxDecoration(
                color: _border,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          Row(
            children: [
              const Icon(Icons.history_rounded, color: _primary, size: 22),
              const SizedBox(width: 8),
              Text(
                'Session History',
                style: GoogleFonts.inter(
                  color: _textPrimary,
                  fontWeight: FontWeight.w700,
                  fontSize: 18,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          ..._history.asMap().entries.map((e) {
            final item  = e.value;
            final score = int.parse(item['score']!);
            final color = score >= 80 ? _success : score >= 60 ? _warning : const Color(0xFFEF4444);
            return Container(
              margin: const EdgeInsets.only(bottom: 10),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: _surfaceCard,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: _border),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(item['title']!, style: GoogleFonts.inter(color: _textPrimary, fontWeight: FontWeight.w600)),
                        const SizedBox(height: 3),
                        Text(item['date']!, style: GoogleFonts.inter(color: _textSecondary, fontSize: 12)),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                      color: color.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      '${item['score']}%',
                      style: GoogleFonts.inter(color: color, fontWeight: FontWeight.w700, fontSize: 13),
                    ),
                  ),
                ],
              ),
            ).animate().fadeIn(delay: Duration(milliseconds: e.key * 60)).slideY(begin: 0.05, end: 0);
          }),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────
// Shared small widgets
// ─────────────────────────────────────────────

class _IconBtn extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;
  const _IconBtn({required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return IconButton(
      onPressed: onTap,
      style: IconButton.styleFrom(
        backgroundColor: _surfaceCard,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      icon: Icon(icon, color: _textPrimary, size: 20),
    );
  }
}

class _DialogTextField extends StatelessWidget {
  final TextEditingController controller;
  final String hint;
  final int maxLines;
  const _DialogTextField({required this.controller, required this.hint, this.maxLines = 1});

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      maxLines: maxLines,
      style: GoogleFonts.inter(color: _textPrimary),
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: GoogleFonts.inter(color: _textSecondary, fontSize: 13),
        filled: true,
        fillColor: _surfaceCard2,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: _border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: _border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: _primary),
        ),
      ),
    );
  }
}

class _GradientButton extends StatelessWidget {
  final String label;
  final VoidCallback onTap;
  const _GradientButton({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
        decoration: BoxDecoration(
          gradient: const LinearGradient(colors: [_primary, _accent]),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Text(
          label,
          style: GoogleFonts.inter(color: Colors.white, fontWeight: FontWeight.w700),
        ),
      ),
    );
  }
}
