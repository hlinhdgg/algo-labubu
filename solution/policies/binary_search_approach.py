# solution/policies/binary_search_approach.py
from solution.policies.yuhelpers import merge_sort_parcels, binary_search_first_active_index

def dispatch(parcel, context):
    """
    Binary Search Window-Filtering Policy:
    1. Filters unassigned parcels.
    2. Sorts them by delivery_window_end using MergeSort.
    3. Uses Binary Search to instantly locate relevant parcels for the current time.
    4. Greedily packs parcels into the vehicle respecting capacity and range constraints.
    """
    current_time = context["current_time"]
    departure_time = current_time + context["departure_delay"]
    capacity = context["capacity"]
    max_range = context["max_trip_distance_km"]
    travel_distance = context["travel_distance"]

    # 1. Filter available unassigned parcels
    available = []
    for pid, data in parcel.items():
        if data["vehicle_assigned"] is None and data["delivery_time"] is None:
            available.append((pid, data))

    if not available:
        return []

    # 2. Sort available parcels by delivery_window_end using MergeSort (EDF)
    sorted_parcels = merge_sort_parcels(
        available, 
        key_func=lambda item: item[1]["delivery_window_end"]
    )

    # 3. Use Binary Search to filter out parcels whose windows have already completely expired
    start_idx = binary_search_first_active_index(sorted_parcels, current_time)
    active_parcels = sorted_parcels[start_idx:]

    if not active_parcels:
        return []

    # 4. Greedily select parcels that fit capacity and range constraints
    selected_parcel_ids = []
    current_load = 0.0
    last_location = "HUB"
    current_trip_time = departure_time

    for pid, data in active_parcels:
        parcel_size = float(data["size"])
        dest = data["delivery_location_id"]
        
        # Check capacity constraint (hard constraint: max 30)[cite: 1]
        if current_load + parcel_size > capacity:
            continue
            
        # Test adding this parcel to the route and calculate total distance (HUB -> route -> HUB)
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

        # Estimate travel time to destination
        travel_time = travel_distance.get(last_location, {}).get(dest, 0.0)
        arrival_at_customer = current_trip_time + travel_time

        # Accept the parcel (Soft constraints: allow deliveries without strict rejections)
        selected_parcel_ids.append(pid)
        current_load += parcel_size
        last_location = dest
        current_trip_time = arrival_at_customer

    return selected_parcel_ids