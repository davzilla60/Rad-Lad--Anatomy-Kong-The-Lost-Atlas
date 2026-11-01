"""Build index.html / anatomy-kong.embed.html from game.html + assets/.

The world art is drawn in code. The build inlines the Rad-Lad logo and the
sprites/portraits cut from the concept sheet (run tools/cut_concept.py first).

Usage:  python build.py            -> index.html + anatomy-kong.embed.html (self-contained)
        python build.py --preview  -> _preview.html (references assets/ files; for local testing,
                                      because this machine's local server stalls on large files)
"""
import base64, json, sys
from pathlib import Path

ROOT = Path(__file__).parent
A = ROOT / "assets"


def data_uri(p):
    mime = "image/png" if p.suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def main():
    preview = "--preview" in sys.argv
    ref = (lambda f: f.relative_to(ROOT).as_posix()) if preview else data_uri
    assets = {"logo_mark": ref(A / "logo_mark.png")}
    for f in sorted((A / "sprites").glob("*.png")):
        assets[f.stem] = ref(f)
    src = (ROOT / "game.html").read_text(encoding="utf-8")
    out = src.replace("/*__ASSETS__*/{}", json.dumps(assets))
    names = ["_preview.html"] if preview else ["index.html", "anatomy-kong.embed.html"]
    for n in names:
        (ROOT / n).write_text(out, encoding="utf-8")
    print(f"-> {', '.join(names)}, {len(out)/1e6:.2f} MB")


if __name__ == "__main__":
    main()
