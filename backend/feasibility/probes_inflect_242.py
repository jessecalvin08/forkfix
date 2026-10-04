import collections
import hashlib
import random
import subprocess
import sys

import inflect

p = inflect.engine()


def outcome(n):
    try:
        return "ok", p.number_to_words(n)
    except Exception as e:  # noqa: BLE001
        return type(e).__name__, ""


# 1. Out-of-range magnitudes with every kind of leading group: the issue says these should raise NumOutOfRangeError.
kinds = collections.Counter()
for exp in range(30, 70):
    for lead in (1, 2, 5, 10, 11, 12, 13, 15, 19, 20, 21, 99, 100, 101, 110, 111, 115, 119, 999):
        for add in (0, 1, 7, 13):
            kinds[outcome(lead * 10**exp + add)[0]] += 1
print("huge inputs ->", dict(kinds))

# 2. In-range inputs must be unchanged: hash the words for teens, tens, hundreds and a seeded random sample.
rng = random.Random(0)
sample = list(range(0, 1200)) + [rng.randrange(10**rng.randrange(3, 33)) for _ in range(4000)]
sample += [10**e + t for e in range(3, 33, 3) for t in range(10, 20)]
digest = hashlib.sha256("|".join(outcome(n)[1] for n in sample).encode()).hexdigest()[:16]
errors = sum(outcome(n)[0] != "ok" for n in sample)
print("in-range inputs:", len(sample), "hash", digest, "errors", errors)

# 3. The project's own test suite.
r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-x", "-q"], cwd="/testbed",
                   capture_output=True, text=True)
print("pytest:", (r.stdout.strip().splitlines() or ["(no output)"])[-1])
