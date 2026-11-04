# Validation record

Validated 2026-11-04 on Windows with Python 3.11 and Pillow 12.3.0. Tests use temporary synthetic PNGs only. No private images or live external services were needed.

## Red → green evidence

Initial acceptance run, before the pipeline existed:

```text
python -m unittest discover -s tests -v
Ran 8 tests in 0.051s
FAILED (failures=10)
AssertionError: unexpectedly None : public pipeline build API must exist
```

After implementation, original-pixel anchor regression first failed because `source_anchor` was not accepted; it then passed while a changed arm bounding box retained the same transformed foot position. Numbering, opacity/loop diagnostics and transient Windows rename tests were added before their implementation. An extreme numeric JSON test exposed `OverflowError: int too large to convert to float`; numeric validation was corrected to reject it with ValueError.

Final unit run:

```text
python -m unittest discover -s tests -v
Ran 24 tests in 0.516s
OK
ruff check .
All checks passed!
```

Coverage includes natural ordering, required numbering continuity and duplicate IDs, alpha/aspect, explicit normalized and original-pixel anchors, repeated sequence/timing, scale/offset, all five image exports, ZIP and sheet imports, clipping/opaque/empty QA, corrupted images, invalid config, archive path traversal, excessive canvas, source/output overlap, existing output preservation, failed-export cleanup and bounded rename retries.

## Real CLI builds

Original demo generator produced eight frames, one ZIP and one sheet. Commands run successfully:

```text
frame-workbench build examples/directory.json --output examples/output-directory
frame_count: 8, total_duration_ms: 960
frame-workbench build examples/zip.json --output examples/output-zip
frame_count: 14, total_duration_ms: 1400
frame-workbench build examples/sheet.json --output examples/output-sheet
frame_count: 4, total_duration_ms: 560
```

An initial Windows directory rename encountered a transient access denial. The failed build cleaned its staging directory. A bounded retry was implemented and regression-tested; the subsequent real build succeeded. Persistent permission failures still report an error.

## Browser verification

The generated demo preview was exercised through Playwright with installed Chrome: playback advances; pause remains fixed; frame slider selects the fourth frame; original and processed frames remain synchronized; checker/light/dark backgrounds, speed and 100% zoom work; image corner alpha remains zero. A one-shot animation stops on the final frame and the Replay control restarts it. A 390px mobile viewport had no horizontal overflow. No page errors were recorded. Updated desktop/mobile screenshots were inspected; the public screenshot contains only the newly generated geometric character.

## Independent skill forward evaluation

A separate agent used `skills/character-motion-pipeline/SKILL.md` with an independently generated geometric robot, the actual `python -m frame_workbench build` command and output assertions. Four 160×120 frames totalled 660 ms. With `source_anchor: [80,108]` and `trim: false`, a moving hand did not shift the feet/body. Normalized PNG pixels, WebP frame count/durations/alpha, four complete-pose OpenRaster layers and self-contained preview assets passed verification. The native-size contact sheet was visually inspected on multiple backgrounds. Browser playback for this robot was not tested; the main-demo browser checks above cover that separately.

The no-skill baseline already recommended stable landmarks and honest matting limits. No baseline failure is claimed. The skill adds a reproducible CLI/configuration/output workflow. Its frontmatter also passed the skill validator.

## Approved-scope follow-up

Independent review identified missing action metadata, loop policy, explicit crop bounds and original/processed comparison. Four behavioral tests initially failed on unsupported fields/missing manifest data. Implementation added validated `action_id`, shared `infinite`/`once` export policy, original-coordinate rectangular cropping and synchronized embedded source frames. Tests decode GIF/WebP loop metadata, verify crop-relative placement preserves original pixel anchors, reject invalid bounds/IDs/policies, and decode embedded original PNG data for a repeated source sequence. The browser checks above cover the updated comparison, once playback and Replay behavior.

## Packaging and limits

Independent quality review reproduced two edge cases: a one-pixel subject plus a fully transparent source exceeded the resize budget, and 12 identical 60-second frames caused Pillow to overflow GIF's merged-delay field. Regression tests initially reproduced both exceptions. Empty frames now bypass invisible resizing; GIF timelines above 655350 ms fail validation with a clear CLI error and no partial output, while the same long timeline remains supported without GIF. The suite now passes 24 tests.

`python -m build` successfully generated source and wheel distributions. The final wheel was installed into the isolated `.venv` with Pillow 12.3.0. The installed `frame-workbench --version` returned 0.1.0; its real demo build produced 8 frames / 960 ms, and all 24 tests passed against the installed wheel (0.507s). The source distribution includes docs, the original example generator/configs and the optional skill; generated frames and local environments are excluded. Independent code review rechecked the empty-frame and GIF-limit fixes and found no remaining actionable issues within its scope.

CI is configured for Python 3.11/3.13 on Windows and Ubuntu; those remote matrix jobs are not claimed as already run. Browser inspection covers Chrome, not every browser. GIF timing/palette limitations and the non-perceptual scope of QA are explicit in the configuration reference.
