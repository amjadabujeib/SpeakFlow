import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import '../../support/test_app.dart';
import 'package:go_router/go_router.dart';
import 'package:speakflow/app/providers.dart';
import 'package:speakflow/core/providers/app_state.dart';
import 'package:speakflow/core/theme/app_colors.dart';
import 'package:speakflow/core/theme/app_theme.dart';
import 'package:speakflow/features/home/home_tab.dart';
import 'package:speakflow/features/learning_plan/data/plp_repository.dart';
import 'package:speakflow/features/learning_plan/domain/plp_models.dart';
import 'package:speakflow/features/learning_plan/presentation/first_run_gate.dart';
import 'package:speakflow/features/learning_plan/presentation/learning_plan_screen.dart';
import 'package:speakflow/features/learning_plan/presentation/lesson/lesson_screens.dart';
import 'package:speakflow/features/learning_plan/presentation/onboarding_screen.dart';
import '../../support/asset_plp_repository.dart';

part 'learning_plan_onboarding_test_part.dart';
part 'learning_plan_active_test_part.dart';
part 'learning_plan_retry_test_part.dart';

class _FixedRepository extends PlpRepository {
  final PlpDocument document;

  const _FixedRepository(this.document);

  @override
  Future<PlpDocument> loadPlan() async => document;
}

class _ResettableRepository extends _FixedRepository {
  bool resetCalled = false;

  _ResettableRepository(super.document);

  @override
  bool get isRemote => true;

  @override
  Future<void> resetLearner() async {
    resetCalled = true;
  }
}

class _ActiveGenerationRepository extends _FixedRepository {
  _ActiveGenerationRepository(super.document);

  @override
  bool get isRemote => true;

  @override
  Future<JsonMap> generationStatus(String jobId) async => {
    'job_id': jobId,
    'status': 'generating_week_one',
    'ready_weeks': 0,
    'total_weeks': 4,
    'completed_lessons': 0,
    'total_lessons': 20,
    'failed_lesson_ids': <String>[],
    'retry_after_seconds': 0,
  };
}

class _FutureGenerationRepository extends _FixedRepository {
  _FutureGenerationRepository(super.document);

  @override
  bool get isRemote => true;

  @override
  Future<JsonMap> generationStatus(String jobId) async => {
    'job_id': jobId,
    'status': 'generating_future_weeks',
    'ready_weeks': 1,
    'total_weeks': 4,
    'completed_lessons': 5,
    'total_lessons': 20,
    'failed_lesson_ids': <String>[],
    'retry_after_seconds': 0,
  };
}

class _OnboardingRepository extends PlpRepository {
  JsonMap? savedProfile;

  @override
  Future<PlpDocument> loadPlan() => throw const PlpApiException(404, 'No plan');

  @override
  Future<JsonMap> saveProfile(JsonMap profile) async {
    savedProfile = profile;
    return profile;
  }

  @override
  Future<String> generatePlan({bool regenerate = false}) async {
    if (regenerate) {
      throw StateError('Onboarding must not request regeneration.');
    }
    return 'job-from-onboarding';
  }

  @override
  Future<JsonMap> latestGeneration() =>
      throw const PlpApiException(404, 'No generation');
}

class _PendingRetryRepository extends _FixedRepository {
  int retryCalls = 0;
  final Completer<JsonMap> retryCompleter = Completer<JsonMap>();

  _PendingRetryRepository(super.document);

  @override
  bool get isRemote => true;

  @override
  Future<JsonMap> retryGeneration(String jobId) {
    retryCalls += 1;
    return retryCompleter.future;
  }
}

class _GenerationPollingRepository extends _FixedRepository {
  final bool finishImmediately;
  int loadCalls = 0;

  _GenerationPollingRepository(
    super.document, {
    required this.finishImmediately,
  });

  @override
  bool get isRemote => true;

  JsonMap get _queued => {
    'job_id': 'generation-job',
    'status': 'generating_week_one',
    'ready_weeks': 0,
    'total_weeks': 4,
    'completed_lessons': 0,
    'total_lessons': 20,
    'failed_lesson_ids': <String>[],
    'retry_after_seconds': 0,
  };

  @override
  Future<PlpDocument> loadPlan() async {
    loadCalls += 1;
    if (!finishImmediately || loadCalls == 1) {
      throw const PlpApiException(404, 'No active plan yet.');
    }
    return document;
  }

  @override
  Future<JsonMap> latestGeneration() async => _queued;

  @override
  Future<JsonMap> generationStatus(String jobId) async => finishImmediately
      ? {..._queued, 'status': 'idle', 'ready_weeks': 1, 'completed_lessons': 5}
      : _queued;
}

void main() {
  registerLearningPlanOnboardingTests();
  registerLearningPlanActiveTests();
  registerLearningPlanRetryTests();
}
