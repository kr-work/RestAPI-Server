"""Match/game rules that are independent from HTTP and DB.

This module is organized by *concept* (rules), not by game mode.
Mode-specific rules can live together here to avoid scattering files.

Rule of thumb:
- OK: math, validation, coordinate generation, pure transformations.
- Not OK: touching DB sessions, Redis, FastAPI, datetime.now(), etc.
"""

# ==============================================================================
# ==== Common (shared across modes) ============================================
# ==============================================================================


# ==============================================================================
# ==== Standard only ===========================================================
# ==============================================================================


# ==============================================================================
# ==== Mixed doubles only ======================================================
# ==============================================================================
# ==== Positioned stones =======================================================
# NOTE: power play coordinates are defined for the RIGHT side; LEFT side flips x.

MD_POSITIONED_STONE_IN_HOUSE = (0.0, 38.870)
MD_POWER_PLAY_IN_HOUSE = (1.219, 38.260)

# Pattern index (0-5) matches positioned_stones_pattern.
MD_POSITIONED_STONE_GUARD = [
    (0.0, 35.350),
    (0.0, 35.060),
    (0.0, 34.435),
    (0.0, 34.145),
    (0.0, 33.520),
    (0.0, 33.230),
]

MD_POWER_PLAY_GUARD = [
    (1.093, 35.350),
    (1.087, 35.060),
    (1.073, 34.435),
    (1.067, 34.145),
    (1.053, 33.520),
    (1.047, 33.230),
]


def generate_mixed_doubles_initial_stones(
    hammer_team_name: str,
    power_play_side: str | None,
    positioned_stones_pattern: int,
) -> dict:
    """Generate initial pre-positioned stones for mixed doubles.

    We keep 8 stones per team for simulator compatibility; unused stones remain at (0, 0).

    Args:
        hammer_team_name: "team0" or "team1".
        power_play_side: None | "left" | "right".
        positioned_stones_pattern: 0..5.

    Returns:
        Stone coordinate dict compatible with StoneCoordinateSchema.data.
    """
    if positioned_stones_pattern < 0 or positioned_stones_pattern > 5:
        raise ValueError("positioned_stones_pattern must be between 0 and 5")

    x_sign = -1.0 if power_play_side == "left" else 1.0

    data = {
        "team0": [{"x": 0.0, "y": 0.0} for _ in range(8)],
        "team1": [{"x": 0.0, "y": 0.0} for _ in range(8)],
    }

    non_hammer_team_name = "team1" if hammer_team_name == "team0" else "team0"

    if power_play_side in ("left", "right"):
        house_x, house_y = MD_POWER_PLAY_IN_HOUSE
        guard_x, guard_y = MD_POWER_PLAY_GUARD[positioned_stones_pattern]
        house_x *= x_sign
        guard_x *= x_sign
    else:
        house_x, house_y = MD_POSITIONED_STONE_IN_HOUSE
        guard_x, guard_y = MD_POSITIONED_STONE_GUARD[positioned_stones_pattern]

    # Place one stone in the house for the non-hammer team,
    # and one guard stone for the hammer team.
    data[non_hammer_team_name][0] = {"x": float(house_x), "y": float(house_y)}
    data[hammer_team_name][0] = {"x": float(guard_x), "y": float(guard_y)}
    return data
