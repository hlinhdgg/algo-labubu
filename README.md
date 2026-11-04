# IS115 Project README

Last-mile delivery dispatch. Metric: **service rate** (`service_rate`) — the average service score over every parcel that arrived during the day:

- delivered inside its preferred window (boundaries included): **1**;
- delivered early or late: **1 − minutes outside the window ÷ window length**, and **0** once it is off by a whole window length or more;
- never delivered: **0**.

The delivery windows are soft, so a parcel 5 minutes late should not count the same as one 3 hours late; scaling by the window's own length means a 15-minute delay costs more for a 30-minute window than for a 3-hour one, without choosing a fixed cut-off. Undelivered parcels score 0, so the metric cannot be raised by skipping hard parcels. About 3.5% of parcels arrive too late in the day for any truck to reach them, so the best possible value is about 96.5%, not 100%.

`metrics.json` also reports the strict `on_time_rate` (on-time deliveries ÷ all parcels), `delivered_rate`, `on_time_rate_delivered` (on-time ÷ delivered), early and late counts and average lateness.

The service rate is the final metric. Earlier versions were on-time ÷ delivered parcels (guarded by `delivered_rate`) and then strict on-time ÷ all parcels. `fleet_aware` ranks first under all three; `greedy_insertion`, `local_search` and `exhaustive_small` are close enough to swap places (with the current trip cost, `exhaustive_small` leads on service rate and `local_search` narrowly leads on strict on-time). Tuning numbers quoted below say which version they use.

Requires Python 3.9+, standard library only. Run every command from the project root.

## Policies

| Module | Approach |
|---|---|
| `solution.policies.baseline` | Supplied FIFO first-fit (unchanged) |
| `solution.policies.edd_nearest` | Greedy 1: min-heap picks parcels by least slack (earliest due date allowing for travel), hopeless parcels last; stops visited nearest-neighbour, then a capped 2-opt pass |
| `solution.policies.greedy_insertion` | Greedy 2: TSP-style cheapest insertion; heap picks the top-50 most urgent candidates each step |
| `solution.policies.local_search` | Greedy insertion, then improve the stop order: exact (every order) for trips with at most 8 stops, a capped 2-opt pass for bigger trips |
| `solution.policies.exhaustive_small` | Best of the four core methods. Greedy insertion; trips with at most 8 stops are re-ordered by trying every stop order |
| `solution.policies.fleet_aware` | **Recommended** (highest service rate). Builds on the core methods: greedy insertion, tight-deadline parcels first; parcels no other truck can return in time for are loaded before anything else (uses `context["fleet"]`); never placed where they would arrive early; relaxed filler parcels may add at most 20 km to the trip; last-chance parcels go on first; nearly empty trucks wait late in the day if that costs nothing; small trips re-ordered exhaustively |

All policies except the baseline share one departure rule: if the trip would leave with less than 20 units on board (capacity 30) and every parcel on it has more than 60 minutes to spare, the truck waits for the next planning round instead (`helpers.worth_waiting`).

Shared code is in `solution/policies/helpers.py`. The metric is in `solution/performance_monitor.py`.

## Reproduce one run

```bash
python3 -m simulator --policy solution.policies.exhaustive_small \
    --data data --day day_001 \
    --output results/exhaustive_small/day_001

python3 -m solution.performance_monitor \
    --data data --day day_001 \
    --log results/exhaustive_small/day_001/log.txt
```

The log goes to `results/<policy>/<day>/log.txt` and the metrics to `metrics.json` beside it.

## Reproduce all results

```bash
for policy in baseline edd_nearest greedy_insertion local_search exhaustive_small fleet_aware; do
  for n in $(seq -w 1 20); do
    day="day_0$n"
    python3 -m simulator --policy solution.policies.$policy \
        --data data --day "$day" --output "results/$policy/$day"
    python3 -m solution.performance_monitor \
        --data data --day "$day" --log "results/$policy/$day/log.txt"
  done
done
```

The full sweep takes about five minutes. All policies are deterministic, so re-running gives identical logs.

## Results (mean over 20 days)

| Policy | Service rate | Std dev | Worst day | Days 1–10 | Validation days 11–20 | Strict on-time | Delivered rate | On-time ÷ delivered | Trips/day |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 27.41% | 1.61% | 24.75% | 27.23% | 27.58% | 27.41% | 40.47% | 67.73% | 21 |
| edd_nearest | 89.03% | 4.84% | 80.15% | 89.10% | 88.97% | 82.21% | 94.88% | 86.70% | 29 |
| greedy_insertion | 91.85% | 2.28% | 86.70% | 92.08% | 91.62% | 86.40% | 95.93% | 90.06% | 30 |
| local_search | 91.69% | 1.99% | 87.70% | 92.09% | 91.29% | 87.09% | 95.81% | 90.90% | 30 |
| exhaustive_small (best core method) | 91.95% | 2.28% | 88.11% | 92.23% | 91.67% | 86.95% | 95.73% | 90.82% | 30 |
| **fleet_aware** (recommended) | **95.99%** | 0.48% | 95.13% | 95.96% | 96.01% | 94.63% | 96.35% | 98.22% | 32 |
| *best possible (unlimited trucks)* | *96.46%* | | | | | *96.46%* | *96.46%* | *100.00%* | |

Service rate, std dev, worst day, days 1–10, validation and strict on-time are taken over daily values; delivered rate and on-time ÷ delivered are pooled over all parcels of the 20 days.

### Trip cost matches the metric

Every insertion-based step (cheapest insertion, the exhaustive stop order and 2-opt) compares trips by `helpers.route_cost` = (service lost, distance), where the service lost at a stop is min(1, minutes outside the window ÷ window length) — exactly what the service rate takes away. An earlier version counted missed windows instead, so a parcel 2 minutes late cost the same as one 3 hours late. Switching the cost (found by a separate search agent; no new constants) raised the service rate on both halves for every policy (days 1–10 / 11–20, before → after):

| Policy | Days 1–10 | Days 11–20 | Days better (1–10 / 11–20) | Validation worst day |
|---|---|---|---|---|
| edd_nearest | 87.4% → 89.1% | 87.6% → 89.0% | 10 / 10 | 81.0% → 83.6% |
| greedy_insertion | 90.7% → 92.1% | 89.5% → 91.6% | 10 / 8 | 84.2% → 87.9% |
| local_search | 91.1% → 92.1% | 89.4% → 91.3% | 8 / 9 | 83.8% → 87.7% |
| exhaustive_small | 91.0% → 92.2% | 90.6% → 91.7% | 9 / 8 | 84.7% → 88.1% |
| fleet_aware | 93.3% → 93.6% | 92.8% → 93.5% | 7 / 7 | 84.7% → 87.0% |

(These `fleet_aware` figures are before the filler limit below.) The gain for `fleet_aware` is small and on days 11–20 comes mostly from its two worst days (19 and 20); it is kept so every policy uses one cost. The trade-off: strict on-time falls by 0.3–2.8 points (e.g. `exhaustive_small` 89.2% → 86.4% on days 11–20), because the greedy now accepts several small near-misses instead of one large miss. That is right for the service rate but would be wrong if the metric went back to strict on-time, in which case this change should be re-tested. With the old cost, the service rate added only 1–5 points over strict on-time (most misses were about an hour outside their window); now it adds 2–7. The baseline does not move: when it is late it is very late (about 210 minutes on average).

The baseline delivers only 40.5% of parcels, so it scores 27.4%; measured only over the parcels it delivered it would look much better (67.7% on time). That gap is why the metric is taken over all parcels. The same trap catches an extreme waiting rule: a truck that leaves only when something is urgent (`WAIT_MIN_LOAD` above the capacity) delivers about 98% of its parcels on time but delivers only about 88% of parcels, so it scores lower overall and is rejected.

### Filler detour limit in `fleet_aware`

(Figures in this section are before the last-chance rule below.) `fleet_aware` adds relaxed parcels as filler once urgent ones are on board. A filler parcel may now add at most `FILLER_MAX_DETOUR = 20` km to the trip; before this, filler turned morning trips into long tours, so trucks were still out when later parcels needed them.

| `fleet_aware` | Days 1–10 | Days 11–20 |
|---|---|---|
| Service rate | 93.6% → 95.7% | 93.5% → 95.6% |
| Worst day | 90.7% → 95.0% | 87.0% → 94.3% |
| Strict on-time | 91.2% → 94.8% | 91.4% → 93.8% |
| Late parcels | 384 → 36 | 351 → 93 |
| Early parcels | 1 → 64 | 19 → 80 |
| Undelivered parcels | 319 → 316 | 305 → 318 |
| Days better / worse | 8 / 1 | 8 / 1 |

The two worst days show why (trips leaving before 11:00; before → after):

| Day | Mean trip length | Stops per trip | Trucks home at 13:00 | Late parcels |
|---|---|---|---|---|
| 20 | 170 → 79 min | 12.8 → 4.6 | 6 → 10 | 99 → 4 |
| 19 | 187 → 90 min | 13.2 → 6.4 | 6 → 9 | 98 → 1 |

So those days were largely caused by the policy's own long trips, not only by the fleet size. On days 11–20 the gain is uneven: days 19 and 20 gain +7.6 and +8.7 and the other eight average about +0.6. The limit does not help the core methods, which have no separate filler step: applied to all their parcels it also blocks urgent ones (20 km: 87.3–87.7%; 40 km: 89.0–90.0%, against 92.1–92.2% on days 1–10).

### Last-chance parcels and end-of-day waiting in `fleet_aware`

Trucks were waiting at the hub while parcels ran out of time. On day 1 at 16:00, trucks 6, 7 and 8 were all free. Cheapest insertion picked the nearest parcel, adding any of the three parcels on their last round would have broken the 90 km of time left, and `worth_waiting` looks only at parcels on the route, so all three trucks waited and those parcels were lost. Two rules were added:

- **Last chance first:** a parcel that is on time if sent now, but whose direct trip could not get back by the cut-off if it left one round later, goes on the trip before anything else.
- **End-of-day waiting:** in the last `ENDGAME_MINUTES = 150` before the cut-off, a truck with less than `WAIT_MIN_LOAD` units waits one round if the trip would still fit and every parcel on it would still be on time. This keeps it free for parcels that have not arrived yet.

| `fleet_aware` | Days 1–10 | Days 11–20 |
|---|---|---|
| Service rate | 95.69% → 95.96% | 95.58% → 96.01% |
| Worst day | 95.0% → 95.1% | 94.3% → 95.3% |
| Strict on-time | 94.8% → 95.1% | 93.8% → 94.2% |
| Late parcels | 36 → 35 | 93 → 93 |
| Early parcels | 64 → 64 | 80 → 80 |
| Undelivered parcels | 316 → 295 | 318 → 284 |
| Days better / worse | 10 / 0 | 8 / 0 |

Of the parcels that any truck could have reached on time, 73 were never delivered before these rules and 18 now. The last-chance rule gives most of the gain alone (95.79% and 95.89%); end-of-day waiting alone barely helps (95.71% on days 1–10), so it only pays together with the first rule.

### Effect of the waiting rule

Same policies without the waiting rule (and, for `edd_nearest`, its first version ranked by raw window end with late parcels first). This table was measured before the metric switch, so its on-time figures are on-time ÷ delivered:

| Policy | On-time, no waiting | Validation, no waiting | Delivered, no waiting | → On-time with waiting |
|---|---|---|---|---|
| edd_nearest (first version) | 56.0% | 56.6% | 78.3% | 79.4% (87.9% with 2-opt) |
| greedy_insertion | 83.4% | 83.3% | 95.2% | 91.6% |
| local_search (2-opt only) | 82.7% | 81.5% | 95.6% | 91.9% (92.1% with exact order for small trips) |
| exhaustive_small | 83.5% | 83.4% | 95.2% | 92.7% |
| fleet_aware (no exhaustive ordering, no early hold, tight ≤ 240) | 87.0% | 86.5% | 95.4% | 92.7% (94.3% with early hold, 95.5% with tight ≤ 180) |

Parcels arrive in bursts (most at 8h and 11h, then 15h). Without waiting, a truck leaves as soon as it is free, so the whole fleet leaves in the first hour (200 departures at 8–9h over 20 days, then only 2 in the 10h hour). No truck is free when the 9–10h parcels arrive: every one of the 683 parcels arriving at 9h missed its window with `greedy_insertion`. With waiting, departures are spread out and only 75 of them miss. Late deliveries fall from 15.8% to 6.2% of delivered parcels for `greedy_insertion`, and the delivered rate rises for every policy (for `edd_nearest`, most of its rise comes from its new ranking, which alone gives about 92% delivered).

- `edd_nearest` is still lowest: choosing parcels by deadline alone mixes stops from all over the map, so trips are long. Its first version (raw window end, late parcels first) took parcels that could no longer be on time ahead of ones that could. Nearest neighbour only looks one stop ahead, so its routes often cross themselves; adding a 2-opt pass raised it from 75.1% to 82.3% on days 1–10 and from 74.1% to 83.3% on days 11–20 (all-parcels metric). Under the earlier metric this was rejected because the delivered rate fell 0.3 points on days 1–10 (94.2% → 93.9%); the all-parcels metric counts that drop and still shows a large gain, so it was kept.
- `local_search` with 2-opt alone made each trip shorter, but changing the stop order changes when the truck gets back, which changes every later decision; without waiting it lost to `greedy_insertion` on 14 of 20 days. It now uses the exact order for trips with at most 8 stops and 2-opt only for bigger ones: +0.2 points on both halves (on-time ÷ delivered: 92.6% → 92.8% on days 1–10, 91.3% → 91.5% on days 11–20). It still scores below `exhaustive_small`, which leaves big trips in greedy order.
- `exhaustive_small` finds the best order for trips with at most 8 stops and is the best of the four core methods.
- `fleet_aware` scores highest. Re-tuning its "tight" cut-off for the current version (240 → 180 minutes) added 1.5 points on days 1–10 and 0.8 on days 11–20 (on-time ÷ delivered): 94.0% → 95.5% on days 1–10 and 94.6% → 95.4% on days 11–20, with early deliveries falling to 0.0%. Before waiting, its "never arrive early" step backfired (held parcels waited for a busy truck and arrived late); with trucks waiting at the hub there is a truck free for them, and early deliveries fall from 2.6% to 0.5% of delivered parcels. The same step did not help `exhaustive_small` on the validation days (92.8% → 92.5%), so it is only in `fleet_aware`. The early hold's gain (measured at the old cut-off of 240) is uneven: +1.6 points on both halves on average, but most of it comes from two days (day 7 +11.3, day 13 +10.1), it is worse on 6 of 20 days, the spread across days rises (std dev 3.5% → 4.2%) and the validation worst day falls (86.6% → 85.7%).
- `fleet_aware` is recommended: it has the highest service rate on both halves (95.96% on days 1–10, 96.01% on days 11–20) and uses only the same building blocks as the core methods (a heap, cheapest insertion, exhaustive ordering of small trips) plus the trucks' return times from `context["fleet"]`. Among the four core methods (greedy 1, greedy 2, local search, exhaustive search), `exhaustive_small` is best (92.0%, just ahead of `greedy_insertion` 91.8% and `local_search` 91.7%); `fleet_aware` adds 4.0 points through fleet coordination, holding parcels that would arrive early, limiting filler detours, and the last-chance and end-of-day rules.

About 3.5% of all parcels cannot be delivered on time by any policy: even sent out at the first chance, the truck reaches them after their window closes. Without waiting, 561 of the 722 parcels `fleet_aware` never delivered arrived too late for any truck to reach them and return by the cutoff.

## Tuning constants

Settings and ideas were tuned on days 1–10 and then checked on days 11–20. Days 11–20 are **validation days, not unseen test days**: many ideas were kept or rejected because of how they scored there (a distance limit of 0.8, for example, won on days 1–10 and was rejected only because of days 11–20). Their scores have therefore influenced the final policies and may be slightly optimistic; no untouched days remain. The metric changed during the project: `ROUTE_DISTANCE_BUDGET_FRACTION` was first tuned with strict on-time ÷ all parcels; the waiting rule and everything after it, including both re-tunes, used on-time ÷ delivered (with the delivered rate as a guard); then strict on-time ÷ all parcels again; the final metric is the service rate. The tuning figures below are on-time ÷ delivered unless stated. The settings were re-checked after each of the last two switches and after the trip cost changed (below).

After the final switch, the shared settings and three near-miss ideas were re-checked with the all-parcels metric on `exhaustive_small` and `fleet_aware` (days 1–10; current 88.8% and 91.8%). Waiting thresholds `WAIT_MIN_LOAD` 15/25 and `WAIT_SLACK` 30/120, `SLACK_THRESHOLD` 150/210/240, the real-arrival waiting check and shorter trips in a rush all scored the same or lower for at least one of the two. Only a shorter distance limit helped both (0.8: 89.4% and 92.0%; 0.85: 89.1% and 92.1%). 0.8 was chosen before checking days 11–20, where it lost: `exhaustive_small` 89.2% → 88.5%, `greedy_insertion` 87.7% → 87.0%, `edd_nearest` 83.3% → 78.4%, `fleet_aware` unchanged at 91.7% (0.85 also lowered `exhaustive_small`, to 88.9%). All current values were therefore kept.

After the switch to the service rate, the same settings were re-checked once more (days 1–10, service rate; current `exhaustive_small` 91.0%, `fleet_aware` 93.3%, `edd_nearest` 87.4%). `WAIT_MIN_LOAD` 15/25, `WAIT_SLACK` 30/120 and `SLACK_THRESHOLD` 150/210/240 scored the same or lower; removing `fleet_aware`'s early hold lowered it to 91.4% and removing `edd_nearest`'s 2-opt lowered it to 84.1%, so both stay. A distance limit of 0.8 again helped both on days 1–10 (91.5% and 93.5%) and again lost on days 11–20 (`exhaustive_small` 90.6% → 90.2%, `edd_nearest` 87.6% → 83.6%), the fourth time a shorter limit has looked better only on the tuning days. All current values were kept.

After the trip cost changed to service lost, the settings were re-checked again (days 1–10, service rate; current `exhaustive_small` 92.23%, `fleet_aware` 93.63%). `WAIT_MIN_LOAD` 15/25 and `WAIT_SLACK` 30/120 scored lower for both policies (between −0.05 and −0.57), and `SLACK_THRESHOLD` scored lower at 150 (93.33%) and 240 (93.49%) and gave identical logs at 210. Nothing beat the current values, so no check on days 11–20 was needed.

These were re-checked once more with the filler limit (days 1–10, service rate; current `fleet_aware` 95.69%). `SLACK_THRESHOLD` 150 gave +0.05, too small to matter, 210 gave −0.05 and 240 gave −2.12; `WAIT_MIN_LOAD` 15/25 and `WAIT_SLACK` 30/120 were all lower (−0.02 to −1.95). Adding 2-opt for trips over 8 stops gave −0.02, so it was not added. Current values were kept without another check on days 11–20.

In `solution/policies/helpers.py`:

- `ROUTE_DISTANCE_BUDGET_FRACTION = 0.9` — trips stop growing at 90% of the 320 km range. First chosen before the waiting rule on days 1, 5, 10, 15 and 20 (which wrongly included two validation days). Re-tuned with waiting on days 1–10 only: `greedy_insertion` scored 90.4% at 0.75, 92.2% at 0.8, 91.9% at 0.85, 91.7% at 0.9 and 91.6% at 1.0, with the same pattern for `exhaustive_small` and `fleet_aware`. But 0.8 was worse than 0.9 on the validation days for all three (e.g. `greedy_insertion` 90.6% vs 91.4%), so 0.9 was kept.
- `TOP_K = 50` — how many of the most urgent parcels are fully checked at each insertion step. If none of them fit, every waiting parcel is checked before the route is closed.
- `WAIT_MIN_LOAD = 20`, `WAIT_SLACK = 60` — the waiting rule. On `fleet_aware` over days 1–10 (the version before exhaustive ordering and the early hold were added): 87.6% with no waiting, 87.8% at 5 units, 89.9% at 10, 91.5% at 15, 92.3% at 20 and 25, 88.1% at 30. A slack of 30, 60 or 120 minutes changes the result by at most 0.5 points; 30 lowers the delivered rate. 20 was chosen over 25 because it is further from the drop at 30.

In `solution/policies/exhaustive_small.py`, `local_search.py` and `fleet_aware.py`:

- `MAX_EXHAUSTIVE_STOPS = 8` — 8! = 40,320 orders; 10 stops would be 3.6 million per trip.

In `solution/policies/fleet_aware.py`:

- `SLACK_THRESHOLD = 180` — a parcel is "tight" if it has at most 180 minutes to spare. First set to 240 before waiting, the early hold and exhaustive ordering existed (180, 240 and 300 scored about the same then). Re-tuned on the current version, days 1–10: 93.3% at 60, 93.5% at 90, 93.2% at 120, 95.1% at 150, 95.5% at 180 and 210, 94.0% at 240, 93.0% at 300. 180 was committed to before checking days 11–20 (95.4%, the same as 210). Waiting thresholds of 20 and 25 tie at 180; 15 is lower.
- `ENDGAME_MINUTES = 150` — how long before the cut-off the end-of-day waiting rule applies. With the last-chance rule, days 1–10, service rate: 95.79% with no end-of-day waiting, 95.80% at 90, 95.90% at 120, 95.96% at 150 and 180. 150 was committed to before checking days 11–20 (96.01%). On this data it means from 15:30.
- `FILLER_MAX_DETOUR = 20` — how many km one filler parcel may add to a trip. Days 1–10, service rate: 89.9% at 0, 94.3% at 5, 94.7% at 10, 95.7% at 15, 20, 25 and 30, 95.0% at 40, 94.3% at 60, 93.6% with no limit. 20 was committed to before checking days 11–20 (95.6%), because it sits well inside the flat range. Why 15–30 give identical scores is not fully explained.

## Ideas tried and dropped

These were tested on days 1–10 and are not in `solution/`, except where noted. Each says which metric it was measured with ("on-time ÷ delivered" is the version used before the final switch):

- **Never arrive early** (skip slots that reach a stop before its window opens). Before the waiting rule it failed for every policy: early deliveries fell to 0%, but late ones rose from 10.3% to 19.6% of parcels, because held parcels waited for a busy truck. With waiting (on-time ÷ delivered) it was dropped for `exhaustive_small` (92.5% → 92.7% on days 1–10, 92.8% → 92.5% on days 11–20) and `greedy_insertion` (91.7% → 91.1% on days 1–10), but kept for `fleet_aware` (see above).
- **Booking parcels onto returning trucks by capacity** (all-parcels metric): about 5 points below `fleet_aware`. Forcing a large group of parcels onto a trip first breaks up the compact routes that cheapest insertion builds.
- **2-opt that only keeps reversals saving a missed window** (no distance-only changes): 83.8% vs 84.0% on days 1–10 without waiting (on-time ÷ delivered), so it was rejected, although it scored higher on days 11–20 (83.3% vs 81.5%).
- **Shorter trips during a rush** (cap trips at 60% or 75% of the range when 100–250+ parcels are waiting at the hub; on-time ÷ delivered, with waiting): every setting was within ±0.4 points of no cap on days 1–10. The best for `fleet_aware` (250+ parcels, 60%) gave +0.2 on days 1–10 and +0.4 on days 11–20, and exactly 0 for `greedy_insertion`. Dropped: the gain is the size of the noise between settings, it was the best of 8 tried, the validation gain comes from a single day (day 16, 93.0% → 97.9%; the other nine days are identical), and it adds two constants.
- **Never wait when a big pile is waiting** (on-time ÷ delivered, with waiting): no change for `greedy_insertion` or `exhaustive_small` (when the pile is big their trips are already full), and 0.7–3.0 points worse for `fleet_aware`.
- **Waiting check using real arrival times on the trip** instead of the direct-drive slack (on-time ÷ delivered): +0.0 to +0.2 points on days 1–10 and +0.0 on days 11–20; with a 30-minute margin the delivered rate drops.
- **Shorter trips late in the day** (cap trip length after 13:00–16:00): best setting 87.8% vs 87.6% for `fleet_aware` on days 1–10 (on-time ÷ delivered), but 86.4% vs 86.5% on days 11–20. Short trips cannot reach far stops, and most undelivered parcels are unreachable anyway.
- **Reserve truck in the morning** (until 12:00, the last free truck does not leave unless a parcel on its trip has 60 minutes or less to spare; aimed at the worst days 8, 19 and 20, when ~65 parcels for 6 stops arrive at once with ~85-minute windows; on-time ÷ delivered). Days 1–10: `exhaustive_small` 92.5% → 93.6%, `greedy_insertion` 91.7% → 93.0%, `local_search` 92.8% → 93.1%, but `fleet_aware` 95.5% → 94.4%; cut-offs of 11:00 and 11:30 were worse than none. Days 11–20: `exhaustive_small` 92.8% → 92.6%, `fleet_aware` 95.4% → 94.5% (worst day 86.9% → 81.8%), and the delivered rate fell for the three core policies. Rejected: it did not help the worst days, because when the wave arrives two trucks are usually home already and the wave needs about three truckloads; one held truck does not close that gap. (A later trace showed the larger cause on those days was long morning trips; see "Filler detour limit in `fleet_aware`".)
- **No new misses** (cheapest insertion only accepts insertions that add no missed window; parcels that can no longer be on time are then added as filler, so they are still delivered; found by a separate search agent). With strict on-time ÷ all parcels it helped every insertion policy (e.g. `greedy_insertion` 88.0% → 90.0% on days 1–10, 87.7% → 89.1% on days 11–20). With the service rate, where a near-miss earns partial credit, it no longer helps them on days 1–10 (`greedy_insertion` 90.7% → 90.7%, `local_search` 91.1% → 91.0%, `exhaustive_small` 91.0% → 90.7%) and hurts `fleet_aware`. For `edd_nearest` without 2-opt it passed narrowly (87.4% → 88.0% on days 1–10, 87.6% → 88.0% on days 11–20), but it was worse on 6 of the 10 tuning days with daily changes of −6 to +12 points, so the gain is smaller than the day-to-day noise and `edd_nearest` keeps 2-opt instead.
- **Small follow-ups to the service cost** (service rate; found by the same search agent): ranking parcels already a whole window length late last in the top-50 shortlist (within ±0.15 for every policy on days 1–10); ordering `edd_nearest`'s hopeless parcels by remaining credit (+0.14 on days 1–10, 2 days better, 1 worse); letting `fleet_aware`'s must-take list include late parcels that can still earn credit (93.6% → 93.9% on days 1–10, mostly day 8, but 93.5% → 93.4% on days 11–20). None kept.
- **`fleet_aware`'s filler rule using service lost** instead of counting missed windows (a filler parcel may add at most 0, 0.1, 0.25 or 0.5 service lost; service rate, days 1–10): logs identical to the current rule on all 10 days at every setting. The cost already picks parcels that add no service lost first, so the limit never changes a decision. Not kept, as it would add code with no effect.
- **Allowing slightly early arrivals in `fleet_aware`** (5, 15 or 30 minutes before the window; service rate, days 1–10, before the filler limit): 93.5%, 93.1% and 93.0% vs 93.6%. **Shortlist of 100 instead of 50**: no gain in the mean (93.6%). Not kept.
- **Trimming long trips in the morning** (before 11:00 or 12:00, drop parcels with more than 180 or 240 minutes to spare from a trip longer than 90, 120 or 150 km; on-time ÷ delivered; aimed at days 19 and 20, where a truck left on a long trip with non-urgent parcels just before an urgent wave). Every setting was worse on days 1–10: `fleet_aware` 95.5% → 64.0–94.6%, `exhaustive_small` 92.5% → 74.6–91.1%, and the delivered rate fell. The rule also cut the full 8:00 trips, so parcels they would have delivered on time piled up for later. Rejected without a validation run. The filler detour limit later achieved what this aimed at: it stops long detours while the trip is being built, instead of removing parcels afterwards.
- **Only stopping the truck from waiting when a last-chance parcel exists** (`worth_waiting` looks at every waiting parcel, not just those on the route; days 1–10): 95.69% → 95.63%. The truck leaves, but the last-chance parcels are still not on it. The fix has to put them on the trip.
- **Stopping `best_stop_order` from creating early arrivals** (days 1–10): early parcels 64 → 0, but late parcels 36 → 111 and the service rate 95.69% → 95.62% (95.96% → 95.89% with the last-chance and end-of-day rules). Arriving a few minutes early costs little under the service rate, so these re-orders are kept. Under a metric that punishes early arrivals more, this should be re-tested.
