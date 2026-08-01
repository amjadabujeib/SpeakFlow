import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/network/api_client.dart';
import '../features/auth/data/auth_api.dart';
import '../features/chat/data/roleplay_api.dart';
import '../features/news/data/news_api.dart';
import '../features/learning_plan/data/learning_plan_api.dart';
import '../features/practice/data/language_tools_api.dart';
import '../features/practice/data/pronunciation_api.dart';

class AppDependencies {
  static final instance = AppDependencies();

  final ApiClient apiClient;
  late final AuthApi auth;
  late final RoleplayApi roleplay;
  late final LanguageToolsApi languageTools;
  late final NewsApi news;
  late final PronunciationApi pronunciation;
  late final LearningPlanApi learningPlan;

  AppDependencies({ApiClient? apiClient})
    : apiClient = apiClient ?? ApiClient() {
    auth = AuthApi(this.apiClient);
    roleplay = RoleplayApi(this.apiClient);
    languageTools = LanguageToolsApi(this.apiClient);
    news = NewsApi(this.apiClient);
    pronunciation = PronunciationApi(this.apiClient);
    learningPlan = LearningPlanApi(this.apiClient);
  }
}

final appDependenciesProvider = Provider<AppDependencies>(
  (ref) => AppDependencies.instance,
);
final authApiProvider = Provider<AuthApi>(
  (ref) => ref.watch(appDependenciesProvider).auth,
);
final roleplayApiProvider = Provider<RoleplayApi>(
  (ref) => ref.watch(appDependenciesProvider).roleplay,
);
final languageToolsApiProvider = Provider<LanguageToolsApi>(
  (ref) => ref.watch(appDependenciesProvider).languageTools,
);
final newsApiProvider = Provider<NewsApi>(
  (ref) => ref.watch(appDependenciesProvider).news,
);
final pronunciationApiProvider = Provider<PronunciationApi>(
  (ref) => ref.watch(appDependenciesProvider).pronunciation,
);
final learningPlanApiProvider = Provider<LearningPlanApi>(
  (ref) => ref.watch(appDependenciesProvider).learningPlan,
);
