"""Greedy nearest neighbour among feasible, on-time next deliveries."""

# Data structures: lists for candidates and the route; a dictionary for distance lookups.

from .helpers import HUB, evaluate_route, waiting_ids


def dispatch(parcel, context):
    remaining = waiting_ids(parcel)
    route = []
    while remaining:
        origin = parcel[route[-1]]["delivery_location_id"] if route else HUB
        candidates = []
        for pid in remaining:
            result = evaluate_route(route + [pid], parcel, context)
            p = parcel[pid]
            if result is not None and p["delivery_window_start"] <= result[2][-1] <= p["delivery_window_end"]:
                candidates.append((context["travel_distance"][origin][p["delivery_location_id"]],
                                   p["delivery_window_end"], pid))
        if not candidates:
            break
        pid = min(candidates)[2]
        route.append(pid)
        remaining.remove(pid)
    return route
