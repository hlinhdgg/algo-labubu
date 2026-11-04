"""Run from the project directory: python -m unittest discover -s tests -v."""

import copy
import unittest

from solution.policies import (
    greedy_best_on_time_route,
    greedy_nearest_neighbour,
)
from solution.policies.helpers import evaluate_route

POLICIES = (
    greedy_nearest_neighbour,
    greedy_best_on_time_route,
)


def record(location, end=600.0, start=480.0, size=1.0):
    return dict(arrival_time=480.0, delivery_location_id=location,
                delivery_window_start=start, delivery_window_end=end, size=size,
                vehicle_assigned=None, delivery_time=None, trip_id=None)


def context():
    return dict(current_time=480.0, vehicle_id=1, capacity=30.0,
                departure_delay=30.0, return_cutoff=1080.0,
                max_trip_distance_km=320.0,
                travel_distance={
                    "HUB": {"HUB": 0.0, "A": 10.0, "B": 20.0},
                    "A": {"HUB": 11.0, "A": 0.0, "B": 12.0},
                    "B": {"HUB": 21.0, "A": 8.0, "B": 0.0}},
                fleet={1: {"available_at": 480.0, "max_trip_distance_km": 320.0}})


class PolicyTests(unittest.TestCase):
    def test_all_policies_produce_valid_routes_without_mutating_snapshots(self):
        parcels = {"a": record("A"), "b": record("B"), "c": record("A", size=29.0),
                   "assigned": record("A"), "delivered": record("B")}
        parcels["assigned"]["vehicle_assigned"] = 2
        parcels["delivered"].update(vehicle_assigned=2, delivery_time=480.0)
        ctx = context()
        original = copy.deepcopy((parcels, ctx))
        for policy in POLICIES:
            with self.subTest(policy=policy.__name__):
                route = policy.dispatch(parcels, ctx)
                self.assertTrue(route)
                self.assertEqual(len(route), len(set(route)))
                self.assertTrue(set(route) <= {"a", "b", "c"})
                # Check constraints independently of the shared route evaluator.
                locations = ["HUB"] + [parcels[p]["delivery_location_id"] for p in route] + ["HUB"]
                distance = sum(ctx["travel_distance"][a][b] for a, b in zip(locations, locations[1:]))
                self.assertLessEqual(sum(parcels[p]["size"] for p in route), ctx["capacity"])
                self.assertLessEqual(distance, ctx["max_trip_distance_km"])
                self.assertLessEqual(ctx["current_time"] + 30 + distance, ctx["return_cutoff"])
                self.assertEqual((parcels, ctx), original)
                self.assertEqual(route, policy.dispatch(dict(reversed(list(parcels.items()))), ctx))

    def test_empty_and_impossible_routes(self):
        for policy in POLICIES:
            with self.subTest(policy=policy.__name__):
                self.assertEqual(policy.dispatch({}, context()), [])
                self.assertEqual(policy.dispatch({"large": record("A", size=31)}, context()), [])
                ctx = context()
                ctx["max_trip_distance_km"] = 20  # A round trip is 21, not 20.
                self.assertEqual(policy.dispatch({"a": record("A")}, ctx), [])
                ctx = context()
                ctx["current_time"] = 1040  # Return would be 1091, after cutoff.
                self.assertEqual(policy.dispatch({"a": record("A")}, ctx), [])

    def test_window_endpoints_and_early_delivery(self):
        parcels = {"a": record("A", start=520, end=520)}
        self.assertEqual(evaluate_route(["a"], parcels, context())[1], 1)
        self.assertEqual(greedy_nearest_neighbour.dispatch(parcels, context()), ["a"])
        parcels["a"]["delivery_window_start"] = 521
        parcels["a"]["delivery_window_end"] = 600
        self.assertEqual(greedy_nearest_neighbour.dispatch(parcels, context()), [])

    def test_nearest_and_grouping(self):
        parcels = {"a1": record("A", end=540), "b": record("B", end=550),
                   "a2": record("A", end=600)}
        self.assertEqual(greedy_nearest_neighbour.dispatch(parcels, context()), ["a1", "a2", "b"])


if __name__ == "__main__":
    unittest.main()
