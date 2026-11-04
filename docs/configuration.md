# JSON configuration reference (v1)

All unknown keys are errors. Paths resolve relative to the configuration file. JSON must be UTF-8 (a BOM is accepted), at most 1 MiB. An omitted field uses its default. No environment substitution, shell execution, or network input occurs.

| Field | Type / default | Meaning |
| --- | --- | --- |
| `source` | required object | `type` and `path`; sheet also accepts `cell`, `count` |
| `source.type` | `directory`, `zip`, `sheet` | PNG only; animated PNG is rejected |
| `source.path` | required string | Relative to config or absolute local path |
| `source.cell` | `[width,height]` | Required for sheet, positive integers <=8192; exact grid with no margin/gutter |
| `source.count` | all sheet cells | First N row-major cells, 1..512 |
| `source.allow_gaps` | `false` | Permit intentionally missing numeric filename IDs for directory/ZIP inputs; duplicates remain errors |
| `action_id` | `"animation"` | 1..64 ASCII letters/digits, `_` or `-`; first character must be a letter/digit; preserved in manifest |
| `loop` | `"infinite"` | `infinite` or `once`; applied consistently to GIF, WebP and HTML |
| `crop` | whole source frame | `[left,top,right,bottom]` original-frame integer pixel bounds; positive area, inside every affected source frame; right/bottom exclusive |
| `canvas` | `[256,256]` | Positive integer width/height <=8192, product <=16,777,216 |
| `trim` | `true` | After explicit crop, further crop each frame to all nonzero alpha before transforming |
| `resample` | `"lanczos"` | `lanczos` for smooth artwork, `nearest` for pixel art; applied to normalization |
| `analysis` | `{}` | Optional object; unknown analysis keys are errors |
| `analysis.enabled` | `true` | Emit motion diagnostics and a proposed timing-preserving config patch; false skips analysis |
| `analysis.duplicate_threshold` | `0.01` | Normalized visual distance 0..0.2; zero requires identical visible pixels, larger values propose more approximate removals |
| `anchor` | `"bottom-center"` | Source-relative fraction after optional crop; names `center`, `top-left` or `[x,y]` in 0..1 |
| `source_anchor` | absent | Original single-frame pixel coordinate `[x,y]`, each 0..16384; overrides `anchor` and accounts for crop offset |
| `target_anchor` | `"bottom-center"` | Canvas fraction/name using same syntax as `anchor` |
| `scale` | `1` | Uniform multiplier of shared contain fit, .001..16 |
| `offset` | `[0,0]` | Canvas pixel offset, each -16384..16384; positive y moves down |
| `frames` | `{}` | Object keyed by canonical zero-based source indices, e.g. `"2"`; values allow only anchor/source_anchor/target_anchor/scale/offset/crop |
| `sequence` | all source indices | Nonempty 0-based index list, at most 512; may repeat or omit source frames |
| `duration_ms` | `100` | Default integer frame duration 10..60000 ms |
| `durations_ms` | absent | Integer durations for **output sequence**, takes precedence; exact sequence length |
| `sheet_columns` | `8` | Integer 1..512, clamped to output frame count |
| `exports` | `["png","sheet","gif","webp"]` | Unique subset of png/sheet/gif/webp/ora; empty list creates preview + reports only |

GIF builds have a conservative total timeline limit of **655350 ms** (65535 centiseconds). Pillow can merge adjacent identical frames into one hold; the GIF delay field cannot represent a longer hold. Longer timelines fail with a clear configuration error before rendering. Remove `gif` from exports or shorten the sequence; PNG, HTML and WebP are not subject to this GIF-specific limit.

Completely transparent frames produce blank canvas-sized outputs without resampling an invisible source rectangle; their manifest `scaled_size` is `[0,0]`. This avoids excessive invisible allocations when a different source frame contains only a tiny visible subject.

Per-frame `scale` multiplies global scale, and per-frame `offset` adds to global offset. Per-frame anchor and crop values replace corresponding global values. A global `source_anchor` remains authoritative even if a per-frame `anchor` is set; set that frame's `source_anchor` to change the pixel anchor.

Explicit crop runs before alpha trim, shared fit and placement. `source_anchor` always refers to the original single-frame coordinates (a sheet cell's local coordinates), even after both crop stages; it is never interpreted relative to the crop rectangle. Normalized `anchor` fractions refer to the resulting cropped image. Cropping can intentionally remove content; empty crops are retained and warned. Out-of-image crop bounds fail rather than silently introducing padding. Every imported frame's crop is validated, including frames omitted by sequence.

The HTML comparison embeds original, unmodified source PNGs alongside processed output. Both panels follow the same sequence index, duration, playback state, background and zoom control. At 100% each image uses its own native pixel dimensions. No files or server are needed. The original panel shows a sheet cell for sheet inputs. With `loop:once`, playback holds the last frame after its duration and offers Replay; GIF omits its repeat extension and WebP uses a loop count of 1. `infinite` uses loop count 0 in both encoders.

The shared fit is `min(canvas_width / max_frame_width, canvas_height / max_frame_height)` across **all imported nonempty frames**, after optional alpha cropping. It is unaffected by sequence selection, so selecting a subset does not change character size. Completely transparent frames are retained and flagged. Resampling defaults to Pillow Lanczos; nearest-neighbor is available for pixel art. Integer raster dimensions introduce subpixel rounding differences. Anchors may place visible content outside the canvas; this is allowed and reported as clipping in QA.

For a 128×128 character with constant feet at (64,114), use `source_anchor:[64,114]`, `target_anchor:[0.5,0.9]` and `scale:0.8`. Cropped-bounds anchors alone cannot infer feet and may drift when an arm changes the bounding box. If feet move in the source, specify each source frame's measured anchor. `frames` keys refer to source indices before sequence reordering.

Directory import is nonrecursive, PNG extensions case-insensitive. Both directory and ZIP names use natural ordering with a deterministic case-sensitive tie-break; the manifest records exact names. ZIP directories are accepted but never extracted. ZIP members with `..`, backslashes, absolute paths, colons, duplicate names, Unix symlink mode or encryption are rejected. Limit: 2048 archive entries, 512 PNG frames, total stored/expanded input <=128 MiB, compression ratio <=1000:1. One decoded image <=16,777,216 pixels; all decoded input frames and output sequence independently <=67,108,864 pixels. Sheet padding also counts against the output sheet limit. These are fixed conservative limits, not a general sandbox for hostile files.

Numeric filename checks group paths by their text prefix/suffix around the last digit run (case-insensitive). Each group must be contiguous between its minimum and maximum ID unless `source.allow_gaps:true`; no zero/one starting index is required. Duplicate IDs such as `frame1.png` and `frame01.png` always fail. Unnumbered filenames remain valid. Sheet count is explicit and is not subject to filename checks.

QA includes opaque source count and `loop_rgba_mae` / `loop_alpha_mae`: normalized 0..1 mean absolute channel differences between the final and first output frames. These describe the loop boundary, not motion smoothness or a pass/fail threshold; hidden RGB can affect the RGBA metric. Manifest bounds and placements provide per-frame geometric diagnostics.

## Motion analysis and explicit adoption

`loop_premultiplied_distance` adds a hidden-RGB-invariant boundary metric. It takes the larger of global premultiplied RGBA RMS and half an approximate local 8×8 energy maximum, normalized 0..1. Existing metrics remain available for compatibility.

When enabled, `quality.json.analysis` contains:

- `duplicates`: threshold, zero-based output `keep_positions`, merged `durations_ms`, removed positions with retained-position/distance evidence, total duration and `config_patch`.
- `loop_candidates`: at most three inclusive output-position intervals (`start`, `end`), total duration, seam-to-typical-step ratio, change-centroid velocity change, velocity reliability, score and `good`/`review` heuristic rating. The UI calls `good` “Lower seam”; it is not a quality guarantee. Unavailable velocity evidence uses a conservative penalty of 2, with `velocity_reliable: false`.
- `coverage`: input count, loop sample count, selected original output positions and `complete_loop_search`. All boundaries are considered up to 128 frames; longer timelines sample 128 boundaries uniformly. Intervals contain at least four original frames. Their actual immediate seam neighbors and all original adjacent steps are always examined, including unsampled frames. Static or exactly repeated seam endpoints do not establish a moving loop and are excluded.

Consecutive near-duplicates are compared with the **last kept frame**, not every previous pose; later returns remain. Removed hold durations merge into that frame. Rendering and all encoded assets still follow the original timeline. With analysis disabled, `analysis` is null and no patch file is produced; the boundary metric remains available.

`suggested-config.json` is a **fragment**, not a complete build file. Merge its `sequence` and `durations_ms` into a copy of the original configuration, saved beside the original so relative source paths resolve identically. Keep transforms, anchors, source, exports and other options. The patch maps output positions back to original source indices. Holds above 60000 ms split into repeated source indices with balanced legal durations; total time stays unchanged. GIF timing quantization still applies.

Example: source sequence `[2,2,0]` at `[80,120,100]` ms proposes `[2,0]` at `[200,100]` ms. Approximate removal can erase an intentional blink or gesture; inspect every proposal before adopting it.

The self-contained preview has a Motion review section with removal details, patch download, loop-range preview and Full sequence reset. Range selection affects only preview playback; selecting a candidate repeats it even when the original action is `once`. Returning to Full sequence restores the action's playback policy. To export a loop, explicitly select the candidate's source indices/durations from the original manifest into a new configuration and build into a new output directory. Loop and duplicate proposals are alternative edits of the original timeline; their position indices cannot be combined blindly after a deletion.

Loop scores use 24×24 premultiplied features and timing-aware movement of pixels that differ from a temporal median background. This helps opaque backgrounds but is not optical flow or semantic motion analysis. Unreliable motion estimates require review. Uniformly scaling all durations leaves the normalized ranking unchanged; variable durations affect seam velocity. Small details, rotation, occlusion and multiple subjects may defeat this heuristic. See [research and method boundaries](spriteframe-research.md).

Build validates before publishing, renders in a sibling temporary directory, then renames it into place. A failed build cleans the temporary directory. The destination must not exist or overlap the source directory/file. Do not run simultaneous builds targeting the same destination. Original assets are never changed.

Manifest `schema_version:1` includes `action_id`, `loop`, `canvas`, `frame_count`, `total_duration_ms`, `fit_scale`, selected `exports`, optional `sheet`, and frame records: `index`, `source_index`, `source_name`, `duration_ms`, `file` (null if PNG export disabled), `source_bounds`, `crop_bounds`, `alpha_bounds`, `placement`, `scaled_size`, `clipped`. `source_bounds` is original alpha bounds; `crop_bounds` is the effective original-coordinate rectangle after explicit crop and optional alpha trim. Bounds are `[left,top,right,bottom]`, right/bottom exclusive, or null for empty alpha. Paths in the manifest are output-relative; no source absolute path is emitted.

PNG and WebP retain alpha; GIF uses 255 color entries plus transparency and thresholds alpha at 128. GIF timing is quantized to 10 ms; encoders may combine identical adjacent frames. The manifest, PNG sequence and HTML preview remain authoritative for exact requested frame count and timing. OpenRaster is a layered still-image container, not a timeline format; layer order follows output sequence and only the first layer starts visible. WebP support depends on the Pillow build; a missing encoder fails the whole build without publishing partial output.
