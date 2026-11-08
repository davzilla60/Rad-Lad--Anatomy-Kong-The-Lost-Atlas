# Opening cutscene in 3D: "The Theft of the Atlas"

This folder holds the Blender work that will replace the code-drawn opening cinematic in `game.html` (`introCutscene()`, the section headed `OPENING CINEMATIC`). The cinematic is rendered in Blender to a video. The game plays it and keeps its own subtitles, score and Skip button over the top.

## Status

- The `prototype/` files this README described (`vault.py`, `vault-prototype.mp4`) were not on this laptop or in the repo, so the full version started from scratch on 2026-11-03.
- **Characters (first pass done):** `characters/build_characters.py` builds Dr Dissection, the radiographer and the male radiographer variant entirely in code, then saves `characters/characters.blend`.
  - Each character has a full armature: spine, neck, head, clavicles, arms, hands with 3-bone fingers and thumb, legs, feet and toes, eye bones for gaze, and leg IK that is off by default.
  - Bodies, clothes, hair and props are skinned to the rig with smooth joint blends.
  - Faces use shape keys. Lids: `blink`, `blink.L/.R`, `wide`, `squint`, `narrow.L/.R`. Brows: `up`, `up.L/.R`, `angry`, `worried`. Mouth: `smile`, `smirk.L/.R`, `frown`, `open`, `grin`, `laugh`, `oh`. The named presets live in `EXPRESSIONS` in `doc.py` and `hero.py`. Doc's presets match the concept portraits: calculating, amused, frustrated, victorious.
  - Shading is a three-band cel material with purple-tinted shadows and inverted-hull ink outlines, rendered in Eevee. Face normals are softened toward a smooth head shape so the cel bands fall cleanly.
  - Review sheets are in `characters/renders/`: turnarounds, expression close-ups and a rig test pose for each character.
- **Vault set (first pass done, 2026-11-03):** `sets/vault.py` builds the set; `sets/build_vault.py` builds it with both characters, saves `sets/vault.blend` and renders test shots to `sets/renders/` (`--shots corridor,door,spill,vault,pedestal`).
  - **Corridor** (y 0 to 32, 7 m wide): blue-grey brick, arched niches with glowing blue anatomy glyphs above them, 10 torches, wooden ceiling beams, flagstones, and a stone voussoir arch with pillars round the round door.
  - **Vault door** (`VaultDoor` empty, radius 2.1 m): gold body with rings, rivets, a hub and a 4-spoke wheel. It has six separate bolt objects, `VaultDoor_Bolt0` to `VaultDoor_Bolt5`, which slide along their radial axis to unlock. The door rolls along +X into the wall; `DOOR['open_x']` is the open position.
  - **Tomb** (y 32.9 to 46, 14 m wide; made ancient 2026-11-03 at the user's request): worn, cracked, tilted sandstone blocks (`lib/stonework.py`), broken floor slabs with rubble, worn columns (one broken, its drums on the floor), a cracked slab ceiling with roots, and cobwebs. Arched alcoves hold scrolls, clay tablets, canopic jars and a skull. The altar sits under the oculus with its banded beam and dust, ringed by 12 gold floor glyphs that alternate anatomy and imaging symbols. The loose stone is beside it.
  - **The story on the walls** (`sets/ancient_art.py`, all painted pixel by pixel): the Atlas began as the first illustration of the inside of the body.
    - Its original, an ochre figure with skeleton and organs, is painted on flaking plaster behind the altar.
    - Gold threads run from its heart along its arms and out of its hands, round a frieze, and down to eight painted panels.
    - Left wall, anatomy through history: hand stencils, an Egyptian figure with canopic jars, a Greek figure with blood vessels, a Renaissance skeleton.
    - Right wall, imaging today: X-ray, CT, MRI and ultrasound.
  - **The door** has the same 12 pictographs engraved round its band. Its round shape already echoes a CT gantry.
  - **Atlas:** worn dark leather with a tooled border, the first illustration's figure in gilt, brass corners and clasp, `vault.atlas()`.
  - **Door spill:** the `DoorSpill` light pool is hidden until the door opens.
  - **Light shapes:** beams, glows, dust and glyph icons are banded, see-through shapes (`lib/lightfx.py`) tagged `px_skip_id`, so they colour the frame but never draw outlines.
- **The rest of the set pieces (2026-11-08):** `sets/extras.py` builds the loose pages (with glow trails), the purple portal (a dark core and five spinning rings), the five anonymous lieutenants (one hooded build for all, black on a neutral rim light, in haze) and the night sky of Anatomia (a pixel-painted backdrop with mountains, forest, glowing caves, castle and the temple).
- **Animation and render (2026-11-08):** `anim/cinematic.py` animates all seven scenes from one timeline in code. `apply(t)` sets the camera, poses (walk and run cycles, gestures), faces (expression presets, lip flap on each line, blinks), the bolts and rolling door, the beam and glyphs, the Atlas (it drifts to Doc's hand), the page vortex, burst and sky streaks, the portal and the lieutenants for any time `t`. Frames render at 12 fps (pixel-art "twos") through `lib/pixel.py` at 640x360. The script also writes `anim/timing.json`: the subtitles, the caption and the sound cues the game schedules against the video. The cutscene shows the female radiographer (the game's default hero).

```
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python anim\cinematic.py -- --stills 25,63,102
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python anim\cinematic.py -- --frames 0-1619
python anim\encode.py
```

`--frames` skips frames that already exist (add `--redo` to overwrite), so a range can be re-rendered after a fix by deleting just those frames. One frame takes about 1.5 s on the RTX 2070, so the full 135 s film is about 40 minutes.

### Pixel-art look

Renders go through `lib/pixel.py` so the 3D matches the game's 16-bit art:

1. Eevee renders at the low art resolution (for 1080p: 640x360) with anti-aliasing, dither and cast shadows off. Every pixel is one flat cel colour.
2. A second render switches every material to an emission that records the object index, material index and view depth.
3. Post-processing in numpy then does three things:
   - removes stray single pixels;
   - draws 1-pixel outlines: dark ink on silhouettes and where one thing passes in front of another, and a darker shade of the local colour (sel-out) where two parts of one surface meet or there is a small depth step, such as a nose over a cheek;
   - upscales with nearest-neighbour filtering (x3 by default).
4. Materials get three cel bands with purple shadows, plus a hard glossy highlight band on hair, glasses and shoes (`hl=` in `ak.toon`).

Two extra renders feed the line pass: an ID pass (object and material index) and a depth pass. The depth is split into coarse and fine channels, because Eevee's half-float buffers alone give about 5 mm depth steps at 10 m, which drew false hatching. Depth jumps are measured against the surface's own slope, so walls seen edge-on stay clean. Point, spot and sun lights are made hard during pixel renders.

Lines come from material boundaries. A part that needs its own line (a lapel, cuff, collar or neckline) gets its own material, even when it is the same colour. `pixel.noline()` marks small details that a line would swallow, such as glints, pupils and mouths. Add `--smooth` to `build_characters.py` for the old anti-aliased renders with inverted-hull ink.

### Character files

| File | What it is |
|---|---|
| `lib/akcore.py` | Toon/ink materials, mesh builders (tube, loft, MeshBuilder with weights), textures, render setup |
| `lib/humanoid.py` | Skeleton from a proportions dict, armature, body parts, sculpted head, eyes/lids/brows/mouth rig parts, hair clumps |
| `characters/doc.py` | Dr Dissection: proportions, materials, lab coat, glasses, hair, expressions |
| `characters/hero.py` | Radiographer (`'f'`, default) and male variant (`'m'`): scrubs, kit, backpack, hair, beard |
| `characters/build_characters.py` | Builds everything and saves the .blend. `--turn`, `--faces` and `--pose` render the review sheets; `--only doc\|hero\|hero_m` builds one |

```
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python characters\build_characters.py -- --turn --faces --pose
```

Rig axes, for posing in code: thigh and upper arm `+X` swing forward. Knees bend at `-X`, elbows at `+X`. Arms come down to the sides at `-Z` on `.L` and `+Z` on `.R`. Fingers curl at `-X`.

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

## Game integration (done 2026-11-08)

- `anim/encode.py` writes `anim/theft_of_the_atlas_game.mp4` (640x360, H.264 CRF 23, no audio) and a 1920x1080 nearest-neighbour master that stays out of git.
- The video is too large to inline at a quality that keeps the pixel edges, so the full build streams it from this repo through jsDelivr (`VIDEO_URL` in `build.py`). jsDelivr serves GitHub files up to 20 MB. `_preview.html` uses the local file.
- In `game.html`, `introCutscene()` plays the video over the stage (`videoCutscene()`) and schedules the subtitles, caption, sound effects and score from `CINE_TIMING` by `currentTime`. Skip and Esc end it, and a title card follows. If the video fails, the code-drawn cinematic (`codeCutscene()`) plays instead.
