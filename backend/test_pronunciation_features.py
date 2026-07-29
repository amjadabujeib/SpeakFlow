import unittest

import numpy as np

from pronunciation_features import (
    GOP_FEATURE_DIM,
    PHONE_CONTEXT_FEATURE_DIM,
    WORD_CONTEXT_FEATURE_DIM,
    build_phone_context_features,
    build_word_context_features,
)


class PronunciationFeatureTests(unittest.TestCase):
    def setUp(self):
        self.raw = (
            np.arange(5 * GOP_FEATURE_DIM, dtype=np.float32)
            .reshape(5, GOP_FEATURE_DIM)
            / 100.0
        )
        self.phone_ids = np.asarray([2, 22, 9, 0, 4], dtype=np.int64)
        self.phones = ("K", "AA1", "R", "W", "L")
        self.word_lengths = (3, 2)

    def test_phone_context_contract_is_finite_and_stable(self):
        features = build_phone_context_features(
            self.raw,
            self.phone_ids,
            self.phones,
            self.word_lengths,
            normalization_mean=3.203,
            normalization_std=4.045,
        )

        self.assertEqual(features.shape, (5, PHONE_CONTEXT_FEATURE_DIM))
        self.assertTrue(np.isfinite(features).all())

    def test_word_context_contract_covers_each_word(self):
        features = build_word_context_features(
            self.raw,
            self.phone_ids,
            self.phones,
            self.word_lengths,
            normalization_mean=3.203,
            normalization_std=4.045,
        )

        self.assertEqual(features.shape, (2, WORD_CONTEXT_FEATURE_DIM))
        self.assertTrue(np.isfinite(features).all())

    def test_word_boundaries_must_cover_all_phones(self):
        with self.assertRaises(ValueError):
            build_phone_context_features(
                self.raw,
                self.phone_ids,
                self.phones,
                (3, 1),
                normalization_mean=3.203,
                normalization_std=4.045,
            )

    def test_feature_wise_normalization_is_supported(self):
        features = build_phone_context_features(
            self.raw,
            self.phone_ids,
            self.phones,
            self.word_lengths,
            normalization_mean=np.zeros(GOP_FEATURE_DIM, dtype=np.float32),
            normalization_std=np.ones(GOP_FEATURE_DIM, dtype=np.float32),
        )

        np.testing.assert_allclose(features[:, :GOP_FEATURE_DIM], self.raw)

    def test_non_finite_gop_is_rejected(self):
        raw = self.raw.copy()
        raw[0, 0] = np.nan

        with self.assertRaises(ValueError):
            build_word_context_features(
                raw,
                self.phone_ids,
                self.phones,
                self.word_lengths,
                normalization_mean=3.203,
                normalization_std=4.045,
            )


if __name__ == "__main__":
    unittest.main()
