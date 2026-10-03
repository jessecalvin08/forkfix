"""Free check (no model, no sandbox): the tabulate #71 patch applies floatfmt to every string that parses as a float.
This replicates the patched `valtype is str` branch of tabulate._format and shows what it does to strings that should
stay as written. Run: python -m feasibility.tabulate_71_probe"""


def patched_format_str(val, floatfmt="g"):
    try:
        return format(float(val), floatfmt)
    except (ValueError, TypeError):
        return f"{val}"


if __name__ == "__main__":
    for text in ("0123", "007", "1e3", "12345678901234567890", "1_000", " 5 ", "0.10", "nan", "inf", "abc"):
        print(f"{text!r:>26} -> {patched_format_str(text)!r}")
