# Final Policies Code Walkthrough

This document explains the final technical code in detail. The final policies are:

1. `greedy_nearest_neighbour.py`
2. `greedy_best_on_time_route.py`

Both policies use the shared functions in `solution/policies/helpers.py` and return an ordered list of parcel IDs for one vehicle.

## 1. Simulator interface

The simulator calls each policy as:

```python
route = dispatch(parcel, context)
```

`parcel` is a snapshot of parcels that have already arrived. Each parcel contains:

- `arrival_time`
- `delivery_location_id`
- `delivery_window_start`
- `delivery_window_end`
- `size`
- `vehicle_assigned`
- `delivery_time`

`context` contains:

- `current_time`
- `capacity`
- `travel_distance`
- `departure_delay`
- `return_cutoff`
- `max_trip_distance_km`

The policy must return only parcel IDs. It must not include `HUB` in the returned list. The simulator automatically treats the route as:

```text
HUB -> selected parcel destinations -> HUB
```

The route must obey three hard constraints:

1. Total parcel size must not exceed 30.
2. Total directed distance, including the return to `HUB`, must not exceed 320 km.
3. The vehicle must return by 18:00.

Delivery windows are soft constraints. A parcel may be delivered early or late, but that affects the performance metric.

## 2. Revised performance metric

The project uses:

```text
on-time delivery rate = on-time delivered parcels / total parcels received * 100
```

The denominator is every parcel in that day’s demand file. Therefore, an undelivered parcel contributes zero to the numerator. This avoids rewarding a policy simply for refusing difficult parcels.

For every day, `metrics.json` contains:

```json
{
  "total_parcels": 799,
  "total_delivered": 760,
  "on_time_delivered": 650,
  "on_time_delivery_rate_percent": 81.35
}
```

`total_delivered` is still reported as a secondary coverage measure.

## 3. Shared helper code

Both policies use the same helper module so that they apply the same route feasibility rules.

### Exact code

```python
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
```

### Line-by-line explanation

| Code | Explanation |
|---|---|
| `from math import fsum` | Imports accurate floating-point summation for route distances. |
| `HUB = "HUB"` | Stores the simulator’s hub location ID in one constant. |
| `def waiting_ids(parcel):` | Defines a reusable function for finding parcels that can still be assigned. |
| `parcel.items()` | Iterates through every parcel ID and record in the snapshot. |
| `p["vehicle_assigned"] is None` | Ensures the parcel has not already been assigned to a vehicle. |
| `p["delivery_time"] is None` | Ensures the parcel has not already been delivered. |
| `sorted(...)` | Makes the output deterministic. The same snapshot always produces the same order. |
| `def evaluate_route(...)` | Defines the common route checker and scoring function. |
| `len(route) != len(set(route))` | Detects duplicate parcel IDs. A route cannot deliver one parcel twice. |
| `pid not in parcel` | Rejects an unknown parcel ID. |
| `vehicle_assigned is not None` | Rejects a parcel already committed to another trip. |
| `delivery_time is not None` | Rejects a parcel already delivered. |
| `fsum(parcel[pid]["size"] ...)` | Adds every selected parcel’s size. |
| `> context["capacity"]` | Rejects a trip exceeding vehicle capacity. |
| `distances = context["travel_distance"]` | Reads the directed distance matrix from the simulator snapshot. |
| `departure = current_time + departure_delay` | Calculates when loading and charging finish. |
| `time = departure` | Starts the predicted clock at departure. |
| `location = HUB` | Starts the route at the hub. |
| `legs, arrivals = [], []` | Creates lists for distances and predicted delivery times. |
| `on_time = 0` | Starts the on-time delivery counter. |
| `for pid in route:` | Processes parcels in the exact delivery order proposed by the policy. |
| `destination = ...` | Gets the current parcel’s destination. |
| `leg = distances[location][destination]` | Looks up the directed distance from the current location. |
| `time += leg` | Adds travel time. The simulator uses one minute per kilometre. |
| `arrivals.append(time)` | Records the predicted arrival time for that parcel. |
| `start <= time <= end` | Counts the parcel as on time only inside the inclusive preferred window. |
| `location = destination` | Makes this destination the origin for the next leg. |
| `legs.append(distances[location][HUB])` | Adds the required return journey. |
| `distance = fsum(legs)` | Calculates complete trip distance. |
| `distance > max_trip_distance_km` | Rejects a trip beyond EV range. |
| `departure + distance > return_cutoff` | Rejects a trip returning after 18:00. |
| `return distance, on_time, arrivals` | Returns route distance, on-time count, and arrival times for policy scoring. |

The helper returns `None` whenever a route is infeasible. This lets both policies use the same validation logic without modifying simulator state.

## 4. Policy one greedy nearest neighbour

### Algorithm idea

Nearest neighbour makes one local choice at a time:

1. Find all waiting parcels.
2. Test every parcel as the next stop.
3. Remove parcels that would be infeasible or late.
4. Choose the candidate with the shortest next movement.
5. Repeat from the new route endpoint.

It is greedy because it does not enumerate every complete route. It chooses the best-looking next stop using current information.

### Data structures

- `remaining`: a list of candidate parcel IDs.
- `route`: an ordered list of selected parcel IDs.
- `candidates`: a list of score tuples.
- `travel_distance`: a nested dictionary for directed distance lookup.

### Exact code

```python
"""Greedy nearest neighbour among feasible, on-time next deliveries."""

# Data structures: lists for candidates and the route; a dictionary for distance lookups.

from .helpers import HUB, evaluate_route, waiting_ids


def dispatch(parcel, context):
    """Build an ordered route using the nearest feasible on-time next stop."""
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
```

### Line-by-line explanation

| Code | Explanation |
|---|---|
| `from .helpers ...` | Imports the hub constant, route checker, and waiting-parcel filter. |
| `def dispatch(parcel, context):` | Defines the interface required by the simulator. |
| `remaining = waiting_ids(parcel)` | Starts with all arrived, unassigned, undelivered parcels. |
| `route = []` | Creates the route in delivery order. |
| `while remaining:` | Keeps trying while there are possible parcels. |
| `origin = ... if route else HUB` | Uses HUB for the first stop; afterward uses the previous destination. |
| `candidates = []` | Stores feasible next-stop score tuples. |
| `for pid in remaining:` | Tests each currently available parcel. |
| `route + [pid]` | Creates a new proposed route without changing the existing route. |
| `result = evaluate_route(...)` | Checks capacity, range, return time, and calculates predicted arrival. |
| `p = parcel[pid]` | Reads the parcel’s destination and window. |
| `result is not None` | Keeps only hard-feasible routes. |
| `start <= result[2][-1] <= end` | Keeps only parcels predicted to arrive within their window. |
| `candidates.append(...)` | Stores a tuple whose priority is next-leg distance, then deadline, then ID. |
| `if not candidates:` | Stops if no remaining parcel can be delivered on time and feasibly. |
| `pid = min(candidates)[2]` | Python tuple ordering chooses the smallest score; the third value is the parcel ID. |
| `route.append(pid)` | Commits the chosen parcel to the route. |
| `remaining.remove(pid)` | Prevents selecting the same parcel again. |
| `return route` | Gives the simulator the ordered parcel IDs. |

### Why the policy works

The window check protects punctuality. The distance ranking avoids unnecessary detours. The deadline and parcel ID tie-breakers ensure deterministic output. Its limitation is that a locally short next stop may block a better combination later.

### Complexity

Let `N` be all arrived parcel records and `n` the waiting parcels. Filtering is `O(N)`. In the worst case, the loop makes `O(n)` rounds, scans `O(n)` candidates per round, and each route evaluation scans up to `O(n)` stops. The conservative bound is:

```text
Time:  O(N + n^3)
Space: O(n)
```

## 5 Policy two greedy best on-time route

### Algorithm idea

This policy looks at the result of adding each possible next parcel. It does not accept a candidate if the proposed route would reduce the current number of on-time deliveries. Among acceptable candidates, it prefers:

1. More on-time deliveries.
2. More selected stops.
3. Shorter complete route distance.
4. Smaller parcel ID as a deterministic tie-breaker.

This gives a balance between punctuality and coverage.

### Data structures

- `remaining`: a set, allowing efficient removal of selected IDs.
- `route`: an ordered list representing the trip.
- `choices`: a temporary list of route score tuples.
- `result`: the route evaluation tuple returned by the helper.

### Exact code

```python
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
```

### Line-by-line explanation

| Code | Explanation |
|---|---|
| `from .helpers ...` | Imports shared route scoring and waiting-parcel filtering. |
| `def dispatch(...)` | Defines the simulator’s required policy interface. |
| `remaining = set(waiting_ids(parcel))` | Stores candidates in a set so selected IDs can be removed. |
| `route = []` | Starts an empty delivery sequence. |
| `current_on_time = 0` | Records the best on-time count already protected by the route. |
| `while remaining:` | Repeats while parcels remain to be considered. |
| `choices = []` | Stores candidate score tuples for this planning step. |
| `for pid in remaining:` | Tests each remaining parcel as the next stop. |
| `evaluate_route(route + [pid], ...)` | Scores the complete proposed route, not just the next leg. |
| `result is None` | Rejects capacity, range, or return-time violations. |
| `result[1] < current_on_time` | Rejects a candidate that would reduce on-time deliveries. |
| `-result[1]` | Makes a larger on-time count sort first under `min()`. |
| `-len(route) - 1` | Makes a route containing more stops sort first after on-time count. |
| `result[0]` | Uses shorter complete distance as the next priority. |
| `pid` | Makes the tie-break deterministic. |
| `result` | Stores the already calculated route evaluation for reuse. |
| `if not choices:` | Stops when no candidate preserves punctuality. |
| `min(choices)` | Selects the lexicographically best score tuple. |
| `route.append(pid)` | Commits the chosen parcel. |
| `remaining.remove(pid)` | Prevents duplicate selection. |
| `current_on_time = result[1]` | Updates the protected on-time count. |
| `return route` | Returns the final ordered trip. |

### Why the policy works

Nearest neighbour chooses the shortest next leg after filtering. Best on-time route evaluates the resulting route score first. It can choose a farther parcel when doing so preserves or improves the route’s on-time count. Its secondary preference for more stops helps maintain delivery coverage.

### Complexity

The conservative bound is also:

```text
Time:  O(N + n^3)
Space: O(n)
```

It does more scoring work than nearest neighbour, but the vehicle capacity limits how many parcels can fit into one committed trip.

## 6 Metric implementation walkthrough

The important part of `solution/performance_monitor.py` is:

```python
windows = {
    parcel["parcel_id"]: (
        parse_time(parcel["delivery_window_start"]),
        parse_time(parcel["delivery_window_end"]),
    )
    for parcel in parcels
}
total_delivered = 0
on_time_delivered = 0
for event in events:
    if event["event_type"] != "delivery":
        continue
    window_start, window_end = windows[event["parcel_id"]]
    total_delivered += 1
    if window_start <= event["time"] <= window_end:
        on_time_delivered += 1
total_parcels = len(parcels)
rate = (on_time_delivered / total_parcels * 100) if total_parcels else 0.0
```

Line logic:

1. Build a dictionary from parcel ID to numeric window start and end.
2. Start counters at zero.
3. Ignore non-delivery events such as parcel arrivals and vehicle returns.
4. Match each delivery event to its parcel window.
5. Count every delivery in `total_delivered`.
6. Count only deliveries inside both inclusive bounds in `on_time_delivered`.
7. Set `total_parcels` to the number of rows in the demand file.
8. Divide by all received parcels, not only completed deliveries.

## 7 Final results

Across 20 days there are 15,867 received parcels:

| Policy | On-time rate | On-time deliveries | Total delivered | Coverage |
|---|---:|---:|---:|---:|
| Baseline | 27.41% | 4,349 | 6,421 | 40.47% |
| Greedy nearest neighbour | 82.95% | 13,162 | 13,162 | 82.95% |
| Greedy best on-time route | 79.78% | 12,658 | 15,194 | 95.76% |

Nearest neighbour has the highest on-time rate. Best on-time route is the strongest balanced recommendation because it delivers 15,194 parcels while maintaining a 79.78% rate.

## 8 Tests

Run:

```powershell
python -m unittest discover -s tests -v
```

The tests check:

- no duplicate parcel IDs;
- capacity, range, and return cutoff compliance;
- exclusion of assigned and delivered parcels;
- no mutation of input snapshots;
- deterministic output;
- inclusive delivery-window endpoints;
- empty and impossible routes.

## 9 Presentation questions

### Why are some parcels undelivered?

The brief allows undelivered parcels. Hard constraints and the 18:00 cutoff can make some parcels impossible or undesirable to include. The revised metric penalises this through the all-parcels denominator.

### Why is nearest neighbour a real algorithm rather than a trivial solution?

It is a greedy nearest-neighbour heuristic. At each step it searches current feasible candidates, applies route validation and the delivery window, then chooses the shortest next movement. It is not simply “deliver nothing.” It delivered 13,162 parcels in the experiment.

### Why does best on-time route have a lower rate but higher coverage?

It accepts additional feasible stops when they do not reduce the current on-time count. That produces many more completed deliveries, but some are late and therefore count only in coverage, not the on-time numerator.

### Can either policy see future arrivals?

No. Each call receives only the current snapshot of parcels that have already arrived. The policies do not read future demand files.

### What is the main limitation?

Both policies are local heuristics. They do not search every possible route, so they cannot guarantee a globally optimal solution.

## 10 Presentation order

1. Explain the simulator and constraints.
2. Define the revised metric.
3. Explain `waiting_ids` and `evaluate_route`.
4. Walk through nearest neighbour line by line.
5. Walk through best on-time route line by line.
6. Show the results table and explain rate versus coverage.
7. Present complexity and limitations.
8. Demonstrate the reproduction commands and tests.
