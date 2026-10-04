"""Free check (no model, no sandbox): the dateutil #1236 patch rejects a week when the resulting date's calendar year
differs from the ISO year. ISO week 1 can start in the previous December and week 53 can end in the next January, so
this also rejects valid dates. This replicates the patched _calculate_weekdate. Run: python -m feasibility.dateutil_1236_probe"""
from datetime import date, timedelta


def patched(year, week, day):
    if not 0 < week < 54:
        raise ValueError("Invalid week")
    if not 0 < day < 8:
        raise ValueError("Invalid weekday")
    jan_4 = date(year, 1, 4)
    week_1 = jan_4 - timedelta(days=jan_4.isocalendar()[2] - 1)
    ret = week_1 + timedelta(days=(week - 1) * 7 + (day - 1))
    if ret.year != year:
        raise ValueError(f"Invalid week: {week} for year {year}")
    return ret


if __name__ == "__main__":
    wrong_rejects = wrong_accepts = 0
    examples = []
    for y in range(2000, 2031):
        for w in range(1, 54):
            for d in range(1, 8):
                try:
                    valid = date.fromisocalendar(y, w, d)  # the standard library's own check
                except ValueError:
                    valid = None
                try:
                    got = patched(y, w, d)
                except ValueError:
                    got = None
                if valid is not None and got is None:
                    wrong_rejects += 1
                    if len(examples) < 4:
                        examples.append(f"{y}-W{w:02d}-{d} is valid ({valid}) but the patch raises")
                if valid is None and got is not None:
                    wrong_accepts += 1
    print(f"valid ISO dates the patch rejects: {wrong_rejects}; invalid ones it still accepts: {wrong_accepts}")
    print(*examples, sep=chr(10))
