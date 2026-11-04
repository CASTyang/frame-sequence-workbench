"""Read PNG frames without extracting archive members."""

import io
import re
import warnings
import zipfile
from pathlib import PurePosixPath

from PIL import Image

from .config import MAX_BYTES, MAX_FRAMES, MAX_PIXELS, MAX_TOTAL_PIXELS


def natural(name):
    return tuple((1, int(part)) if part.isdigit() else (0, part.casefold()) for part in re.split(r"(\d+)", name))


def validate_numbering(names, allow_gaps):
    groups = {}
    for name in names:
        match = re.fullmatch(r"(.*?)([0-9]+)([^0-9]*)", name)
        if match:
            prefix, number, suffix = match.groups()
            groups.setdefault((prefix.casefold(), suffix.casefold()), []).append(int(number))
    for numbers in groups.values():
        if len(set(numbers)) != len(numbers):
            raise ValueError("duplicate numeric frame IDs (including zero-padding aliases)")
        if not allow_gaps and max(numbers) - min(numbers) + 1 != len(numbers):
            raise ValueError("missing frame numbers; set source.allow_gaps=true for intentional gaps")


def decode(stream):
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            with Image.open(stream) as image:
                if image.format != "PNG" or image.width * image.height > MAX_PIXELS:
                    raise ValueError("input must be PNG within 16,777,216 pixels")
                if getattr(image, "n_frames", 1) != 1:
                    raise ValueError("animated PNG input is unsupported; supply separate frames")
                return image.convert("RGBA")
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
            raise ValueError("image exceeds safe pixel limit") from error


def read(source):
    path = source["path"]
    frames = []
    total_pixels = 0

    def append(name, stream):
        nonlocal total_pixels
        if len(frames) >= MAX_FRAMES:
            raise ValueError("input exceeds 512 frames")
        image = decode(stream)
        total_pixels += image.width * image.height
        if total_pixels > MAX_TOTAL_PIXELS:
            raise ValueError("input exceeds total pixel limit")
        frames.append((name, image))

    if source["type"] == "directory":
        files = sorted(
            (p for p in path.iterdir() if p.suffix.lower() == ".png"), key=lambda p: (natural(p.name), p.name)
        )
        if len(files) > MAX_FRAMES or sum(p.stat().st_size for p in files) > MAX_BYTES:
            raise ValueError("directory exceeds input limits")
        validate_numbering([file.name for file in files], source["allow_gaps"])
        for file in files:
            if file.is_symlink() or not file.is_file():
                raise ValueError("PNG entries must be regular files, not symlinks")
            append(file.name, file)
    elif source["type"] == "zip":
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("ZIP exceeds 128 MiB")
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > 2048 or sum(m.file_size for m in members) > MAX_BYTES:
                raise ValueError("ZIP exceeds member or expanded size limit")
            names = set()
            for member in members:
                name = member.filename
                parts = PurePosixPath(name).parts
                if "\\" in name or ":" in name or name.startswith("/") or ".." in parts or name in names:
                    raise ValueError("unsafe or duplicate ZIP member name")
                names.add(name)
                mode = (member.external_attr >> 16) & 0o170000
                if mode == 0o120000 or member.flag_bits & 1:
                    raise ValueError("symlink/encrypted ZIP members are unsupported")
                if member.file_size > MAX_BYTES or member.file_size / max(member.compress_size, 1) > 1000:
                    raise ValueError("ZIP expansion ratio exceeds limit")
            validate_numbering(
                [m.filename for m in members if not m.is_dir() and m.filename.lower().endswith(".png")],
                source["allow_gaps"],
            )
            for member in sorted(members, key=lambda m: (natural(m.filename), m.filename)):
                if not member.is_dir() and member.filename.lower().endswith(".png"):
                    append(member.filename, io.BytesIO(archive.read(member)))
    else:
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("sheet exceeds 128 MiB")
        image = decode(path)
        width, height = source["cell"]
        if image.width % width or image.height % height:
            raise ValueError("sheet dimensions must be exact multiples of cell dimensions")
        columns, rows = image.width // width, image.height // height
        count = source.get("count", columns * rows)
        if not 1 <= count <= min(columns * rows, MAX_FRAMES):
            raise ValueError("sheet frame count is outside available cells or limits")
        for index in range(count):
            x, y = index % columns * width, index // columns * height
            frames.append((f"{path.name}#{index}", image.crop((x, y, x + width, y + height))))
    if not frames:
        raise ValueError("source contains no PNG frames")
    return frames
