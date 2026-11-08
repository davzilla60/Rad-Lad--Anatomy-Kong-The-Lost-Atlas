"""Encode the rendered frames (anim/frames/f####.png, 12 fps) into:

  theft_of_the_atlas_game.mp4   640x360, one pixel per art pixel; the game streams it (keep it under 20 MB for jsDelivr)
  theft_of_the_atlas_1080p.mp4  1920x1080 master, nearest-neighbour x3 so the pixels stay crisp

  python cinematic/anim/encode.py [--game-only]

Needs ffmpeg on PATH (winget install Gyan.FFmpeg). No audio: the game plays the
score and effects itself, timed from timing.json.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 12


def ffmpeg():
    exe = shutil.which('ffmpeg')
    if not exe:
        sys.exit('ffmpeg not found on PATH')
    return exe


def run(args):
    print(' '.join(args))
    subprocess.run(args, check=True)


def main():
    src = os.path.join(HERE, 'frames', 'f%04d.png')
    base = [ffmpeg(), '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', src]
    run(base + ['-c:v', 'libx264', '-preset', 'veryslow', '-tune', 'animation', '-crf', '23',
                '-pix_fmt', 'yuv420p', '-movflags', '+faststart', os.path.join(HERE, 'theft_of_the_atlas_game.mp4')])
    if '--game-only' not in sys.argv:
        run(base + ['-vf', 'scale=1920:1080:flags=neighbor', '-c:v', 'libx264', '-preset', 'slow', '-tune', 'animation',
                    '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                    os.path.join(HERE, 'theft_of_the_atlas_1080p.mp4')])
    for n in ('theft_of_the_atlas_game.mp4', 'theft_of_the_atlas_1080p.mp4'):
        p = os.path.join(HERE, n)
        if os.path.exists(p):
            print(f'{n}: {os.path.getsize(p) / 1e6:.2f} MB')


if __name__ == '__main__':
    main()
