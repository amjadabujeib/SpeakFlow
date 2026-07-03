// lib/core/data/mock_data.dart

class MockData {
  // ── Onboarding ──────────────────────────────────────────────────
  static const List<Map<String, String>> cefrLevels = [
    {
      'level': 'A1',
      'title': 'Total Beginner',
      'description': 'I know very little English — just a few basic words.',
    },
    {
      'level': 'A2',
      'title': 'Elementary',
      'description': 'I can handle simple conversations on familiar topics.',
    },
    {
      'level': 'B1',
      'title': 'Intermediate',
      'description': 'I can manage most situations when travelling in English.',
    },
    {
      'level': 'B2',
      'title': 'Upper Intermediate',
      'description': 'I can discuss complex topics and understand native speakers.',
    },
    {
      'level': 'C1',
      'title': 'Advanced',
      'description': 'I express myself fluently and spontaneously with ease.',
    },
    {
      'level': 'C2',
      'title': 'Mastery',
      'description': 'I understand virtually everything I read or hear.',
    },
  ];

  static const List<String> learningGoals = [
    'Travel & Tourism',
    'Business & Career',
    'Academic Study',
    'Daily Conversation',
    'Media & Entertainment',
    'Immigration',
  ];

  static const List<String> interests = [
    'Travel',
    'Business',
    'Technology',
    'Food & Cooking',
    'Sports',
    'Music',
    'Science',
    'History',
    'Health',
    'Arts & Culture',
    'Politics',
    'Environment',
  ];

  static const List<String> languages = [
    'Arabic',
    'French',
    'Spanish',
    'German',
    'Chinese',
    'Japanese',
    'Portuguese',
    'Russian',
    'Turkish',
    'Hindi',
  ];

  // ── Home / Learning Plan ─────────────────────────────────────────
  static const List<Map<String, dynamic>> learningPlan = [
    {
      'id': 'unit_1',
      'title': 'Unit 1: Everyday Greetings',
      'description': 'Master the fundamentals of English greetings and self-introduction.',
      'status': 'completed', // completed | in_progress | locked
      'lessons': [
        {
          'id': 'l1_pronunciation',
          'title': 'Pronunciation',
          'name': 'Vowel sounds in greetings',
          'status': 'completed',
        },
        {
          'id': 'l1_grammar',
          'title': 'Grammar',
          'name': 'Subject pronouns & to be',
          'status': 'completed',
        },
        {
          'id': 'l1_vocabulary',
          'title': 'Vocabulary',
          'name': 'Common greeting phrases',
          'status': 'completed',
        },
      ],
    },
    {
      'id': 'unit_2',
      'title': 'Unit 2: Talking About Yourself',
      'description': 'Learn to describe your background, hobbies, and daily routine.',
      'status': 'in_progress',
      'lessons': [
        {
          'id': 'l2_pronunciation',
          'title': 'Pronunciation',
          'name': 'Linking words & sentence stress',
          'status': 'completed',
        },
        {
          'id': 'l2_grammar',
          'title': 'Grammar',
          'name': 'Simple present tense',
          'status': 'in_progress',
        },
        {
          'id': 'l2_vocabulary',
          'title': 'Vocabulary',
          'name': 'Hobbies & daily activities',
          'status': 'locked',
        },
      ],
    },
    {
      'id': 'unit_3',
      'title': 'Unit 3: Getting Around',
      'description': 'Navigate airports, streets, and public transport with confidence.',
      'status': 'locked',
      'lessons': [
        {
          'id': 'l3_pronunciation',
          'title': 'Pronunciation',
          'name': 'Consonant clusters',
          'status': 'locked',
        },
        {
          'id': 'l3_grammar',
          'title': 'Grammar',
          'name': 'Imperatives & directions',
          'status': 'locked',
        },
        {
          'id': 'l3_vocabulary',
          'title': 'Vocabulary',
          'name': 'Transport & location words',
          'status': 'locked',
        },
      ],
    },
    {
      'id': 'unit_4',
      'title': 'Unit 4: At the Restaurant',
      'description': 'Order food, handle menus, and make small talk while dining out.',
      'status': 'locked',
      'lessons': [
        {
          'id': 'l4_pronunciation',
          'title': 'Pronunciation',
          'name': 'Word stress patterns',
          'status': 'locked',
        },
        {
          'id': 'l4_grammar',
          'title': 'Grammar',
          'name': 'Modal verbs (would, can)',
          'status': 'locked',
        },
        {
          'id': 'l4_vocabulary',
          'title': 'Vocabulary',
          'name': 'Food, drinks & menus',
          'status': 'locked',
        },
      ],
    },
  ];

  // ── Streak ──────────────────────────────────────────────────────
  static const int currentStreak = 7;
  static const List<bool> weekStudied = [true, true, false, true, true, true, false];
  // Mon Tue Wed Thu Fri Sat Sun

  // ── Practice ───────────────────────────────────────────────────
  static const List<Map<String, dynamic>> mispronounced = [
    {
      'word': 'thoroughly',
      'ipa': '/ˈθɜːrəli/',
      'score': 42,
      'source': 'Airport roleplay',
    },
    {
      'word': 'comfortable',
      'ipa': '/ˈkʌmftəbəl/',
      'score': 58,
      'source': 'Hotel check-in roleplay',
    },
    {
      'word': 'enthusiasm',
      'ipa': '/ɪnˈθjuːziæzəm/',
      'score': 35,
      'source': 'Job interview roleplay',
    },
    {
      'word': 'particularly',
      'ipa': '/pəˈtɪkjələrli/',
      'score': 61,
      'source': 'Coffee shop roleplay',
    },
    {
      'word': 'literature',
      'ipa': '/ˈlɪtrətʃər/',
      'score': 48,
      'source': 'Own practice',
    },
  ];

  // IPA phoneme heatmap data: key = phoneme symbol, value = accuracy 0–100
  static const Map<String, double> phonemeScores = {
    // Vowels
    'iː': 88.0, 'ɪ': 72.0, 'e': 65.0, 'æ': 44.0, 'ɑː': 78.0,
    'ɒ': 55.0, 'ɔː': 82.0, 'ʊ': 68.0, 'uː': 90.0, 'ʌ': 50.0,
    'ɜː': 38.0, 'ə': 71.0, 'eɪ': 85.0, 'aɪ': 76.0, 'ɔɪ': 62.0,
    'aʊ': 58.0, 'əʊ': 74.0, 'ɪə': 45.0, 'eə': 41.0, 'ʊə': 39.0,
    // Consonants
    'p': 92.0, 'b': 88.0, 't': 85.0, 'd': 80.0, 'k': 87.0,
    'g': 75.0, 'f': 83.0, 'v': 70.0, 'θ': 28.0, 'ð': 32.0,
    's': 86.0, 'z': 72.0, 'ʃ': 65.0, 'ʒ': 48.0, 'h': 91.0,
    'tʃ': 77.0, 'dʒ': 68.0, 'm': 94.0, 'n': 90.0, 'ŋ': 60.0,
    'l': 82.0, 'r': 55.0, 'j': 88.0, 'w': 89.0,
  };

  // ── Chat / Roleplay sections ────────────────────────────────────
  static const List<Map<String, dynamic>> chatSections = [
    {
      'id': 's1',
      'title': 'Travel',
      'icon': '✈️',
      'roleplays': [
        {
          'id': 'r1',
          'title': 'Airport Check-in',
          'description': 'Check in for a flight, handle baggage, and ask about gates.',
          'prompt': 'You are a friendly airline check-in agent at Heathrow Airport.',
          'sessionCount': 3,
        },
        {
          'id': 'r2',
          'title': 'Hotel Check-in',
          'description': 'Book a room, request amenities, and handle issues.',
          'prompt': 'You are a professional hotel receptionist at a 5-star hotel.',
          'sessionCount': 1,
        },
        {
          'id': 'r3',
          'title': 'Asking for Directions',
          'description': 'Navigate an unfamiliar city using public directions.',
          'prompt': 'You are a helpful local in London who knows the city well.',
          'sessionCount': 0,
        },
      ],
    },
    {
      'id': 's2',
      'title': 'Food & Dining',
      'icon': '🍽️',
      'roleplays': [
        {
          'id': 'r4',
          'title': 'Ordering at a Restaurant',
          'description': 'Order food, ask about ingredients, and handle the bill.',
          'prompt': 'You are a waiter at an upscale London restaurant.',
          'sessionCount': 2,
        },
        {
          'id': 'r5',
          'title': 'Café Small Talk',
          'description': 'Have a casual conversation while waiting for your order.',
          'prompt': 'You are a friendly barista at a cozy coffee shop.',
          'sessionCount': 0,
        },
      ],
    },
    {
      'id': 's3',
      'title': 'Business',
      'icon': '💼',
      'roleplays': [
        {
          'id': 'r6',
          'title': 'Job Interview',
          'description': 'Practice answering common interview questions professionally.',
          'prompt': 'You are an HR manager interviewing for a marketing position.',
          'sessionCount': 4,
        },
        {
          'id': 'r7',
          'title': 'Business Meeting',
          'description': 'Present ideas, take notes, and handle disagreements.',
          'prompt': 'You are a colleague in a team meeting discussing project updates.',
          'sessionCount': 1,
        },
      ],
    },
  ];

  // ── Chat messages (mock conversation) ──────────────────────────
  static const List<Map<String, dynamic>> mockMessages = [
    {
      'id': 'm1',
      'isUser': false,
      'text': 'Good morning! Welcome to Heathrow Airport. May I see your passport and ticket, please?',
      'translation': null,
    },
    {
      'id': 'm2',
      'isUser': true,
      'text': 'Good morning! Here is my passport. I am checking in for the flight to New York.',
      'pronScore': 82.0,
      'hint': "Great sentence structure! 'Here is' is correct. Try linking 'checking in' more smoothly.",
      'translation': null,
    },
    {
      'id': 'm3',
      'isUser': false,
      'text': "Thank you. Do you have any bags to check in today? And would you prefer a window or aisle seat?",
      'translation': null,
    },
    {
      'id': 'm4',
      'isUser': true,
      'text': 'I have one bag for check. And I want window seat, please.',
      'pronScore': 64.0,
      'hint': "Say 'one bag to check in' (not 'for check'). Also add the article: 'a window seat'.",
      'translation': null,
    },
    {
      'id': 'm5',
      'isUser': false,
      'text': "No problem! I've assigned you seat 14A — a lovely window seat. Your flight boards at Gate 22 in two hours.",
      'translation': null,
    },
  ];

  // ── News articles ───────────────────────────────────────────────
  static const List<Map<String, dynamic>> newsArticles = [
    {
      'id': 'n1',
      'title': 'Scientists Discover New Species of Deep-Sea Fish',
      'summary':
          'A team of marine biologists has identified a remarkable new species living nearly 3 kilometers below the ocean surface.',
      'category': 'Science',
      'level': 'B1',
      'readingTime': '3 min',
      'body':
          'A team of marine biologists working in the Pacific Ocean has made an exciting discovery. They found a new species of fish living nearly 3,000 meters below the surface. The fish, which has no eyes and produces its own light, was discovered using a deep-sea submersible. Scientists believe there may be thousands of undiscovered species in the deep ocean.',
    },
    {
      'id': 'n2',
      'title': 'Global Travel Rebounds to Pre-Pandemic Levels',
      'summary':
          'International tourism has fully recovered, with record numbers of travellers crossing borders this summer.',
      'category': 'Travel',
      'level': 'B2',
      'readingTime': '4 min',
      'body':
          'The tourism industry has officially bounced back. According to the World Tourism Organization, international arrivals this year have matched 2019 figures for the first time since the pandemic. Popular destinations like France, Spain, and Thailand are reporting record visitor numbers. Airlines have increased their flight schedules to meet the high demand.',
    },
    {
      'id': 'n3',
      'title': 'New AI Tools Are Changing How We Learn Languages',
      'summary':
          'Artificial intelligence is revolutionizing language education, making personalized learning accessible to millions.',
      'category': 'Technology',
      'level': 'A2',
      'readingTime': '2 min',
      'body':
          'Learning a new language is now easier than ever. New apps use artificial intelligence to create personalized lessons for each student. The AI can listen to your pronunciation and give instant feedback. Many students say they learn faster with AI tools than in traditional classrooms. Experts believe AI will change education for millions of people around the world.',
    },
    {
      'id': 'n4',
      'title': 'The Rise of Plant-Based Foods in Global Restaurants',
      'summary':
          'More restaurants worldwide are adding vegan and plant-based options to their menus as demand grows.',
      'category': 'Food',
      'level': 'A2',
      'readingTime': '3 min',
      'body':
          'Plant-based food is becoming very popular. Restaurants around the world are adding more vegan dishes to their menus. Big chains like McDonald\'s and KFC now offer plant-based burgers. Many people choose these options for health or environmental reasons. Chefs are getting creative with vegetables, creating dishes that even meat-lovers enjoy.',
    },
    {
      'id': 'n5',
      'title': 'Record-Breaking Heatwave Hits Southern Europe',
      'summary':
          'Temperatures across Spain, Italy, and Greece have reached all-time highs, prompting health warnings.',
      'category': 'Environment',
      'level': 'B1',
      'readingTime': '4 min',
      'body':
          'Southern Europe is experiencing its hottest summer on record. Temperatures in Spain reached 46°C last week, breaking the previous record set in 2021. Authorities have issued health warnings and opened cooling centers for vulnerable populations. Scientists warn that such extreme heat events will become more common due to climate change. Wildfires have broken out in several regions.',
    },
  ];

  // ── Session feedback ────────────────────────────────────────────
  static const Map<String, dynamic> sessionFeedback = {
    'roleplayTitle': 'Airport Check-in',
    'duration': '8 min 34 sec',
    'pronounciationScore': 71,
    'fluencyScore': 65,
    'lexicalScore': 78,
    'grammarErrors': 4,
    'messageCount': 12,
    'mispronounced': ['check', 'particularly', 'enthusiastic'],
    'corrections': [
      "Use 'a window seat' not 'window seat'",
      "Say 'I'd like to check in' for more natural phrasing",
      "'I have been waiting' (present perfect) instead of 'I waited'",
    ],
  };

  // ── Dictionary popup ────────────────────────────────────────────
  static const Map<String, dynamic> dictionaryEntry = {
    'word': 'thoroughly',
    'ipa': '/ˈθɜːrəli/',
    'partOfSpeech': 'adverb',
    'translation': 'بشكل شامل',
    'definition': 'In a thorough manner; completely and with great attention to detail.',
    'example': 'She thoroughly enjoyed the concert.',
  };
}
