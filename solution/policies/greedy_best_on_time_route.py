"""Greedy route scoring: prefer on-time deliveries, then route coverage."""

# Data structures: a set of remaining IDs and an ordered list for the route.

from .helpers import evaluate_route, waiting_ids


def dispatch(parcel, context):
    """Choose a feasible next stop that preserves the current on-time count."""
    remaining = set(waiting_ids(parcel))
    route = []
    current_on_time = 0
    while remaining:
        choices = []
        for pid in remaining:
            result = evaluate_route(route + [pid], parcel, context)
            if result is None or result[1] < current_on_time:
                continue
            choices.append((-result[1], -len(route) - 1, result[0], pid, result))
        if not choices:
            break
        _, _, _, pid, result = min(choices)
        route.append(pid)
        remaining.remove(pid)
        current_on_time = result[1]
    return route
