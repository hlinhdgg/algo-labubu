"""Policy 2 (greedy 2): the classic TSP-style cheapest-insertion heuristic.

At each step, look at the waiting parcels, work out the single cheapest slot to slide
one into the route-in-progress, and place whichever parcel-and-slot combo costs the
least (fewest missed windows first, then least extra distance). Repeat until nothing
more fits. See solution/policies/helpers.py: build_cheapest_insertion_route for the
shared construction logic (including the top-K speed-up) used here and in
local_search.py, exhaustive_small.py and fleet_aware.py.

If the trip would leave nearly empty with nothing urgent on board, the truck waits
one planning round instead (helpers.worth_waiting).
"""

from typing import Dict, List

from simulator.models import Parcel, SimulationContext
from solution.policies.helpers import build_cheapest_insertion_route, worth_waiting


def dispatch(parcel: Dict[str, Parcel], context: SimulationContext) -> List[str]:
    """Build one trip with the cheapest-insertion greedy heuristic."""

    route = build_cheapest_insertion_route(parcel, context)
    if worth_waiting(route, parcel, context):
        return []
    return route
