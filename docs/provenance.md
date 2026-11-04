# Provenance and scope

This is newly implemented Python code, authored for publication in 2026. It applies practical lessons from an earlier private character-animation workflow: preserve alpha, measure original pixel anchors instead of relying on changing arm bounds, keep shared scale, represent frame timing explicitly, and review on multiple backgrounds. It is not a claim that an existing application was extracted unchanged.

No original private character images, application runtime, user paths, keys, credentials, or cache files are distributed. `examples/generate_demo.py` draws a new geometric character using only Pillow primitives. Those generated examples are covered by this repository's MIT license.

Pillow is an external dependency, installed normally rather than vendored. Its license remains its own; see <https://github.com/python-pillow/Pillow> and <https://pillow.readthedocs.io/>. OpenRaster follows the publicly documented container structure: <https://www.openraster.org/>.

Established tools already cover parts of this space, including Pillow for image processing and Aseprite's CLI for batch sprite workflows (<https://www.aseprite.org/docs/cli/>). This project's narrower contribution is a small configuration-driven alignment pipeline with original-pixel anchors, repeatable timelines, bounded ZIP handling and a portable offline QA preview. It is not a replacement for a full animation editor.
