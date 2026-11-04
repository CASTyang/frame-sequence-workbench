"""Normalize frames and atomically publish a new build directory."""

import math
import os
import shutil
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from . import config as schema
from .analysis import analyze, visual_distance
from .exports import write
from .inputs import read


def prepare(sources, config):
    """Crop before alpha trimming; retain effective crop in original coordinates."""
    cropped, bounds = [], []
    for index, (_, original) in enumerate(sources):
        override = config["frames"].get(str(index), {})
        crop = override.get("crop", config.get("crop", [0, 0, original.width, original.height]))
        if crop[2] > original.width or crop[3] > original.height:
            raise ValueError(f"crop for source {index} extends beyond image bounds")
        image = original.crop(crop)
        effective = list(crop)
        ink = image.getchannel("A").getbbox()
        if config["trim"] and ink:
            image = image.crop(ink)
            effective = [crop[0] + ink[0], crop[1] + ink[1], crop[0] + ink[2], crop[1] + ink[3]]
        cropped.append(image)
        bounds.append(effective)
    return cropped, bounds


def normalize(sources, config, sequence, durations):
    boxes = [image.getchannel("A").getbbox() for _, image in sources]
    cropped, crop_bounds = prepare(sources, config)
    nonempty = [image for image in cropped if image.getchannel("A").getbbox()]
    width, height = config["canvas"]
    fit = min(
        width / max((i.width for i in nonempty), default=width),
        height / max((i.height for i in nonempty), default=height),
    )
    images, records, warnings = [], [], []
    opaque = [index for index, (_, image) in enumerate(sources) if image.getchannel("A").getextrema()[0] == 255]
    warnings.extend(f"source {index}: fully opaque; check background removal" for index in opaque)
    for position, (source_index, duration) in enumerate(zip(sequence, durations)):
        image = cropped[source_index]
        override = config["frames"].get(str(source_index), {})
        scale = fit * config["scale"] * override.get("scale", 1)
        size = max(1, round(image.width * scale)), max(1, round(image.height * scale))
        empty = image.getchannel("A").getbbox() is None
        if empty:
            # No pixels need resampling. A tiny visible subject can otherwise make
            # a blank source's nominal scaled rectangle exceed the image budget.
            size = (0, 0)
        if math.prod(size) > schema.MAX_PIXELS:
            raise ValueError("scaled frame exceeds pixel limit; reduce scale")
        source_anchor = override.get("anchor", config["anchor"])
        pixel_anchor = override.get("source_anchor", config.get("source_anchor"))
        if pixel_anchor is not None:
            crop = crop_bounds[source_index]
            source_anchor = [(pixel_anchor[0] - crop[0]) / image.width, (pixel_anchor[1] - crop[1]) / image.height]
        target_anchor = override.get("target_anchor", config["target_anchor"])
        offset = [a + b for a, b in zip(config["offset"], override.get("offset", [0, 0]))]
        x = round(width * target_anchor[0] - size[0] * source_anchor[0] + offset[0])
        y = round(height * target_anchor[1] - size[1] * source_anchor[1] + offset[1])
        frame = Image.new("RGBA", (width, height))
        ink = None
        if not empty:
            method = Image.Resampling.NEAREST if config["resample"] == "nearest" else Image.Resampling.LANCZOS
            resized = image.resize(size, method)
            frame.paste(resized, (x, y))
            ink = resized.getchannel("A").getbbox()
        bbox = frame.getchannel("A").getbbox()
        clipped = bool(ink and (x + ink[0] < 0 or y + ink[1] < 0 or x + ink[2] > width or y + ink[3] > height))
        if boxes[source_index] is None:
            warnings.append(f"frame {position}: empty source alpha")
        elif image.getchannel("A").getbbox() is None:
            warnings.append(f"frame {position}: explicit crop contains no visible pixels")
        if clipped:
            warnings.append(f"frame {position}: visible pixels clipped by canvas")
        records.append(
            {
                "index": position,
                "source_index": source_index,
                "source_name": sources[source_index][0],
                "duration_ms": duration,
                "file": f"frames/{position:04d}.png" if "png" in config["exports"] else None,
                "source_bounds": boxes[source_index],
                "crop_bounds": crop_bounds[source_index],
                "alpha_bounds": bbox,
                "placement": [x, y],
                "scaled_size": list(size),
                "clipped": clipped,
            }
        )
        images.append(frame)
    manifest = {
        "schema_version": 1,
        "action_id": config["action_id"],
        "loop": config["loop"],
        "canvas": config["canvas"],
        "frame_count": len(images),
        "total_duration_ms": sum(durations),
        "fit_scale": fit,
        "exports": config["exports"],
        "resample": config["resample"],
        "frames": records,
    }
    difference = ImageStat.Stat(ImageChops.difference(images[-1], images[0]))
    quality = {
        "schema_version": 1,
        "frame_count": len(images),
        "warnings": warnings,
        "checks": {
            "aspect_preserved": True,
            "empty_frames": sum(r["alpha_bounds"] is None for r in records),
            "clipped_frames": sum(r["clipped"] for r in records),
            "opaque_sources": len(opaque),
        },
        "metrics": {"loop_rgba_mae": sum(difference.mean) / 4 / 255, "loop_alpha_mae": difference.mean[3] / 255},
        "notes": [
            "Loop differences are normalized 0..1 diagnostics, not a perceptual motion-quality score.",
            "QA detects empty alpha, opaque sources and geometric clipping; it does not assess anatomy or motion quality.",
        ],
    }
    quality["metrics"]["loop_premultiplied_distance"] = visual_distance(images[-1], images[0])
    quality["analysis"] = None
    if config["analysis"]["enabled"]:
        report = analyze(images, durations, config["analysis"]["duplicate_threshold"])
        proposal = report["duplicates"]
        patch_sequence, patch_durations = [], []
        for position, duration in zip(proposal["keep_positions"], proposal["durations_ms"]):
            # Split merged holds to retain the schema's 10..60000 ms range.
            parts = math.ceil(duration / 60000)
            base, remainder = divmod(duration, parts)
            patch_sequence.extend([sequence[position]] * parts)
            patch_durations.extend([base + (i < remainder) for i in range(parts)])
        proposal["config_patch"] = {"sequence": patch_sequence, "durations_ms": patch_durations}
        quality["analysis"] = report
    return images, manifest, quality


def build(config_path, output_dir):
    """Build from a JSON file into a previously nonexistent directory; return manifest."""
    config = schema.load(config_path)
    output = Path(output_dir).absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"output already exists: {output}")
    output = output.resolve()
    source = config["source"]["path"]
    if (
        output == source
        or output in source.parents
        or (config["source"]["type"] == "directory" and source in output.parents)
    ):
        raise ValueError("output must not overlap input")
    sources = read(config["source"])
    sequence, durations = schema.timeline(config, len(sources))
    images, manifest, quality = normalize(sources, config, sequence, durations)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    try:
        write(staging, images, config, manifest, quality, [image for _, image in sources])
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"output already exists: {output}")
        for attempt in range(5):
            try:
                os.rename(staging, output)
                break
            except PermissionError:
                if attempt == 4 or output.exists():
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest
