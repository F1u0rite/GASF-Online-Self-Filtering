# Delivery verification

Verified on 2026-10-28 in the supplied Windows workspace. The project was continued from its existing parser/audit/statistics modules; those modules and their valid results were not discarded.

## Workspace and data protection

- At resumption, `git status --short` showed only `?? visualization/`; `git diff --stat` was empty. The five original visualization subdirectories were siblings, with no accidental nesting or malformed PowerShell paths.
- The original baseline covers all seven raw logs and ten files under `src/` (17 files total). SHA-256 values still match the pre-work baseline. No logs, ROS 2 C++ source, algorithm configuration or existing experiment results were edited.
- Every new file is under `visualization/`. The pipeline only reads input bytes; all output operations are confined to the visualization project, with checks preventing input/output overlap.

## Analysis correctness

- 7 files / 845 records parsed. 9 requested fields complete. 0 parser warnings/errors for this batch. 838 adjacent within-run intervals are exactly 10 Frame units.
- All 7,605 raw core-field values were independently tokenized and compared to parsed values in tests.
- Zero raw denominators produce NA; illegal numbers and ambiguous repeated keys produce explicit diagnostics. Ratios greater than 1 remain un-clipped and trigger a blocking error. Incomplete records are retained; duplicate Frames and restarted timelines are not silently merged.
- Independent arithmetic checks verified saved per-group ratio and latency sample counts, means, extrema and P25/P50/P75/P95/P99. The quantile checker uses a separate scalar interpolation implementation.
- No statistical outliers were deleted. The recorded 9.304 ms at Frame 1500 of 03_arc_A is preserved and annotated.
- Static/dynamic and cage conditions remain separate. Constant-mask correlations are NA; no p-values, inferred ground truth, accuracy metric or causal result is reported.

## Executed tests

`python -m unittest discover -s visualization/tests -v`: **18 tests passed**, exit code 0.

Coverage: ROS prefix/spacing/separators; missing versus zero; illegal numeric values and Int64 overflow; duplicate keys; duplicate Frames; Frame reversal; gaps; unrecognized lines; decode errors; UTF-16 BOM; zero and excessive ratios; empty input; independently checked real-log values; real activation samples and maximum latency; path protection; known linear quantiles; distinct ratio weighting; undefined constant correlations.

Synthetic malformed records are isolated test fixtures in temporary directories under `visualization/tests/` and never enter research figures or tables.

## Executed pipeline and format validation

`python visualization/run.py`: **PASS**, all seven groups processed, all 12 CSVs and 15 formal image files written. The captured successful run is `pipeline_run.log`.

`python visualization/validate_outputs.py --render-pdfs`: **PASS**. Per-file evidence is in `validation.json`.

| Figure | PNG pixels | PNG DPI metadata | PDF | SVG |
| --- | --- | --- | --- | --- |
| 01_online_mask_convergence | 2460 × 2610 | 299.9994 × 299.9994 | 1 vector page; rendered | Parsed and rendered |
| 02_mask_hit_ratio_comparison | 2460 × 2160 | 299.9994 × 299.9994 | 1 vector page; rendered | Parsed and rendered |
| 03_runtime_latency_distribution | 2460 × 2220 | 299.9994 × 299.9994 | 1 vector page; rendered | Parsed and rendered |
| 04_static_vs_dynamic_learning | 2460 × 3180 | 299.9994 × 299.9994 | 1 vector page; rendered | Parsed and rendered |
| 05_orientation_diversity_vs_mask_activation | 2460 × 2040 | 299.9994 × 299.9994 | 1 vector page; rendered | Parsed and rendered |

The stored DPI is the ordinary integer-pixels-per-metre rounding of the requested 300 DPI. No downsampling was applied to the formal PNGs.

Poppler `pdfinfo` and `pdftoppm` successfully opened/rendered all five PDFs. Bundled pypdf strict parsing independently found one page in each, extractable English text and zero embedded raster images. All five SVGs passed XML/path checks and were decoded to PNG using bundled sharp/librsvg. See `pdf_structure_validation.json`, `svg_render_validation.json`, `pdf_render/`, `svg_render/` and `vector_render_comparison.png`. These optional QA tools were already available; no new packages were installed.

All five original PNGs were visually reviewed. Figure 1 initially had a legend/note collision and an annotation close to the upper candidate trace; the existing plotting code was adjusted, exports regenerated and the revised PDF rendering checked. The final figure keeps the legend, explanatory notes and data separated. Rendered PNG/PDF/SVG comparison shows matching content. Text boundary checks execute before each export. Full-size figures should be used for final thesis review; the overview montage is navigation only.

## Skill workflow verification

The installed `plot-is-all-you-need` entry, plotting Skill and all three applicable stages were read. Three gallery candidates/cards were opened; no reference script was available in their code fields. Six real-data exploratory views were generated before formal plotting, exposing the zero-heavy static distributions, the full-range latency outlier and the 60-bin cap. This motivated observation-preserving boxes/ECDF, independent experiment facets and un-fitted relationship scatter plots. `style_appraisal.png` places reference arrangements beside the final GASF ratio figure. Reference attribution is retained separately. The installed gallery and taste files were not changed.

## Reproducibility and remaining limits

An unchanged second full run produced **byte-identical SHA-256 hashes for all 27 compared artifacts** (12 CSV + 5 PNG + 5 SVG + 5 PDF). See `reproducibility.json`. Jitter uses a fixed seed, quantile interpolation is explicit, SVG identifiers use a fixed salt, and PDF/SVG creation timestamps are suppressed. Font/rendering differences across operating systems or library versions can still change file bytes; use the recorded environment for exact reproduction.

The delivered code was executed with the existing Windows Python 3.14.8 installation and the recorded dependency versions. Installation into a newly downloaded virtual environment was not exercised; the documented PowerShell commands and version constraints provide that path. Core execution requires only NumPy, pandas, Matplotlib and Pillow; optional vector-render checks require additional existing local tools.

No blocking implementation issue remains. Scientific limitations remain: sparse callback logging, no point labels, no verified repeated trials, unequal experiment duration, no per-run historical build/config/subscriber manifest, no Mask voxel identities, orientation-cap saturation, asynchronous model state and the disturbed 04_loop_A mounting condition. None is replaced with fabricated data or unsupported inference. Follow-up experiment recommendations are in `audit_report.md` and the project README.
