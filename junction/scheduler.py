"""Choose the next road while keeping ties deterministic."""

from .config import HEAVY_QUEUE, ROADS, road_after


def _scan_order(cursor: str) -> list[str]:
    start = ROADS.index(cursor) if cursor in ROADS else 0
    return [ROADS[(start + offset) % len(ROADS)] for offset in range(len(ROADS))]


def choose_road(demand: dict[str, int], cursor: str) -> dict | None:
    order = _scan_order(cursor)
    heavy = [road for road in order if demand.get(road, 0) >= HEAVY_QUEUE]
    if heavy:
        maximum = max(demand[road] for road in heavy)
        road = next(road for road in heavy if demand[road] == maximum)
        return {"road": road, "reason": "heavy_traffic", "nextCursor": road_after(road)}
    road = next((road for road in order if demand.get(road, 0) > 0), None)
    if road is None:
        return None
    return {"road": road, "reason": "round_robin", "nextCursor": road_after(road)}
