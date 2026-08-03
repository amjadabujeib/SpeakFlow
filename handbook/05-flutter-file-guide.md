# Flutter file guide

This page covers every hand-written file under `frontend/lib`.

## App and core

- **`main.dart`** — Startup, release URL safety, state restoration, portrait lock,
  theme, router, and text scaling.

- **`app/providers.dart`** — Constructs focused API dependencies and exposes Riverpod
  providers.

- **`app/router.dart`** — Auth redirects, shell routes, full-screen routes, and typed
  route extras.

- **`core/auth/auth_session_store.dart`** — Restores/persists the bearer session and
  notifies routing on auth changes.

- **`core/network/api_config.dart`** — Compile-time origins, unversioned `/api` HTTP
  paths, and `/ws/chat`.

- **`core/network/api_client.dart`** — Authorized JSON HTTP transport, timeout/error
  handling, and session invalidation.

- **`core/providers/app_state.dart`** — Shared learner snapshot, font preference,
  generation tracking, and refresh notifications.

- **`core/data/practice_word_store.dart`** — User-namespaced device persistence for
  saved practice words.

- **`core/data/phoneme_progress_store.dart`** — User-namespaced measured phoneme history
  and JSON persistence.

- **`core/theme/app_colors.dart`** — Dark-interface color tokens only.

- **`core/theme/app_theme.dart`** — Dark Material theme, typography, inputs, buttons,
  cards, navigation, and dialogs.

- **`core/theme/local_fonts.dart`** — Local/fallback font resolution used instead of
  scattered font setup.

## Authentication feature

- **`features/auth/data/auth_api.dart`** — Signup, signin, guest, current-user, and
  signout HTTP adapter; updates session store.

- **`features/auth/application/auth_controller.dart`** — Async authentication workflow
  state consumed by the auth UI.

- **`features/auth/auth_gate.dart`** — Chooses signed-out authentication or the
  signed-in first-run gate.

- **`features/auth/auth_screen.dart`** — Login/signup/guest form presentation and
  validation feedback.

- **`features/auth/onboarding_screen.dart`** — Main account onboarding state and library
  for step parts.

- **`features/auth/onboarding_chrome.dart`** — Shared onboarding page frame, progress,
  actions, and choice components.

- **`features/auth/onboarding_language_step.dart`** — Native-language selection.

- **`features/auth/onboarding_cefr_step.dart`** — CEFR selection and explanatory UI.

- **`features/auth/onboarding_goal_step.dart`** — Primary learning-goal selection.

- **`features/auth/onboarding_interests_step.dart`** — Up-to-three-interest selection.

- **`features/auth/loading_screen.dart`** — Transitional plan-generation/loading
  experience.

The auth onboarding records the same profile dimensions used by PLP. The PLP
onboarding screen remains available for direct learning-data reset/re-entry.

## Shell and home

- **`features/shell/main_shell.dart`** — Top settings action, route-derived bottom
  navigation, active child, and plan refresh key.

- **`features/home/home_tab.dart`** — Embeds the active learning plan and links to
  grammar, pronunciation, and dictionary tools.

- **`features/home/dictionary_screen.dart`** — Full dictionary workflow, input
  validation, loading, result, and speech controls.

## Learning-plan data and domain

- **`features/learning_plan/data/learning_plan_api.dart`** — Focused unversioned
  learning-plan calls for dependency-provider consumers.

- **`features/learning_plan/data/plp_repository.dart`** — `PlpRepository`, HTTP
  implementation, generation polling, profile, attempts, and reset.

- **`features/learning_plan/domain/plp_models.dart`** — Public model library, immutable
  helpers, and exports of domain part files.

- **`features/learning_plan/domain/plp_model_validation.dart`** — Safe JSON readers,
  required fields, enum/status checks, and format exceptions.

- **`features/learning_plan/domain/plp_plan_models.dart`** — Plan, week, lesson summary,
  generation, and profile model parsing.

- **`features/learning_plan/domain/plp_lesson_models.dart`** — Lesson content, activity,
  choice, pronunciation, and attempt result models.

- **`features/learning_plan/domain/plp_progress_models.dart`** — Progress, streak,
  skills, mastery evidence, and adaptation models.

## Learning-plan presentation

- **`features/learning_plan/presentation/first_run_gate.dart`** — Loads profile/plan and
  chooses checking, onboarding, app, or retry UI.

- **`features/learning_plan/presentation/onboarding_screen.dart`** — Standalone PLP
  profile form and generation launch.

- **`features/learning_plan/presentation/learning_plan_screen.dart`** — Main plan
  library/state, repository lifecycle, polling, and lesson navigation.

- **`features/learning_plan/presentation/learning_plan_states.dart`** — Loading, empty,
  error, and no-plan widgets.

- **`features/learning_plan/presentation/learning_plan_generation.dart`** — Pending/rate-limited/failed
  generation status and retry widgets.

- **`features/learning_plan/presentation/learning_plan_header.dart`** — Plan identity,
  progress, streak, summary, and reset actions.

- **`features/learning_plan/presentation/learning_plan_weeks.dart`** — Week selection
  and weekly mission presentation.

- **`features/learning_plan/presentation/learning_plan_lessons.dart`** — Lesson
  list/cards, status, score, availability, and launch behavior.

## Lesson presentation

- **`features/learning_plan/presentation/lesson/lesson_screens.dart`** — Lesson library,
  imports, shared state, activity dispatch, and public lesson screen.

- **`features/learning_plan/presentation/lesson/lesson_controller.dart`** — Current
  activity, submitted answers, score/completion transitions, and repository calls.

- **`features/learning_plan/presentation/lesson/lesson_content_widgets.dart`** — Explanations,
  vocabulary/prototype content, stimuli, and lesson text.

- **`features/learning_plan/presentation/lesson/lesson_question_widgets.dart`** — Choice,
  fill-blank, listening, and checkpoint question interactions.

- **`features/learning_plan/presentation/lesson/lesson_pronunciation_page.dart`** — Pronunciation
  activity page state and backend result handling.

- **`features/learning_plan/presentation/lesson/lesson_pronunciation_widgets.dart`** — Target,
  recording, analysis, and score widgets for pronunciation.

- **`features/learning_plan/presentation/lesson/lesson_guided_speaking_page.dart`** — Open
  speaking recording/transcription activity.

- **`features/learning_plan/presentation/lesson/lesson_completion_widgets.dart`** — Activity
  progress, lesson completion, XP, score, and next actions.

- **`features/learning_plan/presentation/lesson/lesson_feedback_widgets.dart`** — Correct/incorrect
  explanations and structured attempt feedback.

- **`features/learning_plan/presentation/lesson/lesson_common_widgets.dart`** — Lesson-local
  layout, buttons, section headings, and reusable controls.

## Practice feature

- **`features/practice/data/language_tools_api.dart`** — Grammar, dictionary, TTS, and
  chat helper calls.

- **`features/practice/data/pronunciation_api.dart`** — Multipart
  pronunciation/guided-speaking calls and response decoding.

- **`features/practice/practice_tab.dart`** — Practice library/state and word/phoneme
  practice coordination.

- **`features/practice/practice_add_word.dart`** — Add-word dialog and validation.

- **`features/practice/practice_word_queue.dart`** — Queue state and practice-session
  controls.

- **`features/practice/practice_word_cards.dart`** — Saved-word cards, actions, and
  score summaries.

- **`features/practice/practice_phoneme_map.dart`** — Aggregate measured phoneme map and
  empty-state behavior.

- **`features/practice/practice_phoneme_grid.dart`** — Individual phoneme cells and
  visual score bands.

- **`features/practice/grammar_check_screen.dart`** — Grammar workflow library and async
  state.

- **`features/practice/grammar_input_widgets.dart`** — Input editor, examples, and
  submit controls.

- **`features/practice/grammar_result_widgets.dart`** — Corrected result, changes,
  explanations, and actions.

- **`features/practice/grammar_correction_card.dart`** — Focused before/after correction
  display.

- **`features/practice/pronunciation_screen.dart`** — Recording lifecycle, target input,
  API call, and result state.

- **`features/practice/pronunciation_input_widgets.dart`** — Target field, recorder,
  validation, and loading controls.

- **`features/practice/pronunciation_result_widgets.dart`** — Overall metrics, phone
  evidence, warnings, and coaching.

## Chat and roleplay data/models

- **`features/chat/data/roleplay_api.dart`** — Scenario/session/history REST calls and
  authenticated WebSocket URL.

- **`features/chat/roleplay_models.dart`** — Scenario, objective, session, transcript,
  and launch argument models.

- **`features/chat/roleplay_feedback_data.dart`** — Final category/evidence models and
  empty fallback.

- **`features/chat/roleplay_chat_message.dart`** — Text/audio chat message value with
  optional confidence/feedback.

- **`features/chat/roleplay_confidence_transcript.dart`** — Recognition-confidence
  representation and verification helpers.

## Chat and roleplay presentation

- **`features/chat/chat_tab.dart`** — Scenario catalog/history library and
  custom-scenario state.

- **`features/chat/chat_tab_widgets.dart`** — Scenario cards, section states, and
  chat-tab components.

- **`features/chat/chat_scenario_builder.dart`** — Custom scenario editor, generated
  draft review, and submission.

- **`features/chat/chat_scenario_fields.dart`** — Focused editable scenario fields and
  weighted criteria controls.

- **`features/chat/chat_screen.dart`** — Live roleplay library, socket/recording state,
  and screen scaffold.

- **`features/chat/chat_session_controller.dart`** — Session creation, socket lifecycle,
  inbound events, and finalization.

- **`features/chat/chat_interaction_controller.dart`** — Sending text/audio, recording
  transitions, and pending-turn behavior.

- **`features/chat/chat_input_widgets.dart`** — Composer, record/send controls, and
  connection state.

- **`features/chat/roleplay_chat_components.dart`** — Objective/progress headers and
  general chat components.

- **`features/chat/roleplay_message_bubbles.dart`** — Learner/assistant text and audio
  message rendering.

- **`features/chat/roleplay_grammar_feedback.dart`** — Trusted correction display
  attached to learner messages.

- **`features/chat/roleplay_language_help_sheet.dart`** — Arabic escape/help
  translations with register choices.

- **`features/chat/roleplay_history_screen.dart`** — Read-only stored transcript
  display.

- **`features/chat/roleplay_session_summary_screen.dart`** — Evidence-aware final
  feedback and provisional labels.

## News feature

- **`features/news/data/news_api.dart`** — Category/page news calls and image proxy
  URLs.

- **`features/news/news_tab.dart`** — News screen library, selected category, paging,
  refresh, and article state.

- **`features/news/news_models.dart`** — Parsed article/feed models.

- **`features/news/news_article_widgets.dart`** — Article list/detail, metadata, image,
  and text presentation.

- **`features/news/news_player_widgets.dart`** — TTS playback controls and player state
  widgets.

## Shared widgets

- **`shared/widgets/dictionary_popup.dart`** — Reusable in-context word lookup overlay.

- **`shared/widgets/settings_drawer.dart`** — Settings library/state, profile load/save,
  regeneration, reset, and signout.

- **`shared/widgets/settings_drawer_body.dart`** — Drawer sections and controls.

- **`shared/widgets/settings_drawer_components.dart`** — Drawer-local headings, tiles,
  dialogs, and compact components.

No light-theme implementation remains: the app intentionally exposes one dark
theme, and color/theme files contain only UI that can currently be reached.
