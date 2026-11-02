from typing import Any


def overs_to_balls(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    whole_overs = int(value)
    balls = round((value - whole_overs) * 10)
    if balls > 5:
        return None
    return whole_overs * 6 + balls


def balls_to_overs(balls: int | None) -> float | None:
    if balls is None or balls < 0:
        return None
    return int(balls // 6) + (balls % 6) / 10


def rate_from_balls(runs: int | float | None, balls: int | None) -> float | None:
    if runs is None or balls is None or balls <= 0:
        return None
    return runs / (balls / 6)
