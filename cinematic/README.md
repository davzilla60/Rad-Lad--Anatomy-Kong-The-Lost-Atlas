# Opening cutscene in 3D: "The Theft of the Atlas"

This folder holds the Blender work that will replace the code-drawn opening cinematic in `game.html` (`introCutscene()`, the section headed `OPENING CINEMATIC`). The cinematic is rendered in Blender to a video. The game plays it and keeps its own subtitles, score and Skip button over the top.

## Status

- `prototype/vault.py` builds a 12.5-second test of scene 2: Dr Dissection walks to the pedestal and takes the Atlas.
- `prototype/vault-prototype.mp4` is that test, rendered on CPU at 384x216 and scaled up 3x.
- The prototype's characters are built from primitives in code. They are placeholders and will be replaced in the full version.

## Running Blender from the command line (Windows)

Blender 5.2 or newer is needed. From this folder:

```
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python prototype\vault.py -- --still 200
```

The flags after `--` belong to the script:

| Flag | Effect |
|---|---|
| (none) | Build the scene and save `vault.blend`. Open it in Blender to look around. |
| `--still 60,200` | Render those frames to `stills/`. |
| `--anim` | Render every frame to `frames/`. |
| `--clean` | Render at 1152x648 with more samples. |

On a machine with a graphics card, set Cycles to the GPU (OptiX for NVIDIA RTX, HIP for AMD) or use Eevee. Either is far faster than the CPU render used for the prototype.

## Goal: as good as possible

- **Characters:** real models of Dr Dissection and the radiographer that match `assets/concept/character_sheet.png`.
  - Model them by hand, or start from a generated or base mesh and refine it.
  - Rig them, with an armature, so walks, gestures and faces animate properly.
  - Toon or painterly shading with ink outlines, to stay true to the concept art.
- **Rendering:**
  - Volumetric light shafts and dust in the vault.
  - Proper particles for the swirling pages.
  - Depth of field, and motion blur on fast moves.
- **Output:**
  - A 1920x1080 master render.
  - A game version that is small enough to inline into the single-file build (see Game integration).

## The lieutenants must stay anonymous

When Dr Dissection says each lieutenant holds a collection of pages (scene 5), five silhouettes appear. They must not give away who the lieutenants are.

- All five are plain black silhouettes against a backlight. There are no faces, costumes, props or colours on the figures themselves.
- They share the same generic hooded or cloaked humanoid build, with only small changes in height and stance. Nothing hints at a body system: no skulls, muscles, hearts or brains.
- They stand half-lost in fog or behind a haze, softly out of focus, so the outlines stay vague.
- The only link to the five chapters is the order they appear in, timed to "the bones, the muscles, the vessels, the brain... and all those wonderfully complicated organs". Each one fades in on its word. Any coloured glow is a dim, neutral rim light that is the same for all five.

## The script (from `introCutscene()` in game.html)

| Scene | Action and dialogue |
|---|---|
| 1. The Grand Vault | The camera moves down a long corridor to a golden vault door. Six bolts unlock one by one, then the door grinds open and light spills out. Dr Dissection walks in silhouette and disappears into the light. Caption: "Dr Dissection has arrived." |
| 2. The Atlas | Inside the vault, the Atlas floats over a pedestal in a beam of light, above a glowing floor glyph. Dr Dissection adjusts his glasses. **Doc:** "At last... the Atlas of Anatomy." He reaches out, the book flickers, he takes it, and the beam and glyph die in a pulse. **Doc:** "Centuries of knowledge... and they kept it locked away in a basement." He looks left and right. **Doc:** "How terribly unimaginative." |
| 3. The radiographer arrives | The radiographer runs in. **Hero:** "Stop! Put that book back!" **Doc:** "Oh, I'm afraid you're a little late." "Although, I must admit... I'm impressed you made it this far." "Unfortunately, our little tour of the vault has reached its conclusion." |
| 4. The scattering | Doc opens the book with a flourish. Pages lift and orbit him, and the wind pushes the hero back. **Hero:** "What are you doing?!" **Doc:** "Oh, merely reorganising the curriculum!" He flicks his wrist and the pages burst upward. Cut to the night sky of Anatomia: the pages streak out across the world toward distant landmarks. |
| 5. The lieutenants | Back in the vault, Doc brushes off his coat. **Doc:** "And there we have it. A rather comprehensive redistribution of anatomical knowledge." "The pages are now scattered across Anatomia." "Of course, I haven't left them entirely unattended." "Each of my lieutenants has been entrusted with a collection of pages." The five anonymous silhouettes appear, one per chapter: "The bones, the muscles, the vessels, the brain... and all those wonderfully complicated organs." He walks up to the hero. "So, if you wish to reclaim the Atlas..." "You'll have to find my lieutenants..." Close-up: "...and defeat every last one of them." |
| 6. The escape | A purple portal opens behind Doc. **Hero:** "You're not getting away with this!" Doc laughs. **Doc:** "My dear radiographer..." He adjusts his glasses. "You spend your days looking inside people." "Let's see how well you actually know what's in there." He backs toward the portal and points. "Oh, and do try not to break anything. The skeleton is rather difficult to put back together." He vanishes into the portal with the book, and the portal implodes. |
| 7. The adventure begins | The hero walks to the empty pedestal. One page is stuck under a stone. It flutters free into the hero's hands. **Hero:** "Well... this is going to be a long shift." The camera pulls back, the screen fades, and the title appears: ANATOMY KONG, THE LOST ATLAS. |

The radiographer has a female and a male version (`port_hero` and `port_hero_m`). Decide whether the cutscene shows one of them or is rendered twice.

## Game integration (after the render)

1. Render a game version at 384x216 or 768x432 and encode it as MP4 (H.264). At 384x216 the prototype came to about 23 KB a second, so 2 minutes is about 3 MB.
2. `build.py` inlines it as a data URI, the same way it handles the sprites. The single-file build grows from about 0.7 MB to about 4.5 MB.
3. In `game.html`:
   - `introCutscene()` plays the video in a `<video>` element over the canvas, scaled with `image-rendering: pixelated`.
   - The existing `line()` subtitles, `MUS` score and `SFX` cues are scheduled by the video's `currentTime`.
   - Skip and Esc end the video.
   - If the video fails to load, the current code-drawn cinematic plays instead.
4. A 1080p version is too big to inline. It would be hosted separately and loaded by URL.
