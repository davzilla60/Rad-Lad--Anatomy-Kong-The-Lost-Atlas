# Anatomy Kong: The Lost Atlas

A Rad-Lad retro jungle platformer that teaches anatomy. Dr Dissection has stolen the Atlas of Anatomy and scattered its pages across Anatomia; the great chapters are guarded by his five lieutenants. You play a radiographer who is pulled into this world to put it right.

## Now playable
- Opening cinematic, "The Theft of the Atlas" (about 2 minutes, skippable): the corridor and golden vault door, Dr Dissection taking the Atlas, the radiographer's arrival, the pages swirling and bursting across the night sky of Anatomia, the lieutenants, Dr Dissection's portal exit, and the last page landing in the radiographer's hands. Letterboxed, with camera moves, auto-advancing subtitles, close-up panels from the concept art, and a synthesised score.
- World 1, Bone Island, Level 1-1 "Welcome to the Jungle": run, jump, roll attack, vine climbing, golden bone tokens, 2 Atlas pages, a lightbox checkpoint and an exit hut.
- Anatomy challenge: name the glowing bone at the plinth to rebuild the bone bridge.
- Enemy quizzes: bump into an enemy and it asks a Bone Island anatomy question (`QBANK` in game.html). Right defeats it; wrong costs a heart, shows the answer, and the enemy stays.
- Markers: "A Bone to Pick" (bridge on your first answer) "No Bones About It" (clear 1-1) and "Anatomically Correct" (clear 1-1 with no wrong enemy answers).

## Controls
Arrows/WASD run and climb, Z/Space jump, X/Shift roll (for speed; it no longer defeats enemies), Up reads a plinth, Esc skips the intro. Touch: d-pad plus JUMP and ROLL buttons.

## Build
`game.html` is the source. `python tools/cut_concept.py` cuts the hero sprites and dialogue portraits out of `assets/concept/character_sheet.png` into `assets/sprites/`; `python build.py` then writes the self-contained `index.html` and `anatomy-kong.embed.html` (for Wix).

The game draws a 384x224 world at 3x resolution (1152x672), so art can carry the finer detail of the concept sheet. `python build.py --preview` writes `_preview.html`, which loads images as separate files, for testing on a local server.

The hero sprites and dialogue portraits come from Rad-Lad's concept sheet; the world, enemies, props and cutscene sets are original art drawn in code.
