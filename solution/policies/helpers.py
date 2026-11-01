"""Shared, read-only route calculations; all times are minutes after midnight."""

from math import fsum

HUB = "HUB"


def waiting_ids(parcel):
    """Return available IDs in deterministic order."""
    return sorted(pid for pid, p in parcel.items()
                  if p["vehicle_assigned"] is None and p["delivery_time"] is None)


def evaluate_route(route, parcel, context):
    """Return (distance, on-time count, arrival times), or None if infeasible.

    Includes the return leg and the preparation delay. No waiting at stops is
    modelled by the simulator, so an early arrival is not an on-time delivery.
    """
    if len(route) != len(set(route)):
        return None
    if any(pid not in parcel or parcel[pid]["vehicle_assigned"] is not None
           or parcel[pid]["delivery_time"] is not None for pid in route):
        return None
    if fsum(parcel[pid]["size"] for pid in route) > context["capacity"]:
        return None
    distances = context["travel_distance"]
    departure = context["current_time"] + context["departure_delay"]
    time = departure
    location = HUB
    legs, arrivals = [], []
    on_time = 0
    for pid in route:
        p = parcel[pid]
        destination = p["delivery_location_id"]
        leg = distances[location][destination]
        legs.append(leg)
        time += leg
        arrivals.append(time)
        on_time += p["delivery_window_start"] <= time <= p["delivery_window_end"]
        location = destination
    legs.append(distances[location][HUB])
    distance = fsum(legs)
    if (distance > context["max_trip_distance_km"]
            or departure + distance > context["return_cutoff"]):
        return None
    return distance, on_time, arrivals
