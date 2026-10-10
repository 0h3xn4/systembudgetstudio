"""Wall-clock limits for the tests that time something.

The spec target (10 s for the week-at-1-s stress case) holds on the reference machine; shared CI
runners are slower and noisy. A test fails only when the time is above `LIMIT_S`, three times the
target, which a real regression (a quadratic loop, a lost cache) exceeds by far. `REFUSE_S` is
for hostile inputs that must be refused quickly instead of hanging: the point is "not for minutes".
"""

TARGET_S = 10.0
LIMIT_S = 3 * TARGET_S
REFUSE_S = 10.0
