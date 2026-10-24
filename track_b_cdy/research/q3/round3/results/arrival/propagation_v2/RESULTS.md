# Mapped propagation adapter v2 results

All **39 delivered file hashes** verified. Exact lineage succeeds for **14 run-target rows = 2 physical runs x 7 representative points**, with no rejected pairing. Five OSM points describe three entities; two paper points remain candidate objects. No independent local validation event is added.

The original compact Q2 release table is embedded in the packet and matches the upstream frozen SHA256. Each run preserves all 20 shared physical parameters through the explicitly documented analytic-erfc thermal-model replacement. The original conceptual area geometry, mechanism slab geometry, Q4 mapped compact raster, and later broad-source release-v2 geometry are distinct. The broad-source table has a different area and volume and is not used for this adapter. A compact vector polygon and independent mapping table were not delivered; those geometry details remain unaudited. The actual supplied compact release raster, volume, grid alignment, support cells, composition and density were audited.

p0000 remains `no_cross_observed_complete`, with no onset timestamp, and all of its propagation records remain **if released**. p0036 uses the actual analytic `point_crossing_linear_between_samples`, bracket **2026-07-08 15:00–16:00 UTC** and interpolation **15:34:17.258933921 UTC**. These are conditional ideal-weather retrospective mechanical first-crossing results, not bulk-release truth or operational verified predictions.

The saved-field check finds **1 raw target hit**: p0036 at the paper junction, bracket **1360.5–1380.1 seconds after assumed bulk release**, at h>=0.1m within the registered 100m representative-point buffer. It remains **unqualified**. The other 13 rows have no threshold hit at the stored outputs; this does not establish continuous-time non-arrival or safety. Requested 1800s and actual final 1800.1/1801.7s are retained separately; last outputs within the requested horizon are recorded explicitly.

Both runs retain the compact-source underresolution and unresolved mass-budget qualification failure. Native internal residuals are **+21.372917% / +12.716325%**; raster-source-adjusted residuals are **+21.153363% / +12.613015%**. These are different representations and are not averaged or relabelled as conserved. All qualified travel intervals, absolute arrival times, probabilities and arrival-envelope inclusion remain null/false. Unknown mechanical-initiation-to-bulk-release lag is never set to zero.

`depth_footprint_diagnostics.csv` and `conditional_footprints.png` use actual hashed fields, without a physics rerun. The 0.1/1/5m thresholds are descriptive. Area is affected grid-cell area; distance is maximum affected cell-centre distance to the union of **positive actual release raster cell footprints**, not to a centroid, the broad candidate source, or a cost path. At 60m the 8/16-cell source support exceeds the exact partial-cell compact polygon; exact polygon distance is unavailable. No footprint or distance is a validated hazard zone or warning distance.

`previous_adapter_comparison.csv` evaluates the previous adapter's header/exact-model rule against these same v2 rows. Its old required aliases would reject the absent target mechanism/parent-geometry columns. The new adapter resolves explicit delivered lineage and a registered model replacement while preserving distinct geometry semantics. QA success checks the adapter and provenance; physical qualification stays unchanged.

Reproduce from the Q3 worktree:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 track_b/.venv/bin/python track_b/research/q3/round3/scripts/join_propagation_v2.py
```
