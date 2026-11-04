# Motion analysis implementation plan

**Goal:** Convert public SpriteFrame observations into independent, offline, reviewable motion QA improvements.

**Architecture:** A Pillow-only analysis module consumes normalized RGBA frames and durations. It returns visual-distance diagnostics, duration-preserving adjacent-frame groups and ranked loop candidates. The build writes these suggestions to quality.json and embeds them in its offline preview; output assets remain unchanged until a user explicitly adopts suggested configuration. Nearest-neighbor resampling is an optional deterministic choice for pixel art.

**Evidence boundary:** Public HTML, publicly delivered JS and synthetic browser behavior only. REA 6.8.0 static Evidence is retained outside this repository. No site source, artwork or model implementation is redistributed. Backend AI generation and matting internals are unknown. General pixel comparison and motion-continuity techniques are implemented independently.

**Alternatives:** Automatically dropping frames risks timing/motion loss; suggestions with preserved duration are the selected first step. Rebuilding a complete browser painting/video/cloud application would expand dependencies and is deferred. The focused enhancement preserves existing Python/JSON workflows.

- [x] Add failing tests for invisible RGB invariance, small visible changes, adjacent grouping with duration conservation, monotonic motion vs periodic motion, static sequences and variable timing.
- [x] Implement analysis.py with bounded 24×24 premultiplied RGBA features, global/local RMS distance, neighboring-step context and change-centroid seam velocity scoring. Limit candidate boundaries to 128 samples; actual immediate neighbors and all adjacent steps remain available. Explain mapping/coverage.
- [x] Add optional analysis config (`enabled`, `duplicate_threshold`) and `resample` (`lanczos`/`nearest`) with strict validation. Defaults preserve rendered output. Keep minimum loop length 4 and maximum candidates 3 as fixed bounds, reducing tuning until broader datasets justify it.
- [x] Integrate quality report and preview: show duplicate savings, downloadable proposed sequence/durations, loop preview range and reset. Never apply approximate deletions silently.
- [x] Document public-site findings with evidence hashes/locations and known unknowns; update skill with concrete review/application workflow.
- [x] Run full tests/lint; browser check candidate selection/reset/download/mobile; build/install package and independently review.
- [ ] Push feature branch and draft PR to CASTyang/frame-sequence-workbench.

Acceptance examples: `[A,A,B]` at `[80,120,100]` yields proposed source sequence `[A,B]` and durations `[200,100]`; transparent red/blue hidden RGB is equal; a repeated closed orbit should rank a complete moving cycle above a static endpoint hold; a straight translating object must not be called a seamless loop. Candidate scores are diagnostics, not semantic motion guarantees.
