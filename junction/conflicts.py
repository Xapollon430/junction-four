"""Pure car collision rules used by the observer."""


def movements_conflict(left: dict, right: dict) -> str | None:
    if left.get("entityType") != "car" or right.get("entityType") != "car":
        return None
    if left.get("road") == right.get("road"):
        return None
    return "intersection_center"


def intervals_overlap(left: dict, right: dict) -> bool:
    return left["startedAt"] < right["endsAt"] and right["startedAt"] < left["endsAt"]
