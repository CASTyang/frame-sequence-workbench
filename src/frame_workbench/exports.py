"""Image formats, editable layers, and a completely offline preview."""

import base64
import io
import json
import math
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image

from .config import MAX_TOTAL_PIXELS


def png_bytes(image):
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def openraster(path, images):
    root = ET.Element("image", w=str(images[0].width), h=str(images[0].height), name="Frame sequence", version="0.0.3")
    stack = ET.SubElement(root, "stack")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "image/openraster", compress_type=zipfile.ZIP_STORED)
        for index, image in enumerate(images):
            name = f"data/frame{index:04d}.png"
            archive.writestr(name, png_bytes(image))
            ET.SubElement(
                stack,
                "layer",
                {
                    "name": f"Frame {index:04d}",
                    "src": name,
                    "x": "0",
                    "y": "0",
                    "opacity": "1.0",
                    "visibility": "visible" if index == 0 else "hidden",
                    "composite-op": "svg:src-over",
                },
            )
        archive.writestr("stack.xml", ET.tostring(root, encoding="utf-8", xml_declaration=True))
        archive.writestr("mergedimage.png", png_bytes(images[0]))
        thumbnail = images[0].copy()
        thumbnail.thumbnail((256, 256))
        archive.writestr("Thumbnails/thumbnail.png", png_bytes(thumbnail))


def gif_frame(image):
    # Reserve palette entry 255 for binary transparency; GIF cannot retain soft alpha.
    palette = image.convert("RGB").quantize(colors=255)
    palette.putpalette((palette.getpalette() or [])[:765] + [0, 0, 0])
    mask = image.getchannel("A").point(lambda alpha: 255 if alpha < 128 else 0)
    palette.paste(255, mask=mask)
    palette.info["transparency"] = 255
    return palette


def write(output, images, config, manifest, quality, originals):
    formats = config["exports"]
    encoded = [png_bytes(image) for image in images]
    if "png" in formats:
        (output / "frames").mkdir()
        for index, data in enumerate(encoded):
            (output / f"frames/{index:04d}.png").write_bytes(data)
    if "sheet" in formats:
        columns = min(config["sheet_columns"], len(images))
        rows = math.ceil(len(images) / columns)
        width, height = config["canvas"]
        if width * height * columns * rows > MAX_TOTAL_PIXELS:
            raise ValueError("spritesheet including padding exceeds total pixel limit")
        sheet = Image.new("RGBA", (columns * width, rows * height))
        for index, image in enumerate(images):
            sheet.paste(image, (index % columns * width, index // columns * height))
        sheet.save(output / "sheet.png")
        manifest["sheet"] = {"file": "sheet.png", "columns": columns, "rows": rows, "cell": config["canvas"]}
    durations = [frame["duration_ms"] for frame in manifest["frames"]]
    if "gif" in formats:
        frames = [gif_frame(image) for image in images]
        frames[0].save(
            output / "animation.gif",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            **({"loop": 0} if config["loop"] == "infinite" else {}),
            disposal=2,
            transparency=255,
            optimize=False,
        )
    if "webp" in formats:
        images[0].save(
            output / "animation.webp",
            save_all=True,
            append_images=images[1:],
            duration=durations,
            loop=0 if config["loop"] == "infinite" else 1,
            lossless=True,
            method=4,
        )
    if "ora" in formats:
        openraster(output / "layers.ora", images)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "quality.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
    if quality["analysis"]:
        (output / "suggested-config.json").write_text(
            json.dumps(quality["analysis"]["duplicates"]["config_patch"], indent=2), encoding="utf-8"
        )
    payload = {
        "frames": ["data:image/png;base64," + base64.b64encode(data).decode("ascii") for data in encoded],
        "durations": durations,
        "loop": config["loop"],
        "action_id": config["action_id"],
        "analysis": quality["analysis"],
        "source_indices": [record["source_index"] for record in manifest["frames"]],
        "originals": [
            "data:image/png;base64," + base64.b64encode(png_bytes(image)).decode("ascii") for image in originals
        ],
    }
    (output / "preview.html").write_text(PREVIEW.replace("__PAYLOAD__", json.dumps(payload)), encoding="utf-8")


PREVIEW = r"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Frame Sequence Workbench — Preview</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#101925;color:#edf2f7;font:16px system-ui,sans-serif}
main{max-width:1000px;margin:auto;padding:32px 24px}h1{font-size:28px;margin-bottom:8px}p{color:#b3c4d6}
.stage{height:55vh;min-height:240px;display:grid;place-items:center;border-radius:16px;margin:24px 0;overflow:auto}
.comparison{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.comparison section{min-width:0}.comparison h2{font-size:16px;font-weight:500}.comparison .stage{margin-top:12px}@media(max-width:600px){.comparison{grid-template-columns:1fr}.comparison .stage{height:30vh;min-height:180px}.comparison .stage img{max-height:28vh}}
.checker{background:conic-gradient(#cdd4dc 25%,#f2f4f7 0 50%,#cdd4dc 0 75%,#f2f4f7 0) 0 0/24px 24px}
.light{background:#fff}.dark{background:#19212c}.stage img{max-width:95%;max-height:50vh;object-fit:contain;image-rendering:pixelated}
.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap}button,select{padding:10px 14px;border:1px solid #456078;border-radius:8px;background:#22374c;color:white;font:inherit}input{flex:1;min-width:120px}output{font-variant-numeric:tabular-nums}button:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid #65dbce}footer{margin-top:28px;color:#9cb0c5;font-size:14px}
.review{margin-top:28px;padding:20px;border:1px solid #456078;border-radius:12px}.review h2{margin-top:0;font-size:20px}.review select{max-width:100%}.review a{display:inline-block;color:#65dbce;margin-top:12px}.review [hidden]{display:none}details{margin-top:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}button:disabled{opacity:.5}
</style><main><h1>Frame Sequence Workbench</h1><p>Inspect alignment, alpha edges, and timing. This preview works offline.</p>
<p id="action"></p><div class="comparison"><section><h2>Original source</h2><div class="stage checker" id="source-stage"><img id="original" alt="Original source frame before processing"></div></section>
<section><h2>Processed output</h2><div class="stage checker" id="stage"><img id="frame" alt="Current animation frame"></div></section></div>
<div class="controls"><button id="play" type="button">Pause</button><label for="scrub">Frame</label><input id="scrub" type="range" min="0" value="0" step="1"><output id="status" aria-live="off"></output>
<label for="background">Background</label><select id="background"><option value="checker">Checker</option><option value="light">Light</option><option value="dark">Dark</option></select>
<label for="speed">Speed</label><select id="speed"><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option></select>
<label for="zoom">Zoom</label><select id="zoom"><option value="fit">Fit</option><option value="1">100%</option><option value="2">200%</option><option value="4">400%</option></select></div>
<section class="review" aria-labelledby="review-title"><h2 id="review-title">Motion review</h2>
<p id="analysis-status"></p><p id="duplicate-summary"></p>
<label for="loop-range">Preview range</label> <select id="loop-range"><option value="full">Full sequence</option></select>
<p id="range-detail">Range selection affects this preview only.</p>
<a id="download-proposal" download="suggested-config.json" hidden>Download timing-preserving config patch</a>
<details id="duplicate-details" hidden><summary>Inspect proposed removals</summary><pre id="duplicate-list"></pre></details>
<p>Review at the intended display size. A low score does not guarantee a seamless loop. Merge an accepted patch into your original JSON and build into a new directory.</p></section>
<footer>PNG and WebP preserve alpha. GIF has 256 colors and binary transparency; frame timing may be quantized by the encoder.</footer></main>
<script>
const data=__PAYLOAD__;
const frame=document.getElementById('frame'), original=document.getElementById('original'), scrub=document.getElementById('scrub'), status=document.getElementById('status'), play=document.getElementById('play'), speed=document.getElementById('speed');
let index=0, playing=true, ended=false, timer, rangeStart=0, rangeEnd=data.frames.length-1;
scrub.max=data.frames.length-1;
document.getElementById('action').textContent=data.action_id+' · '+(data.loop==='once'?'Play once':'Infinite loop');
function show(){frame.src=data.frames[index];original.src=data.originals[data.source_indices[index]];scrub.value=index;status.textContent=`${index+1} / ${data.frames.length} · ${data.durations[index]} ms`;}
function schedule(){clearTimeout(timer);if(playing&&!document.hidden)timer=setTimeout(()=>{if(index===rangeEnd&&data.loop==='once'&&document.getElementById('loop-range').value==='full'){playing=false;ended=true;play.textContent='Replay';return;}index=index===rangeEnd?rangeStart:index+1;show();schedule();},data.durations[index]/Number(speed.value));}
play.onclick=()=>{if(ended){index=rangeStart;ended=false;show();}playing=!playing;play.textContent=playing?'Pause':'Play';schedule();};
scrub.oninput=()=>{index=Number(scrub.value);playing=false;ended=false;play.textContent='Play';show();schedule();};
speed.onchange=schedule;
document.getElementById('background').onchange=event=>{for(const stage of document.querySelectorAll('.stage'))stage.className='stage '+event.target.value;};
function applyZoom(){const value=document.getElementById('zoom').value;for(const image of [frame,original]){image.style.maxWidth=value==='fit'?'95%':'none';image.style.maxHeight=value==='fit'?'':'none';image.style.width=value==='fit'?'auto':(image.naturalWidth*Number(value))+'px';}}
document.getElementById('zoom').onchange=applyZoom;frame.onload=applyZoom;original.onload=applyZoom;
document.addEventListener('visibilitychange',()=>{if(document.hidden)clearTimeout(timer);else schedule();});
const range=document.getElementById('loop-range');
if(data.analysis){
 const report=data.analysis, proposal=report.duplicates, coverage=report.coverage;
 document.getElementById('analysis-status').textContent=coverage.complete_loop_search?'All frame boundaries searched for loop candidates.':'Loop search sampled '+coverage.loop_samples+' of '+coverage.input_frames+' boundaries; other ranges may be better.';
 document.getElementById('duplicate-summary').textContent=proposal.removed.length+' adjacent frames proposed for removal; total hold time stays '+proposal.total_duration_ms+' ms. Exported frames are unchanged.';
 const download=document.getElementById('download-proposal');
 download.hidden=false;download.href=URL.createObjectURL(new Blob([JSON.stringify(proposal.config_patch,null,2)],{type:'application/json'}));
 document.getElementById('duplicate-details').hidden=proposal.removed.length===0;
 document.getElementById('duplicate-list').textContent=proposal.removed.map(item=>'Frame '+(item.position+1)+' → hold frame '+(item.kept_position+1)+' · distance '+item.distance).join('\n');
 report.loop_candidates.forEach((item,i)=>{const option=document.createElement('option');option.value=String(i);option.textContent='Frames '+(item.start+1)+'–'+(item.end+1)+' · '+(item.rating==='good'?'Lower seam':'Review seam');range.append(option);});
 if(!report.loop_candidates.length)document.getElementById('range-detail').textContent='No moving loop candidates found. Full sequence remains available.';
}else{document.getElementById('analysis-status').textContent='Motion analysis is disabled for this build.';}
range.onchange=()=>{
 const item=range.value==='full'?null:data.analysis.loop_candidates[Number(range.value)];
 rangeStart=item?item.start:0;rangeEnd=item?item.end:data.frames.length-1;
 scrub.min=rangeStart;scrub.max=rangeEnd;index=rangeStart;ended=false;playing=true;play.textContent='Pause';
 document.getElementById('range-detail').textContent=item?'Preview only · seam / typical step '+item.seam_ratio+' · velocity change '+(item.velocity_reliable?item.velocity_change:'unavailable')+' · '+item.duration_ms+' ms':'Full sequence. Range selection affects this preview only.';
 show();schedule();
};
show();schedule();
</script></html>"""
