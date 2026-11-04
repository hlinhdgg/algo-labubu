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

A parcel on its last chance goes on the trip before anything else: this is the last
round a truck could take it out and be back by the cut-off, and it would still be on
time. Without this rule, trucks could wait at the hub with a small trip while such
parcels ran out of time, because adding one broke the distance budget.

Like the other policies, the truck waits one planning round instead of leaving
nearly empty with nothing urgent on board (helpers.worth_waiting). Late in the day it
also waits if everything on board would still be on time one round later, so a truck
stays free for parcels that have not arrived yet. Small trips get the exact best stop
order (helpers.best_stop_order).
"""

from typing import Dict, List

from simulator.models import Parcel, SimulationContext
from solution.policies.helpers import (
    HUB,
    WAIT_MIN_LOAD,
    available_parcel_ids,
    best_stop_order,
    build_cheapest_insertion_route,
    preferred_budget,
    route_arrival_times,
    route_distance,
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

# In the last ENDGAME_MINUTES before the cut-off, a nearly empty truck waits if waiting
# costs nothing. Tuned on days 1-10: 150 and 180 score the same; 90 and 120 are lower
# (see README.md).
ENDGAME_MINUTES = 150.0

# Minutes between planning rounds (fixed by the brief; not passed in context).
PLANNING_ROUND = 10.0


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


def _last_chance_parcels(parcel: Dict[str, Parcel], context: SimulationContext) -> List[str]:
    """Waiting parcels that are on time if sent now but cannot be sent next round.

    "Cannot" means a direct trip leaving one round later would be back after the cut-off.
    """

    distances = context["travel_distance"]
    cutoff = context["return_cutoff"]
    departure = context["current_time"] + context["departure_delay"]
    last_chance = []
    for parcel_id in available_parcel_ids(parcel):
        stop = parcel[parcel_id]["delivery_location_id"]
        trip = distances[HUB][stop] + distances[stop][HUB]
        arrival = departure + distances[HUB][stop]
        if (
            departure + trip <= cutoff < departure + PLANNING_ROUND + trip
            and parcel[parcel_id]["delivery_window_start"] <= arrival <= parcel[parcel_id]["delivery_window_end"]
        ):
            last_chance.append(parcel_id)
    return last_chance


def _endgame_wait(route: List[str], parcel: Dict[str, Parcel], context: SimulationContext) -> bool:
    """True if, late in the day, a nearly empty truck loses nothing by leaving one round later."""

    if not route or context["return_cutoff"] - context["current_time"] > ENDGAME_MINUTES:
        return False
    if sum(parcel[parcel_id]["size"] for parcel_id in route) >= WAIT_MIN_LOAD:
        return False
    distances = context["travel_distance"]
    later = context["current_time"] + context["departure_delay"] + PLANNING_ROUND
    if later + route_distance(route, parcel, distances) > context["return_cutoff"]:
        return False
    arrivals = route_arrival_times(route, parcel, distances, later)
    return all(
        parcel[parcel_id]["delivery_window_start"] <= arrival <= parcel[parcel_id]["delivery_window_end"]
        for parcel_id, arrival in zip(route, arrivals)
    )


def dispatch(parcel: Dict[str, Parcel], context: SimulationContext) -> List[str]:
    """Build one trip: last-chance parcels, must-take, other tight ones, then safe filler."""

    route = build_cheapest_insertion_route(
        parcel, context, candidate_ids=_last_chance_parcels(parcel, context), hold_early=True
    )

    gap = _wait_for_next_truck(context)
    must_take, tight, relaxed = [], [], []
    for parcel_id in available_parcel_ids(parcel):
        if parcel_id in route:
            continue
        slack = urgency_key(parcel_id, parcel, context)
        if 0 <= slack < gap and slack <= SLACK_THRESHOLD:
            must_take.append(parcel_id)
        elif slack <= SLACK_THRESHOLD:
            tight.append(parcel_id)
        else:
            relaxed.append(parcel_id)

    route = build_cheapest_insertion_route(
        parcel, context, candidate_ids=must_take, start_route=route, hold_early=True
    )
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
    if worth_waiting(route, parcel, context) or _endgame_wait(route, parcel, context):
        return []
    departure_time = context["current_time"] + context["departure_delay"]
    return best_stop_order(
        route, parcel, context["travel_distance"], departure_time, preferred_budget(context), MAX_EXHAUSTIVE_STOPS
    )
