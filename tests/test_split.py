import unittest

from division import split_purchase


class SplitTests(unittest.TestCase):
    def test_open_charges_only_drunk(self):
        self.assertEqual(split_purchase(1500, 24, {1: 6, 2: 6}), {1: 375, 2: 375})

    def test_closed_even_split(self):
        self.assertEqual(
            split_purchase(1500, 24, {1: 12, 2: 12}, 0), {1: 750, 2: 750})

    def test_unaccounted_bottles_split_evenly(self):
        shares = split_purchase(1500, 24, {1: 6, 2: 3, 3: 3}, 0)
        self.assertEqual(shares, {1: 625, 2: 438, 3: 438})  # 1c rounding

    def test_closed_share_never_below_open_share(self):
        consumed = {1: 1, 2: 1, 3: 1}
        open_shares = split_purchase(1001, 3, consumed)
        closed_shares = split_purchase(1001, 3, consumed, 0)
        for pid in consumed:
            self.assertGreaterEqual(closed_shares[pid], open_shares[pid])

    def test_missing_deposit_split_evenly(self):
        shares = split_purchase(1500, 24, {1: 6, 2: 3, 3: 3}, 50)
        self.assertEqual(shares, {1: 642, 2: 454, 3: 454})
        self.assertEqual(sum(shares.values()), 1550)

    def test_discount_crates_priced_separately(self):
        crate_a = split_purchase(1500, 24, {1: 3})
        crate_b = split_purchase(1300, 24, {1: 2})
        self.assertEqual(crate_a, {1: 188})
        self.assertEqual(crate_b, {1: 108})
        self.assertEqual(sum(crate_a.values()) + sum(crate_b.values()), 296)

    def test_closed_with_no_drinkers(self):
        self.assertEqual(split_purchase(1500, 24, {}, 0), {})

    def test_open_share_never_shrinks_when_others_drink(self):
        self.assertEqual(split_purchase(1001, 3, {2: 1}), {2: 334})
        self.assertEqual(split_purchase(1001, 3, {2: 1, 1: 1}), {2: 334, 1: 334})

    def test_over_consumption_rejected(self):
        with self.assertRaises(ValueError):
            split_purchase(1500, 24, {1: 25})


if __name__ == "__main__":
    unittest.main()
