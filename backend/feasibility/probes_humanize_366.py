import hashlib
import subprocess
import sys

import humanize

SIZES = [0, 1, 7, 999, 1000, 1023, 1024, 1025, 999_999, 1_000_000, 1_048_575, 1_048_576, 5_000_000, 10**9, 10**12,
         123_456_789, 10**15, 10**21, 10**27, -1, -999_999, -1_048_575]
NUMERIC = ["%.1f", "%.0f", "%.3f", "%d", "%5.1f", "%g"]
TEXT = ["Size: %.1f", "%.1f bytes-ish", "<%.2f>", "~%.0f", "[%.1f]"]
OPTIONS = [dict(), dict(binary=True), dict(gnu=True)]


def call(n, fmt, opts):
    try:
        return humanize.naturalsize(n, format=fmt, **opts)
    except Exception as e:  # noqa: BLE001
        return "RAISES " + type(e).__name__


numeric = [call(n, f, o) for n in SIZES for f in NUMERIC for o in OPTIONS]
print("numeric formats:", len(numeric), "hash", hashlib.sha256("|".join(numeric).encode()).hexdigest()[:16],
      "raises", sum(x.startswith("RAISES") for x in numeric))
text = [(n, f, o, call(n, f, o)) for n in SIZES for f in TEXT for o in OPTIONS]
print("text formats:", len(text), "raises", sum(t[3].startswith("RAISES") for t in text))
for n, f, o, out in text:
    if n in (999_999, 1_048_575, 1_000_000) and o in (dict(), dict(gnu=True)):
        print(f"  {n:>9} {f!r:<18} {o!s:<14} -> {out}")
r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--color=no"], cwd="/testbed",
                   capture_output=True, text=True)
print("pytest:", (r.stdout.strip().splitlines() or ["(no output)"])[-1])
