"""Create original geometric characters; no external assets or fonts required."""

import math
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw


def main():
    output = Path(__file__).resolve().parent / "generated"
    output.mkdir(exist_ok=False)
    frames_dir = output / "frames"
    frames_dir.mkdir()
    sheet = Image.new("RGBA", (128 * 4, 128 * 2))
    for index in range(8):
        image = Image.new("RGBA", (128, 128))
        draw = ImageDraw.Draw(image)
        lift = round(15 * math.sin(index * math.pi / 4))
        draw.line([(44, 70), (22, 76)], fill="#194b69", width=9)
        draw.line([(83, 68), (104, 56 + lift)], fill="#194b69", width=9)
        draw.rounded_rectangle((39, 47, 89, 103), radius=16, fill="#46c9b2", outline="#194b69", width=3)
        draw.ellipse((43, 20, 85, 62), fill="#ffce70", outline="#194b69", width=3)
        draw.ellipse((54, 35, 58, 41), fill="#194b69")
        draw.ellipse((70, 35, 74, 41), fill="#194b69")
        draw.arc((57, 40, 72, 50), 0, 180, fill="#194b69", width=2)
        draw.rounded_rectangle((44, 97, 60, 113), radius=5, fill="#194b69")
        draw.rounded_rectangle((68, 97, 84, 113), radius=5, fill="#194b69")
        image.save(frames_dir / f"frame{index}.png")
        sheet.paste(image, ((index % 4) * 128, (index // 4) * 128))
    sheet.save(output / "sheet.png")
    with zipfile.ZipFile(output / "frames.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(frames_dir.glob("*.png")):
            archive.write(file, f"frames/{file.name}")
    print("Created 8 original frames, sheet.png and frames.zip in examples/generated")


if __name__ == "__main__":
    main()
