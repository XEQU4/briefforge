from typing import Any


def _filled(value: Any) -> bool:
    return value is not None and bool(str(value).strip())


def calculate_rating(task: Any) -> tuple[int, dict[str, int], list[str]]:
    pairs = [
        ("context+need", _filled(task.context) and _filled(task.need), 20, "context", "need"),
        ("data_materials", _filled(task.data_materials), 20, "data_materials"),
        ("expected_result", _filled(task.expected_result), 15, "expected_result"),
        ("success_criteria", _filled(task.success_criteria), 15, "success_criteria"),
        ("constraints", _filled(task.constraints), 10, "constraints"),
        ("users", _filled(task.users), 10, "users"),
        ("contact+interaction_format", _filled(task.contact) and _filled(task.interaction_format), 10, "contact", "interaction_format"),
    ]
    score = sum(points for _, ok, points, *_ in pairs if ok)
    breakdown: dict[str, int] = {label: points if ok else 0 for label, ok, points, *_ in pairs}
    missing: list[str] = []
    for _, ok, _, *fields in pairs:
        if not ok:
            missing.extend(field for field in fields if not _filled(getattr(task, field, None)))
    return score, breakdown, missing


def readiness_for_score(score: int) -> str:
    if score < 40:
        return "draft"
    if score < 70:
        return "working"
    if score < 90:
        return "ready"
    return "priority"
