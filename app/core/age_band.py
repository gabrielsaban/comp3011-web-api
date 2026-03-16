from __future__ import annotations

AGE_BANDS: tuple[tuple[int, int, str], ...] = (
    (0, 5, "0-5"),
    (6, 10, "6-10"),
    (11, 15, "11-15"),
    (16, 20, "16-20"),
    (21, 25, "21-25"),
    (26, 35, "26-35"),
    (36, 45, "36-45"),
    (46, 55, "46-55"),
    (56, 65, "56-65"),
    (66, 75, "66-75"),
)


def derive_age_band(age: int | None) -> str | None:
    if age is None or age < 0:
        return None
    for lower, upper, label in AGE_BANDS:
        if lower <= age <= upper:
            return label
    return "76+"
