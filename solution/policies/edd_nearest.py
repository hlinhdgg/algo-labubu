"""Policy 1 (greedy 1 + 2-opt): earliest due date to choose parcels, nearest neighbour to order stops.

Choosing: every waiting parcel goes into a min-heap keyed by its slack -- how many
minutes are left before its window closes, counting the drive from the hub (an
earliest-due-date rule that allows for travel time). Parcels that can no longer be
on time (negative slack) go to the back of the heap, so they never take room from
parcels that can still make it. Parcels are popped one at a time and kept if the
truck still has room and the trip still fits the distance budget; otherwise skipped.

Ordering: the kept parcels are visited nearest-neighbour style -- from the hub, always
drive to the closest stop not visited yet (all parcels for one stop are dropped
together). The trip is re-ordered this way every time a parcel is kept, so the
budget check uses the real trip length.

If the trip would leave nearly empty with nothing urgent on board, the truck waits
one planning round instead (helpers.worth_waiting).

Finally, a 2-opt pass (helpers.two_opt_improve, as in local_search.py) reverses
segments of the nearest-neighbour route when that reduces service lost or
distance. Nearest neighbour only ever looks one stop ahead, so its routes often
cross themselves (see README.md for the measured gain).

A first version ranked by the raw window end and took late parcels first; it scored
about 20 points lower (see README.md).
"""

import heapq
from typing import Dict, List, Tuple

from simulator.models import Parcel, SimulationContext
from solution.policies.helpers import (
    HUB,
    available_parcel_ids,
    preferred_budget,
    route_distance,
    two_opt_improve,
    urgency_key,
    worth_waiting,
)

MAX_2OPT_PASSES = 3


def nearest_neighbour_order(
    parcel_ids: List[str], parcel: Dict[str, Parcel], distances: Dict[str, Dict[str, float]]
) -> List[str]:
    """Order parcels by visiting the closest unvisited stop next, starting at the hub."""

    by_location: Dict[str, List[str]] = {}
    for parcel_id in parcel_ids:
        by_location.setdefault(parcel[parcel_id]["delivery_location_id"], []).append(parcel_id)

    route: List[str] = []
    location = HUB
    while by_location:
        # Ties go to the smaller location ID so the result never depends on dict order.
        location = min(by_location, key=lambda stop: (distances[location][stop], stop))
        route.extend(by_location.pop(location))
    return route


def dispatch(parcel: Dict[str, Parcel], context: SimulationContext) -> List[str]:
    """Build one trip: least-slack parcels first, visited in nearest-neighbour order."""

    distances = context["travel_distance"]
    budget = preferred_budget(context)
    capacity = context["capacity"]

    heap: List[Tuple[Tuple[bool, float], str]] = []
    for parcel_id in available_parcel_ids(parcel):
        slack = urgency_key(parcel_id, parcel, context)
        heap.append(((slack < 0, slack), parcel_id))
    heapq.heapify(heap)

    chosen: List[str] = []
    route: List[str] = []
    load = 0.0
    while heap:
        _, parcel_id = heapq.heappop(heap)
        size = parcel[parcel_id]["size"]
        if load + size > capacity + 1e-9:
            continue
        trial = nearest_neighbour_order(chosen + [parcel_id], parcel, distances)
        if route_distance(trial, parcel, distances) > budget + 1e-9:
            continue
        chosen.append(parcel_id)
        route = trial
        load += size
    if worth_waiting(route, parcel, context):
        return []
    departure_time = context["current_time"] + context["departure_delay"]
    return two_opt_improve(route, parcel, distances, departure_time, budget, max_passes=MAX_2OPT_PASSES)
