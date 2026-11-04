# solution/policies/queue_mosturgent.py
from solution.policies.yuhelpers import Queue, merge_sort_parcels

def dispatch(parcel, context):
    """
    Queue-based greedy dispatch policy (EDF) with capacity and range constraints.
    Treats delivery windows as soft constraints to maximize deliveries.
    """
    current_time = context["current_time"]
    departure_time = current_time + context["departure_delay"]
    capacity = context["capacity"]
    max_range = context["max_trip_distance_km"]
    travel_distance = context["travel_distance"]
    
    # 1. Filter available unassigned parcels
    available_parcels = []
    for pid, data in parcel.items():
        if data["vehicle_assigned"] is None and data["delivery_time"] is None:
            available_parcels.append((pid, data))

    if not available_parcels:
        return []

    # 2. Sort available parcels by delivery_window_end using Merge Sort (EDF)
    sorted_parcels = merge_sort_parcels(
        available_parcels, 
        key_func=lambda item: item[1]["delivery_window_end"]
    )

    # 3. Enqueue sorted parcels into Queue ADT
    parcel_queue = Queue()
    for item in sorted_parcels:
        parcel_queue.enqueue(item)

    # 4. Dequeue parcels while respecting capacity and 320km range limit
    selected_parcel_ids = []
    current_load = 0.0
    last_location = "HUB"
    current_trip_time = departure_time

    while not parcel_queue.is_empty():
        pid, data = parcel_queue.dequeue()
        parcel_size = float(data["size"])
        dest = data["delivery_location_id"]

        # Check capacity constraint (hard constraint: max 30)[cite: 1]
        if current_load + parcel_size > capacity:
            continue
            
        # Test adding this parcel to the route and calculate exact total distance (HUB -> route -> HUB)
        test_route_destinations = [
            parcel[p_id]["delivery_location_id"] for p_id in selected_parcel_ids
        ] + [dest]

        projected_distance = 0.0
        current_loc = "HUB"
        for next_loc in test_route_destinations:
            projected_distance += travel_distance.get(current_loc, {}).get(next_loc, 0.0)
            current_loc = next_loc
        projected_distance += travel_distance.get(current_loc, {}).get("HUB", 0.0)

        # Check range constraint (hard constraint: max 320 km)[cite: 1]
        if projected_distance > max_range:
            continue

        # Estimate travel time and update trip time for subsequent stops
        travel_time = travel_distance.get(last_location, {}).get(dest, 0.0)
        arrival_at_customer = current_trip_time + travel_time

        # Accept the parcel (Soft constraints: allow deliveries without strict rejection)
        selected_parcel_ids.append(pid)
        current_load += parcel_size
        last_location = dest
        current_trip_time = arrival_at_customer

    return selected_parcel_ids