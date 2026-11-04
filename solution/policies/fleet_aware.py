"""Policy 5 (improvement): cheapest insertion, deadline-first, coordinated with the fleet.

Parcels are split by slack (minutes to spare, see helpers.urgency_key): "tight" ones
have at most SLACK_THRESHOLD minutes, the rest are "relaxed". Relaxed parcels are only
added as filler where no stop on the trip misses its window, so they never push a
tight parcel late.

Each truck still plans alone, but context["fleet"] tells it when every other truck
will be back at the hub. That splits tight parcels in two:

- must-take: no busy truck will be back in time to deliver it on time, so if this
  truck skips it, it is lost;
- can-wait: a truck returning soon could still get it there in time.

The trip is built in three greedy steps with the same cheapest-insertion helper:
must-take parcels, then the other tight parcels, then relaxed parcels only where no
stop misses its window. The must-take cut-off comes from the fleet's live state, so
it needs no tuning.

A parcel is never put in a slot where the truck would reach it before its window
opens; it waits at the hub for a later trip instead (hold_early). This only helps
together with the waiting rule: without it, trucks were always busy and held parcels
ended up late instead (see README.md).

Filler may add at most FILLER_MAX_DETOUR km to the trip. Without this limit, relaxed
parcels that could easily wait turned morning trips into long tours, so trucks were
still out when later parcels needed them.

Like the other policies, the truck waits one planning round instead of leaving
nearly empty with nothing urgent on board (helpers.worth_waiting), and small trips
get the exact best stop order (helpers.best_stop_order).
"""

from typing import Dict, List

from simulator.models import Parcel, SimulationContext
from solution.policies.helpers import (
    available_parcel_ids,
    best_stop_order,
    build_cheapest_insertion_route,
    preferred_budget,
    urgency_key,
    worth_waiting,
)

# Trips with at most this many stops are re-ordered by trying every stop order
# (as in exhaustive_small.py).
MAX_EXHAUSTIVE_STOPS = 8

# A parcel is "tight" if it has at most this many minutes to spare. Re-tuned on days
# 1-10 after waiting, the early hold and exhaustive ordering were added: 180 and 210
# score best; 150 and below or 240 and above are worse (see README.md).
SLACK_THRESHOLD = 180.0

# A relaxed parcel may add at most this many km to the trip. Tuned on days 1-10: 15, 20,
# 25 and 30 score the same; 10 and below or 40 and above are worse (see README.md).
FILLER_MAX_DETOUR = 20.0


def _wait_for_next_truck(context: SimulationContext) -> float:
    """Minutes until the next busy truck could leave the hub, after this truck leaves.

    A parcel with less slack than this cannot wait for that truck. Uses each truck's
    return time plus the loading delay (it may leave up to one planning round later).
    Returns infinity when no other truck is out, i.e. nobody else is due back.
    """

    now = context["current_time"]
    delay = context["departure_delay"]
    next_departures = [
        vehicle["available_at"] + delay
        for vehicle_id, vehicle in context["fleet"].items()
        if vehicle_id != context["vehicle_id"] and vehicle["available_at"] > now
    ]
    if not next_departures:
        return float("inf")
    return min(next_departures) - (now + delay)


def dispatch(parcel: Dict[str, Parcel], context: SimulationContext) -> List[str]:
    """Build one trip: must-take parcels, then other tight ones, then safe filler."""

    gap = _wait_for_next_truck(context)
    must_take, tight, relaxed = [], [], []
    for parcel_id in available_parcel_ids(parcel):
        slack = urgency_key(parcel_id, parcel, context)
        if 0 <= slack < gap and slack <= SLACK_THRESHOLD:
            must_take.append(parcel_id)
        elif slack <= SLACK_THRESHOLD:
            tight.append(parcel_id)
        else:
            relaxed.append(parcel_id)

    route = build_cheapest_insertion_route(parcel, context, candidate_ids=must_take, hold_early=True)
    route = build_cheapest_insertion_route(
        parcel, context, candidate_ids=tight, start_route=route, hold_early=True
    )
    route = build_cheapest_insertion_route(
        parcel,
        context,
        candidate_ids=relaxed,
        start_route=route,
        max_new_violations=0,
        hold_early=True,
        max_detour=FILLER_MAX_DETOUR,
    )
    if worth_waiting(route, parcel, context):
        return []
    departure_time = context["current_time"] + context["departure_delay"]
    return best_stop_order(
        route, parcel, context["travel_distance"], departure_time, preferred_budget(context), MAX_EXHAUSTIVE_STOPS
    )
