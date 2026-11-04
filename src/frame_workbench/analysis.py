"""Independent alpha-aware diagnostics; proposals never alter the exported timeline."""

import math
import statistics
from functools import lru_cache

from PIL import Image, ImageChops, ImageStat

MAX_LOOP_SAMPLES = 128


def visual_distance(first, second):
    """Premultiplied RGBA RMS, retaining a local-change signal on an 8x8 grid."""
    if first.size != second.size:
        raise ValueError("analysis frames must have matching dimensions")
    difference = ImageChops.difference(first.convert("RGBa"), second.convert("RGBa"))

    def rms(image):
        return math.sqrt(sum(value * value for value in ImageStat.Stat(image).rms) / 4) / 255

    global_score = rms(difference)
    if not difference.getbbox(alpha_only=False):
        return 0.0
    # BOX averages squared differences per tile, so tiny visible changes survive.
    squares = difference.point([round(value * value / 255) for value in range(256)] * 4)
    tiles = squares.resize((min(8, first.width), min(8, first.height)), Image.Resampling.BOX)
    raw = tiles.tobytes()
    local_score = math.sqrt(max(sum(raw[i:i + 4]) / 4 for i in range(0, len(raw), 4)) / 255)
    return max(global_score, local_score * 0.5)


def _feature(image):
    # Pillow resamples premultiplied channels, avoiding RGB bleed under zero alpha.
    small = image.convert("RGBa").resize((24, 24), Image.Resampling.BOX)
    return Image.frombytes("RGBA", small.size, small.tobytes())


def _motion_centers(features):
    """Track deviations from a temporal background, including on opaque canvases."""
    raw_frames = [image.tobytes() for image in features]
    background = [statistics.median(values) for values in zip(*raw_frames)]
    centers, reliable = [], []
    for raw in raw_frames:
        weights = [sum(abs(raw[i + channel] - background[i + channel]) for channel in range(4))
                   for i in range(0, len(raw), 4)]
        mass = sum(weights)
        reliable.append(mass > 0)
        centers.append(tuple(sum(value * ((i % 24) if axis == 0 else (i // 24))
                                 for i, value in enumerate(weights)) / mass for axis in range(2))
                       if mass else (0.0, 0.0))
    return centers, reliable


def analyze(images, durations, duplicate_threshold=0.01):
    """Find consecutive holds and rank bounded loop intervals (inclusive positions).

    Distances and ratings are heuristics, not probabilities or seamless guarantees.
    Variable frame durations scale the centroid velocity around the proposed seam.
    """
    if not images or len(images) != len(durations):
        raise ValueError("analysis requires matching nonempty frames and durations")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0
           for value in durations):
        raise ValueError("analysis durations must be finite and positive")
    if any(image.size != images[0].size for image in images):
        raise ValueError("analysis frames must have matching dimensions")
    if not 0 <= duplicate_threshold <= 0.2:
        raise ValueError("duplicate_threshold must be in [0, 0.2]")
    kept, merged, removed = [0], [durations[0]], []
    for position in range(1, len(images)):
        score = visual_distance(images[kept[-1]], images[position])
        if score <= duplicate_threshold:
            merged[-1] += durations[position]
            removed.append({"position": position, "kept_position": kept[-1], "distance": round(score, 6)})
        else:
            kept.append(position)
            merged.append(durations[position])

    count = min(len(images), MAX_LOOP_SAMPLES)
    positions = sorted({round(i * (len(images) - 1) / max(1, count - 1)) for i in range(count)})
    # Sample only candidate boundaries. True neighbors must remain available at
    # every seam, even if a short reversal falls between sampled boundaries.
    features = [_feature(image) for image in images]
    centers, center_reliable = _motion_centers(features)

    @lru_cache(maxsize=32768)
    def distance(a, b):
        difference = ImageChops.difference(features[a], features[b])
        return math.sqrt(sum(value * value for value in ImageStat.Stat(difference).rms) / 4) / 255

    steps = [distance(i, i + 1) for i in range(len(images) - 1)]
    prefix = [0.0]
    for value in steps:
        prefix.append(prefix[-1] + value)
    elapsed = [0]
    for value in durations:
        elapsed.append(elapsed[-1] + value)

    def velocity(a, b, duration):
        return tuple((centers[b][axis] - centers[a][axis]) / duration for axis in range(2))

    def norm(vector):
        return math.hypot(*vector)

    candidates = []
    for slot, start in enumerate(positions):
        for end in positions[slot + 1:]:
            if end - start < 3:
                continue
            typical = (prefix[end] - prefix[start]) / (end - start)
            seam = distance(end, start)
            if typical < 0.002 or seam < 1e-7:
                continue  # A still or repeated endpoint alone is not evidence of a cycle.
            ratio = seam / typical
            before = velocity(end - 1, end, durations[end - 1])
            across = velocity(end, start, durations[end])
            after = velocity(start, start + 1, durations[start])
            speed = max(norm(before), norm(after))
            reliable = all(center_reliable[i] for i in [start, start + 1, end - 1, end]) and speed > 1e-12
            bend = ((norm(tuple(a - b for a, b in zip(across, before)))
                     + norm(tuple(a - b for a, b in zip(after, across)))) / (2 * speed)
                    if reliable else 2.0)
            context = (distance(end - 1, start) + distance(end, start + 1)) / (4 * typical)
            score = ratio + 0.7 * bend + 0.2 * context
            candidates.append({
                "start": start, "end": end,
                "duration_ms": elapsed[end + 1] - elapsed[start],
                "seam_ratio": round(ratio, 4), "velocity_change": round(bend, 4),
                "velocity_reliable": reliable,
                "score": round(score, 4),
                "rating": "good" if reliable and ratio <= 1.6 and bend <= 1.1 else "review",
            })
    candidates.sort(key=lambda item: (item["score"], -(item["end"] - item["start"])))
    selected = []
    for item in candidates:
        if all(abs(item["start"] - old["start"]) + abs(item["end"] - old["end"]) >= 3 for old in selected):
            selected.append(item)
        if len(selected) == 3:
            break
    return {
        "coverage": {"input_frames": len(images), "loop_samples": count,
                     "loop_positions": positions, "complete_loop_search": count == len(images)},
        "duplicates": {"threshold": duplicate_threshold, "keep_positions": kept,
                       "durations_ms": merged, "removed": removed,
                       "total_duration_ms": sum(durations)},
        "loop_candidates": selected,
        "typical_step_distance": round(statistics.median(steps), 6) if steps else 0,
        "notes": ["Suggestions require visual review; scores do not guarantee a seamless loop.",
                  "Duplicate proposals compare consecutive frames to the last kept frame and preserve hold time.",
                  "Loop search uses small alpha-aware images; sequences over 128 frames sample candidate boundaries.",
                  "Velocity uses the centroid of changes from a temporal median; unreliable estimates require review."],
    }
