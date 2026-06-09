#!/usr/bin/env python3
"""Generate the integration icon set (Home Assistant brands spec).

Outputs (square, transparent corners, supersampled for crisp edges):
  brands/zkteco_acp/icon.png        256x256
  brands/zkteco_acp/icon@2x.png     512x512
  brands/zkteco_acp/logo.png        512x512 (same mark; brands allows logo == icon)

Theme: an access-control padlock over a ZKTeco-blue rounded-square gradient.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

SS = 4  # supersample factor
BASE = 256
S = BASE * SS

TOP = (42, 169, 224)     # ZK light blue
BOTTOM = (14, 77, 164)   # deep blue
WHITE = (255, 255, 255, 255)


def _gradient(size: int) -> Image.Image:
    grad = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        grad.putpixel(
            (0, y),
            tuple(round(TOP[i] + (BOTTOM[i] - TOP[i]) * t) for i in range(3)),
        )
    return grad.resize((size, size))


def _rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def make() -> Image.Image:
    # Background: gradient clipped to a rounded square.
    bg = _gradient(S).convert("RGBA")
    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    canvas.paste(bg, (0, 0), _rounded_mask(S, int(S * 0.22)))

    d = ImageDraw.Draw(canvas)
    cx = S // 2

    # --- Padlock ---
    body_w = int(S * 0.46)
    body_h = int(S * 0.34)
    body_top = int(S * 0.46)
    body_left = cx - body_w // 2
    body_right = cx + body_w // 2
    body_bottom = body_top + body_h
    body_radius = int(S * 0.05)

    # Shackle (open-bottom arc) drawn before the body so the body covers the ends.
    sh_w = int(body_w * 0.62)
    sh_thick = int(S * 0.05)
    sh_left = cx - sh_w // 2
    sh_right = cx + sh_w // 2
    sh_top = int(S * 0.20)
    sh_bottom = body_top + int(S * 0.02)
    # vertical legs
    d.rounded_rectangle(
        [sh_left, sh_top, sh_left + sh_thick, sh_bottom],
        radius=sh_thick // 2,
        fill=WHITE,
    )
    d.rounded_rectangle(
        [sh_right - sh_thick, sh_top, sh_right, sh_bottom],
        radius=sh_thick // 2,
        fill=WHITE,
    )
    # top arc
    d.arc(
        [sh_left, sh_top - sh_w // 2, sh_right, sh_top + sh_w // 2],
        start=180,
        end=360,
        fill=WHITE,
        width=sh_thick,
    )

    # Lock body
    d.rounded_rectangle(
        [body_left, body_top, body_right, body_bottom],
        radius=body_radius,
        fill=WHITE,
    )

    # Keyhole (gradient blue, cut visually by sampling the bg colour).
    key = (18, 96, 190)
    kh_cx = cx
    kh_cy = body_top + int(body_h * 0.42)
    kh_r = int(S * 0.045)
    d.ellipse([kh_cx - kh_r, kh_cy - kh_r, kh_cx + kh_r, kh_cy + kh_r], fill=key)
    slot_w = int(kh_r * 0.7)
    d.polygon(
        [
            (kh_cx - slot_w, body_bottom - int(body_h * 0.18)),
            (kh_cx + slot_w, body_bottom - int(body_h * 0.18)),
            (kh_cx + int(slot_w * 0.5), kh_cy),
            (kh_cx - int(slot_w * 0.5), kh_cy),
        ],
        fill=key,
    )

    # Two small status dots on the body -> hints "access panel".
    dot_r = int(S * 0.018)
    dy = body_top + int(body_h * 0.20)
    d.ellipse(
        [cx - int(S * 0.10) - dot_r, dy - dot_r, cx - int(S * 0.10) + dot_r, dy + dot_r],
        fill=(46, 204, 113),  # green
    )
    d.ellipse(
        [cx + int(S * 0.10) - dot_r, dy - dot_r, cx + int(S * 0.10) + dot_r, dy + dot_r],
        fill=(231, 76, 60),  # red
    )

    return canvas.resize((BASE, BASE), Image.LANCZOS)


def main() -> None:
    out_dir = os.path.join(os.path.dirname(__file__), "..", "brands", "zkteco_acp")
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    icon256 = make()
    icon256.save(os.path.join(out_dir, "icon.png"))
    icon512 = icon256.resize((512, 512), Image.LANCZOS)
    icon512.save(os.path.join(out_dir, "icon@2x.png"))
    icon512.save(os.path.join(out_dir, "logo.png"))
    print("wrote icon.png (256), icon@2x.png (512), logo.png (512) to", out_dir)


if __name__ == "__main__":
    main()
