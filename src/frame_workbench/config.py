"""Strict, bounded JSON configuration."""

import json
import math
import re
from pathlib import Path

MAX_FRAMES = 512
MAX_PIXELS = 16_777_216
MAX_TOTAL_PIXELS = 67_108_864
MAX_BYTES = 134_217_728


def keys(value, allowed, label):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError(f"{label}: expected object with keys {sorted(allowed)}")


def number(value, label, low, high, integer=False):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or (isinstance(value, float) and not math.isfinite(value))
    ):
        raise ValueError(f"{label}: expected finite number")
    if not low <= value <= high or (integer and not isinstance(value, int)):
        raise ValueError(f"{label}: expected {'integer ' if integer else ''}in [{low}, {high}]")
    return value


def pair(value, label, low, high, integer=False):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label}: expected two numbers")
    return [number(v, label, low, high, integer) for v in value]


def anchor(value):
    names = {"bottom-center": [0.5, 1], "center": [0.5, 0.5], "top-left": [0, 0]}
    if isinstance(value, str):
        if value not in names:
            raise ValueError("unknown anchor name")
        return names[value]
    return pair(value, "anchor", 0, 1)


def transform(value):
    if "crop" in value:
        bounds = value["crop"]
        if not isinstance(bounds, list) or len(bounds) != 4:
            raise ValueError("crop must be [left, top, right, bottom]")
        for coordinate in bounds:
            number(coordinate, "crop coordinate", 0, MAX_PIXELS, True)
        if bounds[0] >= bounds[2] or bounds[1] >= bounds[3]:
            raise ValueError("crop must have positive width and height")
    if "source_anchor" in value:
        pair(value["source_anchor"], "source_anchor", 0, 16384)
    for key in ["anchor", "target_anchor"]:
        if key in value:
            value[key] = anchor(value[key])
    if "scale" in value:
        number(value["scale"], "scale", 0.001, 16)
    if "offset" in value:
        pair(value["offset"], "offset", -16384, 16384)


def load(path):
    path = Path(path).resolve()
    if path.stat().st_size > 1_048_576:
        raise ValueError("configuration exceeds 1 MiB")
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    keys(
        config,
        {
            "source",
            "canvas",
            "trim",
            "anchor",
            "source_anchor",
            "target_anchor",
            "scale",
            "offset",
            "frames",
            "sequence",
            "duration_ms",
            "durations_ms",
            "sheet_columns",
            "exports",
            "action_id",
            "loop",
            "crop",
        },
        "config",
    )
    source = config.get("source")
    action_id = config.setdefault("action_id", "animation")
    if not isinstance(action_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", action_id):
        raise ValueError(
            "action_id must be 1..64 ASCII letters/digits, underscores or hyphens, starting with a letter/digit"
        )
    if config.setdefault("loop", "infinite") not in ["infinite", "once"]:
        raise ValueError("loop must be infinite or once")
    keys(source, {"type", "path", "cell", "count", "allow_gaps"}, "source")
    if not isinstance(source.setdefault("allow_gaps", False), bool):
        raise ValueError("source.allow_gaps must be boolean")
    if (
        source.get("type") not in ["directory", "zip", "sheet"]
        or not isinstance(source.get("path"), str)
        or not source["path"]
    ):
        raise ValueError("source requires type and nonempty path")
    source["path"] = (path.parent / source["path"]).resolve()
    if source["type"] == "sheet":
        pair(source.get("cell"), "source.cell", 1, 8192, True)
        if "count" in source:
            number(source["count"], "source.count", 1, MAX_FRAMES, True)
    elif "cell" in source or "count" in source:
        raise ValueError("cell/count only apply to sheet inputs")
    config.setdefault("canvas", [256, 256])
    pair(config["canvas"], "canvas", 1, 8192, True)
    if math.prod(config["canvas"]) > MAX_PIXELS:
        raise ValueError("canvas exceeds pixel limit")
    config.setdefault("trim", True)
    if not isinstance(config["trim"], bool):
        raise ValueError("trim must be boolean")
    config.setdefault("anchor", "bottom-center")
    config.setdefault("target_anchor", "bottom-center")
    config.setdefault("scale", 1)
    config.setdefault("offset", [0, 0])
    transform(config)
    overrides = config.setdefault("frames", {})
    if not isinstance(overrides, dict):
        raise ValueError("frames must be an object keyed by source index")
    for key, value in overrides.items():
        if not key.isascii() or not key.isdecimal() or str(int(key)) != key:
            raise ValueError("frame keys must be canonical zero-based indices")
        keys(value, {"anchor", "source_anchor", "target_anchor", "scale", "offset", "crop"}, "frame transform")
        transform(value)
    number(config.setdefault("duration_ms", 100), "duration_ms", 10, 60000, True)
    number(config.setdefault("sheet_columns", 8), "sheet_columns", 1, MAX_FRAMES, True)
    exports = config.setdefault("exports", ["png", "sheet", "gif", "webp"])
    if (
        not isinstance(exports, list)
        or any(x not in ["png", "sheet", "gif", "webp", "ora"] for x in exports)
        or len(set(exports)) != len(exports)
    ):
        raise ValueError("exports must be a list of unique supported formats")
    return config


def timeline(config, count):
    sequence = config.get("sequence", list(range(count)))
    if not isinstance(sequence, list) or not 1 <= len(sequence) <= MAX_FRAMES:
        raise ValueError("sequence must contain 1..512 source indices")
    for index in sequence:
        number(index, "sequence index", 0, count - 1, True)
    if any(int(key) >= count for key in config["frames"]):
        raise ValueError("frame override references missing source index")
    durations = config.get("durations_ms", [config["duration_ms"]] * len(sequence))
    if not isinstance(durations, list) or len(durations) != len(sequence):
        raise ValueError("durations_ms must match sequence length")
    for duration in durations:
        number(duration, "duration", 10, 60000, True)
    if "gif" in config["exports"] and sum(durations) > 655350:
        raise ValueError(
            "GIF export requires total duration <=655350 ms because identical frames may merge; disable GIF or shorten the sequence"
        )
    if math.prod(config["canvas"]) * len(sequence) > MAX_TOTAL_PIXELS:
        raise ValueError("output sequence exceeds total pixel limit")
    return sequence, durations
