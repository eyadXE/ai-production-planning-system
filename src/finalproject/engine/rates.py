"""Handbook constants — every figure traces to a clause (0.6).

Policy note (implementation of clause 3.1 "books whole weeks forward"):
- a week may HOST a new fabrication run only if it is at least half free;
  fragmented leftovers of nearly-full weeks are not dependable slots.
- once a run has started, the next week may absorb a carry-over top-up of at
  most 25% of weekly capacity (existing committed work keeps priority).
This is the platform's stated booking policy, applied uniformly.
"""

# Clause 2.2 — fabrication rates
RAILING_H_PER_M = 4.0
MEZZANINE_H_PER_M2 = 2.5
STAIR_FLIGHT_H = 40.0
FRAME_H_EACH = 16.0
DOUBLE_GATE_H = 24.0
SINGLE_GATE_H = 14.0
SECURITY_DOOR_H = 8.0
CAGED_LADDER_H = 20.0
RACKING_H_PER_BAY = 6.0
CANOPY_H_PER_M2 = 2.0

INSTALL_PCT = 0.25          # clause 2.3
LABOUR_FAB_EGP_H = 95.0     # clause 2.4
LABOUR_INSTALL_EGP_H = 120.0

WASTE_BARS_PCT = 0.08       # clause 1.5
WASTE_SHEETS_PCT = 0.10
CONSUMABLES_PCT = 0.04      # clause 1.5 (of material cost)

GALV_TURNAROUND_WEEKS = 2   # clause 3.2

# Scheduler policy (clause 3.1 implementation, see module docstring)
HOST_WEEK_MIN_FREE_RATIO = 0.5   # week must be >=50% free to host a new run
TOPUP_MAX_RATIO = 0.25           # carry-over absorbed by the following week
WEEKLY_CAPACITY_DEFAULT = 320.0  # capacity.json nominal week

DECISIONS = (
    "ESCALATE",
    "REFUSE_OVERRIDE",
    "FLAG",
    "REQUEST_INFO",
    "DELAY_RISK",
    "PLAN",
)
