---
name: character-motion-pipeline
description: Use when preparing reusable character animation from generated pose sheets or transparent PNG sequences, especially when frames drift, scale changes, loop seams or desktop-pet exports need correction. Not for automatic Live2D rigging or guaranteed video matting.
---

# Character motion pipeline

Produce repeatable animation assets and an honest visual review. Keep the user's character, chosen generator and requested motion. This skill works with **frame-sequence-workbench**, a separate installable Python tool; it does not invoke a particular paid AI service.

## Start with the actual material

Inspect dimensions, real alpha values, frame numbering, clipping, and the intended idle pose. Keep original files unchanged. A white or checkerboard-looking background is not proof of transparency. Preserve distinctive white details when assessing extracted video.

- Existing PNGs or pose sheet: use the deterministic build workflow below.
- Generation needed: read [motion-prompts.md](references/motion-prompts.md) and adapt its templates to the selected model's supported inputs. Paid calls require authorization from the user's task, not from this skill.
- Flattened video: explain that matting estimates lost alpha. Test a short segment with an appropriate existing matting tool before processing a whole clip. This tool does not contain video inference or promise clean hair on every frame.

## Configure before building

Install the tool from the repository named `CASTyang/frame-sequence-workbench`, or the user's checkout:

```sh
python -m pip install /path/to/frame-sequence-workbench
python -m frame_workbench --help
```

Find `docs/configuration.md` in that checkout for the current schema. Do not assume the directory containing an installed copy of this skill contains the entire tool. Use explicit filesystem paths supplied by the task or discovered in the workspace.

Set the source type and canvas, then use **stable body/foot anchors**. For a raised hand, the silhouette midpoint moves although the feet do not. A bottom-center alpha-bounds anchor alone cannot correct this. Prefer an explicit original-image pixel anchor, with per-frame overrides when necessary. Keep one scale across frames unless stable head/torso landmarks establish a real scale error; uniform scaling cannot fix inconsistent anatomy.

Make the output canvas large enough for the union of aligned poses. Do not shrink each frame independently to fit its own bounding box. Inspect crop/clipping warnings before accepting the result.

Set a portable `action_id`, playback order, frame durations and `loop` policy (`infinite` or `once`) explicitly. Optional `crop: [left, top, right, bottom]` applies before alpha trimming, globally or per frame; `source_anchor` remains in original-image coordinates. A reverse sequence is useful only when physically plausible. A repeated endpoint can create an unintended pause; a crossfade can create double limbs. Neither is an automatic loop repair.

For pixel art choose `resample: "nearest"`; smooth artwork defaults to `lanczos`. Nearest-neighbor alone does not ensure an integer scale or repair an inconsistent pixel grid.

## Build and review

```sh
python -m frame_workbench build /path/to/motion.json --output /path/to/new-output
```

The destination must be new. Do not delete an existing output to make a command pass; choose a versioned destination unless the user requested replacement.

Open the generated `preview.html` and compare synchronized original/processed frames at native and intended display sizes on light, dark and checker backgrounds. Scrub every frame, then play multiple loops for looping actions; for one-shot actions, check the final hold and replay. Check feet, head size, raised hands, transparent edges and the last-to-first transition where applicable. Read `quality.json`; metrics are diagnostics, not a universal quality score.

With tool version 0.2+, inspect **Motion review** and `quality.json.analysis`. Adjacent removal proposals compare the previous retained pose and merge hold times; a later return to the same pose stays in the timeline. Review the removed-frame list for blinks, settling and intentional pauses before adopting an approximate match. Set `analysis.duplicate_threshold: 0` for exact visible-pixel equality, or `analysis.enabled: false` to skip proposals. Transparent hidden RGB must not be interpreted as visible motion.

Preview loop candidates separately, then reset to Full sequence for comparison. Candidate `start`/`end` are inclusive **output positions in the original build**, not source indices. A low score is not proof of physical continuity; inspect the seam at normal speed and frame by frame. Check `coverage` when more than 128 frames were sampled; unsearched boundaries can be better. An unavailable movement estimate or thumbnail detail loss is a reason to inspect, not to assert success.

If removals are acceptable, merge only `sequence` and `durations_ms` from `suggested-config.json` into a copy of the original JSON **beside the original file**, preserving relative source resolution and transforms. The fragment already maps back to source indices and conserves total duration, including holds split to respect the 60000 ms frame limit. It is not a standalone build config. Rebuild into a new directory and compare duration/provenance against the first manifest. To export a loop instead, map its output positions through the first manifest's `source_index` and retain that interval's durations. Do not combine loop positions with a shortened timeline without remapping and reviewing again. Preview selection never applies an edit to existing exports.

The build exports manifest/timing and normalized frames; request sprite sheet, WebP/GIF and editable OpenRaster according to the target. OpenRaster layers are complete poses, **not semantic body-part layers or a Live2D rig**. GIF has limited colors/transparency; PNG/WebP remain the alpha reference. Keep the JSON build configuration with the source material so edits are reproducible.

## Delivery

Report the artifact paths and the exact commands run. Distinguish:

1. Structural checks: actual frame count, dimensions, timing, decoded outputs and alpha.
2. Visual review: observed jitter, proportions, clipping and loop seam at stated display size.
3. Target integration: tested only if the actual intended player consumed the export and advanced frames.

Do not claim a desktop pet is integrated merely because a preview plays. Do not re-use private character art, voice recordings or service credentials in public examples. A generated frame can require manual correction even after every structural check passes.
