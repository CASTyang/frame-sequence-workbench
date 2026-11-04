# Provider-neutral motion preparation

These templates are original workflow guidance, not vendor API syntax. Check the chosen model's actual reference-image, start/end-frame and duration support. Do not equate the words “transparent background” with an alpha-capable output format.

## Character brief

Record identity facts visible in the approved reference: silhouette, head/body ratio, clothing geometry, important colors and asymmetric details. Keep appearance constraints separate from motion. Do not add extra accessories or change the art style unless requested.

Example brief:

> Use the supplied character reference for the same face, head/body proportions, outfit and colors. Show the whole character, including both feet and the full movement of the hands. Keep the camera, character scale and planted feet fixed. The motion is a friendly right-hand wave: neutral pose, lift the arm, two small hand waves, lower the arm, return to the same neutral pose. Keep the torso steady. Use one continuous shot with no zoom or cuts.

For a pose sheet, describe an ordered grid and each pose's function; verify the actual grid rather than trusting generated labels. Ask for intermediate poses only where the movement requires them. Request clear separation between cells; remove text labels before export if the generator adds them.

## Short sample first

For a new generator/character pairing, test a representative motion before making every action. Look for identity drift during hand/head movement, limb deformation, off-canvas pixels and perspective changes. If a neutral pose and a wave have different proportions, correct the source or redraw the offending region; stretching horizontal bands is a character-specific repair, not a generally valid normalization.

## Common action structures

| Action | Enter | Main movement | Exit |
|---|---|---|---|
| Wave | Start from idle, raise one arm | Clear hand movement, stable shoulder and feet | Lower arm to idle |
| Celebration | Prepare with a small torso response | One readable clap or gesture | Relax without changing size |
| Surprise | Neutral | Short facial/body reaction, bounded displacement | Return to original standing anchor |
| Idle | Approved neutral | Small breathing/blink movement | Match the starting state naturally |

These are examples, not mandatory IDs or fixed durations. A walking cycle needs a separate locomotion contract (in-place or root motion); do not label a stationary wave as walking.

## Flattened video

Select a background unlike important costume colors if the generator cannot produce alpha. White medical uniforms on white backgrounds and blue decorations on blue backgrounds lose separability. Use matting and inspect foreground preservation, not only whether corners are transparent. Premultiplied-alpha resizing and downstream decoder assumptions can affect edges; verify the actual final exported file on several backgrounds.

Generation quality and temporal stability remain visual judgments. Stop repeating parameter tweaks when the input lacks recoverable detail; request better source material or describe the manual corrections still needed.
