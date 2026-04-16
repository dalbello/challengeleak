#!/usr/bin/env python3
"""Generate OG image for social sharing. Run inside Docker container or with Pillow installed."""
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow not installed. Run: pip install Pillow")
    sys.exit(1)


def generate_og_image(title, subtitle, features=None, output_path="static/img/og-image.png"):
    """Generate a 1200x630 OG image with green gradient background."""
    width, height = 1200, 630
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    for y in range(height):
        r = int(6 + (y / height) * 18)
        g = int(120 - (y / height) * 40)
        b = int(92 - (y / height) * 35)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
        subtitle_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 27)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except (OSError, IOError):
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    draw.text((60, 84), title, fill="white", font=title_font)
    draw.text((60, 170), subtitle, fill=(210, 255, 230), font=subtitle_font)

    if features:
        y_pos = 274
        for feat in features[:4]:
            draw.text((82, y_pos), f"✓  {feat}", fill="white", font=small_font)
            y_pos += 45

    draw.text((60, height - 74), "tinyship.ai", fill=(210, 255, 230), font=subtitle_font)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path)
    print(f"✅ OG image saved to {output_path}")


if __name__ == "__main__":
    generate_og_image(
        title="ChallengeLeak",
        subtitle="Find Cloudflare challenge rules leaking revenue",
        features=[
            "Revenue-at-risk per rule",
            "Challenge friction impact",
            "Waitlist for private beta",
        ],
    )
