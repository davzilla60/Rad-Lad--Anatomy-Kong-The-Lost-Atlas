"""Build index.html / anatomy-kong.embed.html from game.html + assets/.

Everything in the game is drawn in code, so the build only inlines the
Rad-Lad logo for now. Real images for the anatomy challenges go here later.

Usage:  python build.py   -> index.html + anatomy-kong.embed.html (self-contained)
"""
import base64, json
from pathlib import Path

ROOT = Path(__file__).parent
A = ROOT / "assets"


def data_uri(p):
    mime = "image/png" if p.suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def main():
    assets = {"logo_mark": data_uri(A / "logo_mark.png")}
    src = (ROOT / "game.html").read_text(encoding="utf-8")
    out = src.replace("/*__ASSETS__*/{}", json.dumps(assets))
    for n in ("index.html", "anatomy-kong.embed.html"):
        (ROOT / n).write_text(out, encoding="utf-8")
    print(f"-> index.html, anatomy-kong.embed.html, {len(out)/1e6:.2f} MB")


if __name__ == "__main__":
    main()
