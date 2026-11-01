# IS115 Project README

Run commands from this directory using Python 3.9 or newer. All policies use only
the standard library. The simulator, input data, and supplied baseline are unchanged.

## Dispatch approaches

Each module exposes `dispatch(parcel, context)` and plans one vehicle's trip using
only the supplied snapshots. Hard constraints include the complete return journey.
No policy adds waiting at delivery stops (the simulator does not support it).

| Module under `solution.policies` | Algorithm and structure | Decision rule |
| --- | --- | --- |
| `baseline` | Supplied greedy FIFO, sorted list | Arrival order; ignores preferred windows. |
| `greedy_nearest_neighbour` | Greedy nearest neighbour, list and distance dictionary | Shortest next leg among hard-feasible deliveries inside their windows; deadline then ID break ties. |
| `greedy_destination_grouping` | Greedy grouping, dictionary of lists | Group by exact destination. Select earliest-deadline group; next-leg distance then destination ID break ties. Within groups, use deadline order. |
| `greedy_best_on_time_route` | Greedy route scoring, set and ordered list | Preserve the current on-time count, then favour on-time count, route coverage, and distance. |

`helpers.py` shares availability filtering and route calculations. All choices are
deterministic. Nonempty routes are dispatched immediately; empty routes defer to
the next planning round. All policies except `greedy_nearest_neighbour` may include early
or late deliveries, since windows are soft constraints.

The metric is `on_time_delivered / total_parcels * 100`, where `total_parcels`
includes every parcel in the selected day. Deliveries at either window endpoint
count as on time. Undelivered parcels count as not on time, preventing a policy from
improving its score by simply refusing difficult parcels. `total_delivered` remains
a useful secondary coverage measure.

## Run a policy and calculate metrics

Run the supplied baseline with:

```powershell
python -m simulator --policy solution.policies.baseline --data data --day day_001 --output results/baseline/day_001
python -m solution.performance_monitor --data data --day day_001 --log results/baseline/day_001/log.txt
```

```powershell
python -m simulator --policy solution.policies.greedy_nearest_neighbour --data data --day day_001 --output results/greedy_nearest_neighbour/day_001
python -m solution.performance_monitor --data data --day day_001 --log results/greedy_nearest_neighbour/day_001/log.txt
```

Replace `greedy_nearest_neighbour` with a module name above. To evaluate both selected
policies over all 20 days in PowerShell (existing results for those paths are replaced):

```powershell
$policies = @('greedy_nearest_neighbour', 'greedy_destination_grouping', 'greedy_best_on_time_route')
foreach ($policy in $policies) {
    foreach ($i in 1..20) {
        $day = 'day_{0:D3}' -f $i
        python -m simulator --policy "solution.policies.$policy" --data data --day $day --output "results/$policy/$day"
        if ($LASTEXITCODE -ne 0) { throw "Simulation failed: $policy / $day" }
        python -m solution.performance_monitor --data data --day $day --log "results/$policy/$day/log.txt"
        if ($LASTEXITCODE -ne 0) { throw "Metric calculation failed: $policy / $day" }
    }
}
```

## Checks

```powershell
python -m unittest discover -s tests -v
```

Checks cover input immutability, deterministic selection, capacity, directed return
distance, return deadline, delivery-window endpoints, and approach-specific choices.

## Implementation complexity

Let N be all arrived parcel records and n be the available parcels. These bounds
describe one dispatch call, not the whole simulator. Shared route evaluation scans
the route; routes can contain up to n parcels. Every policy also scans N records.

| Policy | Worst-case time | Additional space |
| --- | --- | --- |
| Nearest feasible | O(N + n³) | O(n) |
| Destination grouping | O(N + n²) | O(n) |
| Best on-time route | O(N + n³) | O(n) |

These conservative bounds reflect the current straightforward implementations,
including repeated route checks.
They do not assume a fixed maximum parcel count from the vehicle's size capacity.
