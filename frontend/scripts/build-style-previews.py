"""Build illustrative, offline style swatches, not model output samples."""
from pathlib import Path
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'public' / 'assets' / 'styles'
PHOTO = ROOT / 'public' / 'assets' / 'inspiration' / 'city.jpg'
FONT = Path('C:/Windows/Fonts/msyh.ttc')


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    photo = ImageOps.fit(Image.open(PHOTO).convert('RGB'), (360, 240))
    font = ImageFont.truetype(str(FONT), 22) if FONT.exists() else ImageFont.load_default()
    small = ImageFont.truetype(str(FONT), 15) if FONT.exists() else ImageFont.load_default()
    styles = {
        'auto': ('#f5f7fa', '#566477'),
        'comic': ('#fff4b9', '#e7555f'),
        'sketch-note': ('#f8fbf9', '#328c77'),
        'watercolor': ('#f4f8fc', '#6998c4'),
        'pencil': ('#faf8fc', '#b77391'),
        'infographic': ('#f5f8fa', '#3c89a5'),
        'photography': ('#ffffff', '#607547'),
        'collage': ('#f3f0ee', '#b26d4f'),
        'minimal': ('#ffffff', '#333d48'),
    }
    for style, (background, accent) in styles.items():
        image = Image.new('RGB', (360, 240), background)
        draw = ImageDraw.Draw(image)
        if style in ('photography', 'collage'):
            crop = photo.resize((185, 160))
            image.paste(crop, (160, 50))
            if style == 'collage':
                draw.rectangle((147, 44, 222, 56), fill='#d5b584')
                draw.rectangle((270, 204, 349, 216), fill='#d5b584')
        elif style == 'watercolor':
            painted = ImageOps.posterize(photo.filter(ImageFilter.SMOOTH_MORE), 4)
            painted = Image.blend(painted, Image.new('RGB', painted.size, '#e6f0f5'), 0.3)
            image.paste(painted.resize((185, 160)), (160, 50))
            draw = ImageDraw.Draw(image)
        else:
            rng = random.Random(7)
            for index in range(3):
                x, y = 183 + index * 43, 163 - index * 29
                if style == 'comic':
                    draw.rounded_rectangle((x, y - 30, x + 57, y + 41), radius=5, fill=accent, outline='#222a33', width=3)
                elif style in ('sketch-note', 'pencil'):
                    for _ in range(3):
                        jitter = rng.randint(-2, 2)
                        draw.rectangle((x + jitter, y - 30, x + 40, y + 35 + jitter), outline=accent, width=1)
                    for line in range(7):
                        draw.line((x + 4, y - 24 + line * 8, x + 34, y - 12 + line * 8), fill=accent)
                else:
                    draw.rectangle((x, y - 30, x + 30, 202), fill=accent)
            if style == 'comic':
                draw.line((177, 55, 191, 40), fill='#222a33', width=3)
                draw.line((196, 62, 217, 57), fill='#222a33', width=3)
        draw.rectangle((18, 20, 26, 46), fill=accent)
        draw.text((36, 18), '知识图文', font=font, fill='#263340')
        for index, label in enumerate(('一个重点', '清晰层级', '统一画风')):
            y = 81 + index * 43
            draw.text((21, y), f'0{index + 1}', font=small, fill=accent)
            draw.text((51, y), label, font=small, fill='#354452')
        image.save(OUT / f'{style}.png', optimize=True)


if __name__ == '__main__':
    build()
