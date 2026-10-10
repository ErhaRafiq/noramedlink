"""Generate the Nora MedLink favicon, app icons and manifest icons from the logo mark.

The mark matches components/ui/NoraLogo.tsx: a rounded square with a blue-to-teal
diagonal gradient (#2563EB -> #00BFA6) and a white rounded medical cross.

Run from the repo root (Pillow is in the backend virtualenv):
    backend\\venv\\Scripts\\python.exe scripts\\generate-icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
START = (0x25, 0x63, 0xEB)  # --primary-start
END = (0x00, 0xBF, 0xA6)  # --primary-end
MASTER = 1024


def gradient(size: int) -> Image.Image:
    """Diagonal gradient from the top-left (START) to the bottom-right (END)."""
    small = Image.new("RGB", (256, 256))
    pixels = small.load()
    for y in range(256):
        for x in range(256):
            t = (x + y) / 510
            pixels[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(START, END))
    return small.resize((size, size), Image.BICUBIC)


def draw_cross(image: Image.Image, scale: float) -> None:
    """White cross centred on the image; `scale` is its arm length relative to the image."""
    size = image.width
    draw = ImageDraw.Draw(image)
    arm = size * scale
    bar = arm * 0.357  # NoraLogo: 2.5 / 7
    c = size / 2
    radius = bar / 2
    draw.rounded_rectangle((c - bar / 2, c - arm / 2, c + bar / 2, c + arm / 2), radius=radius, fill="white")
    draw.rounded_rectangle((c - arm / 2, c - bar / 2, c + arm / 2, c + bar / 2), radius=radius, fill="white")


def rounded_mark() -> Image.Image:
    """The standard icon: gradient rounded square on a transparent background."""
    mark = gradient(MASTER).convert("RGBA")
    draw_cross(mark, 0.636)  # NoraLogo: 7 / 11
    mask = Image.new("L", (MASTER, MASTER), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, MASTER - 1, MASTER - 1), radius=round(MASTER * 0.23), fill=255)
    mark.putalpha(mask)
    return mark


def full_bleed_mark(cross_scale: float) -> Image.Image:
    """Square icon with no transparency (Apple touch icon, Android maskable icon)."""
    mark = gradient(MASTER).convert("RGBA")
    draw_cross(mark, cross_scale)
    return mark


def save_png(image: Image.Image, size: int, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.resize((size, size), Image.LANCZOS).save(path, optimize=True)
    print(f"wrote {path.relative_to(ROOT)} ({size}x{size})")


def main() -> None:
    standard = rounded_mark()

    favicon = ROOT / "app" / "favicon.ico"
    standard.resize((256, 256), Image.LANCZOS).save(favicon, sizes=[(16, 16), (32, 32), (48, 48)])
    print(f"wrote {favicon.relative_to(ROOT)} (16, 32, 48)")

    save_png(full_bleed_mark(0.5), 180, ROOT / "app" / "apple-icon.png")
    save_png(standard, 192, ROOT / "public" / "icons" / "icon-192.png")
    save_png(standard, 512, ROOT / "public" / "icons" / "icon-512.png")
    # Maskable icons are cropped to a circle or squircle: keep the cross inside the 80% safe zone.
    save_png(full_bleed_mark(0.42), 512, ROOT / "public" / "icons" / "icon-maskable-512.png")


if __name__ == "__main__":
    main()
