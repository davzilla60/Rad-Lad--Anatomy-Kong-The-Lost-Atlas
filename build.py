"""Build index.html / anatomy-kong.embed.html from game.html + assets/.

The world art is drawn in code. The build inlines the Rad-Lad logo, the
sprites/portraits cut from the concept sheet (run tools/cut_concept.py first)
and, when it has been rendered, the 3D opening cinematic's subtitle/sound
timing (cinematic/anim); the video itself is linked, not inlined (VIDEO_URL).

Usage:  python build.py            -> index.html + anatomy-kong.embed.html (self-contained)
        python build.py --preview  -> _preview.html (references assets/ files; for local testing,
                                      because this machine's local server stalls on large files)
"""
import base64, json, sys
from pathlib import Path

ROOT = Path(__file__).parent
A = ROOT / "assets"


CINE = ROOT / "cinematic" / "anim"
VIDEO = CINE / "theft_of_the_atlas_game.mp4"     # made by cinematic/anim/encode.py
# The video is too big to inline at a quality that keeps the pixel edges, so the
# full build streams it from the repo through jsDelivr (it serves GitHub files
# with the right video type). If it can't load, the game plays the code-drawn
# cinematic instead. The preview build uses the local file.
VIDEO_URL = ("https://cdn.jsdelivr.net/gh/davzilla60/Rad-Lad--Anatomy-Kong-The-Lost-Atlas@main/"
             "cinematic/anim/theft_of_the_atlas_game.mp4")


def data_uri(p):
    mime = {".png": "image/png", ".mp4": "video/mp4"}.get(p.suffix, "image/jpeg")
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def main():
    preview = "--preview" in sys.argv
    ref = (lambda f: f.relative_to(ROOT).as_posix()) if preview else data_uri
    assets = {"logo_mark": ref(A / "logo_mark.png")}
    for f in sorted((A / "sprites").glob("*.png")):
        assets[f.stem] = ref(f)
    timing = "null"
    if VIDEO.exists() and (CINE / "timing.json").exists():
        assets["cine_video"] = VIDEO.relative_to(ROOT).as_posix() if preview else VIDEO_URL
        timing = json.dumps(json.loads((CINE / "timing.json").read_text(encoding="utf-8")))
    src = (ROOT / "game.html").read_text(encoding="utf-8")
    out = src.replace("/*__ASSETS__*/{}", json.dumps(assets)).replace("/*__CINE_TIMING__*/null", timing)
    names = ["_preview.html"] if preview else ["index.html", "anatomy-kong.embed.html"]
    for n in names:
        (ROOT / n).write_text(out, encoding="utf-8")
    print(f"-> {', '.join(names)}, {len(out)/1e6:.2f} MB")


if __name__ == "__main__":
    main()
