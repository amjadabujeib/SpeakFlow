import unittest

import numpy as np
import torch

from ctc_gop import (
    CTC_GOP_FEATURE_DIM,
    CTC_PHONE_TO_ID,
    alignment_free_ctc_gop,
)


class AlignmentFreeCtcGopTests(unittest.TestCase):
    def test_returns_one_41d_row_per_canonical_phone(self):
        torch.manual_seed(7)
        logits = torch.randn(12, 40)
        target = [CTC_PHONE_TO_ID["K"], CTC_PHONE_TO_ID["AA"], CTC_PHONE_TO_ID["R"]]

        result = alignment_free_ctc_gop(logits, target, counterfactual_batch_size=11)

        self.assertEqual(result.features.shape, (3, CTC_GOP_FEATURE_DIM))
        self.assertTrue(np.isfinite(result.features).all())
        self.assertEqual(len(result.likely_phones), 3)
        self.assertEqual(result.likely_phone_probabilities.shape, (3,))
        self.assertEqual(result.deletion_probabilities.shape, (3,))

    def test_canonical_replacement_has_zero_likelihood_ratio(self):
        torch.manual_seed(11)
        logits = torch.randn(10, 40)
        target = [CTC_PHONE_TO_ID["TH"], CTC_PHONE_TO_ID["IH"]]

        result = alignment_free_ctc_gop(logits, target)

        for row_index, phone_id in enumerate(target):
            # Column zero is LPP. Ratio columns are deletion at 1, then
            # replacement IDs 1..39 at columns 2..40.
            self.assertAlmostEqual(
                float(result.features[row_index, phone_id + 1]), 0.0, places=4
            )

    def test_rejects_blank_in_canonical_sequence(self):
        with self.assertRaisesRegex(ValueError, "unsupported phone"):
            alignment_free_ctc_gop(torch.randn(8, 40), [0, 2])


if __name__ == "__main__":
    unittest.main()
