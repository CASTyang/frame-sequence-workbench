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

## Version 0.2 motion analysis (2026-11-04)

The Windows Python 3.11 suite passes 36 tests with Pillow 12.3.0. An isolated installation of the 0.2 wheel with the minimum supported Pillow 10.4.0 also passes all 36 tests, importing from that environment's site-packages. Ruff passes, and source/wheel distributions build successfully. The original 24 tests remain; additions cover hidden transparent RGB, duration conservation, moving cycles versus straight translation, static sequences, boundary sampling, long-hold patch splitting, nearest scaling and disabled analysis.

Independent review reproduced three scoring defects before fixes: opaque backgrounds hid moving-subject centroids, an absolute velocity floor rewarded uniformly slowed poor seams, and sampled neighbors missed real short reversals. Regression tests failed before fixes and now pass. The reviewer reran the 512-frame adversarial case and found no unresolved important issues within its scope. Loop ratings remain heuristics, with coverage and unreliable velocity exposed.

Playwright with installed Chrome exercised the final offline HTML: play/pause, scrub and original/processed synchronization; candidate selection, range wrapping and full reset; background, speed and native zoom; once-mode final hold and Replay; disabled analysis; and actual JSON patch download. The downloaded patch was `[0,1,0]` with `[200,100,150]` ms. A 390px viewport had no horizontal overflow. No HTTP requests or page errors occurred. Desktop/mobile screenshots were inspected; the README screenshot contains only original geometric artwork. Browser plugin tools were unavailable, so Playwright was used directly.

An independent forward evaluation followed the updated motion skill with three newly generated poses. It built `[2,2,0]` / `[80,120,100]`, merged only the suggested fields into a sibling config and rebuilt `[2,0]` / `[200,100]`. Both timelines total 300 ms; relative input paths, original-pixel anchor, offsets, nearest resampling, per-source transforms, geometry and retained RGBA pixels were preserved. Hashes confirmed original inputs/config/output stayed unchanged. Original-manifest interval mapping was checked separately; three frames do not meet the four-frame loop minimum. This evaluation did not inspect browser playback; that is covered above. The updated skill also passes the official frontmatter validator.

Public-site research used synthetic inputs, public JavaScript and REA static analysis. Evidence scope and unknown AI backend details are recorded in [the research report](spriteframe-research.md). Raw site code, third-party artwork, large evidence files, local paths and credentials are excluded from distributions. The CI matrix also builds the new analysis example; remote CI results are available on the feature PR, separate from these local records.
