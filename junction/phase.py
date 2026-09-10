"""Derive a signal state from a committed phase and the current time."""


def phase_stage(phase: dict | None, now_ms: int) -> dict:
    if not phase:
        return {"stage": "all_red", "light": "red", "allRedPhaseId": "startup"}
    elapsed = now_ms - phase["startAt"]
    if elapsed < 0:
        return {"stage": "all_red", "light": "red", "allRedPhaseId": phase["previousPhaseId"]}
    if elapsed < phase["greenMs"]:
        return {"stage": "green", "light": "green", "allRedPhaseId": None}
    if elapsed < phase["greenMs"] + phase["yellowMs"]:
        return {"stage": "yellow", "light": "yellow", "allRedPhaseId": None}
    return {"stage": "all_red", "light": "red", "allRedPhaseId": phase["phaseId"]}


def phase_ready_at(phase: dict | None) -> int:
    if not phase:
        return 0
    return phase["startAt"] + phase["greenMs"] + phase["yellowMs"] + phase["allRedMs"]
