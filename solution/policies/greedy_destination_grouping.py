"""Dictionary-based destination grouping with greedy deadline ordering."""

# Data structure: a hash table (Python dictionary) mapping destinations to lists of parcel IDs.

from .helpers import HUB, evaluate_route, waiting_ids


def dispatch(parcel, context):
    groups = {}
    for pid in waiting_ids(parcel):
        groups.setdefault(parcel[pid]["delivery_location_id"], []).append(pid)
    for ids in groups.values():
        ids.sort(key=lambda pid: (parcel[pid]["delivery_window_end"],
                                  parcel[pid]["arrival_time"], pid))
    route = []
    while groups:
        origin = parcel[route[-1]]["delivery_location_id"] if route else HUB
        # Urgent group first; distance and location ID break ties.
        destination = min(groups, key=lambda loc: (
            parcel[groups[loc][0]]["delivery_window_end"],
            context["travel_distance"][origin][loc], loc))
        for pid in groups.pop(destination):
            if evaluate_route(route + [pid], parcel, context) is not None:
                route.append(pid)
    return route
