"""Reproducible scientific figure addendum; does not mutate frozen bundles."""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
BASE = OUT.parents[1]
traces = pd.read_csv(OUT / "diagnostic_traces.csv")
pairs = pd.read_csv(OUT / "paired_v2_fd0625.csv")
fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.7), layout="constrained")

left = traces[(traces.parameter_set_id == "q2r3-p0107") & (traces.law_policy == "linear_extension")]
left = left[(left.elapsed_hours >= 178) & (left.elapsed_hours <= 214)]
case = pairs[pairs.base_scenario_id == "q2r3-p0107-S_T_H-linear"].iloc[0]
axes[0].plot(left.elapsed_hours, left.analytic_margin, "o-", ms=3, lw=1.6, color="#173c69", label="Analytical thermal")
axes[0].plot(left.elapsed_hours, left.fd0625_margin, "s--", ms=2.5, lw=1.2, color="#ca732d", label="FD thermal, dz=0.0625 m")
axes[0].axvline(case.v2_onset_elapsed_hours, color="#6d6d6d", ls=":", lw=1.2, label="v2 dz=0.125 onset only")
axes[0].axhline(0, color="black", lw=.8)
axes[0].set(title="p0107 S+T+H: near the initiation criterion", xlabel="Elapsed since 2026-06-01 00:00 UTC [h]", ylabel="Failure margin (positive = stable)", ylim=(-.01, .02))
axes[0].legend(fontsize=8, loc="upper right")

right = traces[(traces.parameter_set_id == "q2r3-p0052") & (traces.law_policy == "thawed_rock_contact")]
peak = right.iloc[np.abs(right.analytic_margin-right.fd0625_margin).argmax()]
right = right[(right.elapsed_hours >= peak.elapsed_hours-8) & (right.elapsed_hours <= peak.elapsed_hours+8)]
axes[1].plot(right.elapsed_hours, right.analytic_margin, "o-", ms=3, lw=1.6, color="#173c69", label="Analytical thermal")
axes[1].plot(right.elapsed_hours, right.fd0625_margin, "s--", ms=2.5, lw=1.2, color="#ca732d", label="FD thermal, dz=0.0625 m")
axes[1].axhline(0, color="black", lw=.8)
axes[1].set(title="p0052 S+T+H: thaw-policy discontinuity", xlabel="Elapsed since 2026-06-01 00:00 UTC [h]", ylabel="Failure margin (counterfactual diagnostic)")
axes[1].legend(fontsize=8, loc="best")
for ax in axes:
    ax.grid(alpha=.18)
    ax.spines[["top", "right"]].set_visible(False)
fig.suptitle("Conditional numerical scenarios: thermal solver comparison", fontsize=13)
target = OUT / "numerical_comparison.png"
fig.savefig(target, dpi=180, metadata={"Software": "Q2 reproducible numerical scenario figure"})
plt.close(fig)
print(json.dumps(dict(path=str(target), bytes=target.stat().st_size, sha256=hashlib.sha256(target.read_bytes()).hexdigest())))
