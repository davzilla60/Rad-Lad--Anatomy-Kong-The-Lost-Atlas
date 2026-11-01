# Anatomy Kong: The Lost Atlas

A Rad-Lad retro jungle platformer that teaches anatomy. Dr Dissection has stolen the Atlas of Anatomy and scattered its pages across Anatomia; the great chapters are guarded by his five lieutenants. You play a radiographer who is pulled into this world to put it right.

## Now playable
- Intro cutscene: the theft at the Temple of Anatomia, the pages scattering, and the chapters handed to the lieutenants (skippable).
- World 1, Bone Island, Level 1-1 "Welcome to the Jungle": run, jump, roll attack, vine climbing, golden bone tokens, 2 Atlas pages, a lightbox checkpoint and an exit hut.
- Anatomy challenge: name the glowing bone at the plinth to rebuild the bone bridge.
- Markers: "A Bone to Pick" (bridge on your first answer) and "No Bones About It" (clear 1-1).

## Controls
Arrows/WASD run and climb, Z/Space jump, X/Shift roll, Up reads a plinth, Esc skips the intro. Touch: d-pad plus JUMP and ROLL buttons.

## Build
`game.html` is the source. `python tools/cut_concept.py` cuts the hero sprites and dialogue portraits out of `assets/concept/character_sheet.png` into `assets/sprites/`; `python build.py` then writes the self-contained `index.html` and `anatomy-kong.embed.html` (for Wix).

The game draws a 384x224 world at 2x resolution, so art can carry the finer detail of the concept sheet.

The hero sprites and dialogue portraits come from Rad-Lad's concept sheet; the world, enemies, props and cutscene sets are original art drawn in code.
