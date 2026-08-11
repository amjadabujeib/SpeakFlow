import 'dart:convert';
import 'dart:io';

import 'package:speakflow/features/learning_plan/data/plp_repository.dart';
import 'package:speakflow/features/learning_plan/domain/plp_models.dart';

const plpFixturePath = 'test/fixtures/plp_plan.json';

class TestFixtureBundle {
  const TestFixtureBundle();

  Future<String> loadString(String path) => File(path).readAsString();
}

const rootBundle = TestFixtureBundle();

class AssetPlpRepository extends PlpRepository {
  static const defaultAssetPath = plpFixturePath;
  final String assetPath;

  const AssetPlpRepository({this.assetPath = defaultAssetPath});

  @override
  Future<PlpDocument> loadPlan() async {
    final decoded = jsonDecode(await rootBundle.loadString(assetPath));
    if (decoded is! Map<String, dynamic>) {
      throw const PlpFormatException('document root must be a JSON object');
    }
    return PlpDocument.fromJson(decoded);
  }
}
