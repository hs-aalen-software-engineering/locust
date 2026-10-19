from locust import User, constant, task
from locust.user.inspectuser import _calc_distribution, print_task_ratio, print_task_ratio_json

import io
import json
import unittest
from contextlib import redirect_stdout


def make_user(name, weight=1, fixed_count=0):
    """Build a throwaway User subclass with the given weight / fixed_count."""

    class _User(User):
        wait_time = constant(0)

        @task
        def noop(self):
            pass

    _User.__name__ = name
    _User.__qualname__ = name
    _User.weight = weight
    _User.fixed_count = fixed_count
    return _User


class TestCalcDistribution(unittest.TestCase):
    def test_equal_weights_split_evenly(self):
        a, b = make_user("A"), make_user("B")
        self.assertEqual({"A": 5, "B": 5}, _calc_distribution([a, b], 10))

    def test_mixed_weights_are_proportional(self):
        light, heavy = make_user("Light", weight=1), make_user("Heavy", weight=3)
        self.assertEqual({"Light": 2, "Heavy": 6}, _calc_distribution([light, heavy], 8))

    def test_rounding_can_make_sum_differ_from_num_users(self):
        # 10 / 3 = 3.33 -> rounds to 3 for every class; the total (9) is not 10.
        classes = [make_user("A"), make_user("B"), make_user("C")]
        result = _calc_distribution(classes, 10)
        self.assertEqual({"A": 3, "B": 3, "C": 3}, result)
        self.assertEqual(9, sum(result.values()))

    def test_rounding_uses_bankers_rounding(self):
        # Python's round() rounds .5 to the nearest even number: 2.5 -> 2 for both classes.
        a, b = make_user("A"), make_user("B")
        self.assertEqual({"A": 2, "B": 2}, _calc_distribution([a, b], 5))

    def test_fixed_count_is_subtracted_before_weighting(self):
        fixed, weighted = make_user("Fixed", fixed_count=2), make_user("Weighted", weight=5)
        self.assertEqual({"Fixed": 2, "Weighted": 8}, _calc_distribution([fixed, weighted], 10))

    def test_fixed_count_ignores_weight(self):
        # A fixed_count class must not contribute its weight to the weighted split.
        fixed = make_user("Fixed", weight=100, fixed_count=1)
        a, b = make_user("A", weight=1), make_user("B", weight=3)
        self.assertEqual({"Fixed": 1, "A": 1, "B": 3}, _calc_distribution([fixed, a, b], 5))

    def test_fixed_count_larger_than_num_users_clamps_weighted_to_zero(self):
        fixed, weighted = make_user("Fixed", fixed_count=5), make_user("Weighted")
        self.assertEqual({"Fixed": 5, "Weighted": 0}, _calc_distribution([fixed, weighted], 3))

    def test_no_num_users_defaults_to_total_weight(self):
        a, b = make_user("A", weight=2), make_user("B", weight=3)
        self.assertEqual({"A": 2, "B": 3}, _calc_distribution([a, b], 0))
        self.assertEqual({"A": 2, "B": 3}, _calc_distribution([a, b], None))

    def test_no_num_users_with_fixed_count_defaults_to_one(self):
        # num_users falls back to 1, which the fixed class already consumes.
        fixed, weighted = make_user("Fixed", fixed_count=2), make_user("Weighted", weight=4)
        self.assertEqual({"Fixed": 2, "Weighted": 0}, _calc_distribution([fixed, weighted], None))

    def test_only_fixed_count_classes(self):
        a, b = make_user("A", fixed_count=2), make_user("B", fixed_count=7)
        self.assertEqual({"A": 2, "B": 7}, _calc_distribution([a, b], 100))
        self.assertEqual({"A": 2, "B": 7}, _calc_distribution([a, b], None))


class TestPrintTaskRatio(unittest.TestCase):
    def test_print_task_ratio_json_uses_calculated_distribution(self):
        light, heavy = make_user("Light", weight=1), make_user("Heavy", weight=3)
        out = io.StringIO()
        with redirect_stdout(out):
            print_task_ratio_json([light, heavy], 8)
        data = json.loads(out.getvalue())

        self.assertEqual({"per_class", "total"}, set(data))
        self.assertAlmostEqual(0.25, data["total"]["Light"]["ratio"])
        self.assertAlmostEqual(0.75, data["total"]["Heavy"]["ratio"])
        # per_class task ratios are relative to the class, total ones are scaled by it.
        self.assertAlmostEqual(1.0, data["per_class"]["Heavy"]["tasks"]["noop"]["ratio"])
        self.assertAlmostEqual(0.75, data["total"]["Heavy"]["tasks"]["noop"]["ratio"])

    def test_print_task_ratio_prints_percentages(self):
        light, heavy = make_user("Light", weight=1), make_user("Heavy", weight=3)
        out = io.StringIO()
        with redirect_stdout(out):
            print_task_ratio([light, heavy], 8, True)
        lines = [line.split() for line in out.getvalue().splitlines()]

        self.assertEqual([["25.0", "Light"], ["25.0", "noop"], ["75.0", "Heavy"], ["75.0", "noop"]], lines)
