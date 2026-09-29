"""Contact sheets and explicit publication of visually reviewed sample IDs."""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .style_samples import RUN_ROOT, ROOT, persist

ASSETS = ROOT / 'frontend/public/assets/styles/samples'
MANIFEST = ROOT / 'frontend/src/features/styles/samples.json'


def contact_sheets(state, root=RUN_ROOT):
    records = [item for item in state['samples'].values() if item['status'] == 'generated']
    font_path = Path('C:/Windows/Fonts/msyh.ttc')
    font = ImageFont.truetype(str(font_path), 19) if font_path.exists() else ImageFont.load_default()
    for offset in range(0, len(records), 8):
        image = Image.new('RGB', (1600, 1160), 'white')
        draw = ImageDraw.Draw(image)
        for index, item in enumerate(records[offset:offset + 8]):
            x, y = (index % 4) * 400, (index // 4) * 580
            draw.text((x + 10, y + 8), f"{item['id']} / {item['name']}", font=font, fill='#222222')
            with Image.open(root / f"{item['id']}.png") as original:
                thumb = ImageOps.contain(original, (390, 530))
                image.paste(thumb, (x + (400 - thumb.width) // 2, y + 40))
        output = root / f'contact-{offset // 8 + 1}.jpg'
        image.save(output, quality=95)
        print(output)


def publish(state, ids, note, *, rejected=False, root=RUN_ROOT):
    ASSETS.mkdir(parents=True, exist_ok=True)
    review_path = root / 'reviews.json'
    reviews = json.loads(review_path.read_text(encoding='utf-8')) if review_path.exists() else {}
    for style_id in ids:
        record = state['samples'][style_id]
        if record['status'] != 'generated':
            raise ValueError(f'{style_id}: no completed image')
        reviews[style_id] = {'review': 'rejected' if rejected else 'approved', 'review_note': note,
                             'image_sha256': record['image_sha256']}
    # Generation owns run.json; reviews must not overwrite a concurrently completed request.
    persist(review_path, reviews)
    existing = json.loads(MANIFEST.read_text(encoding='utf-8')) if MANIFEST.exists() else []
    manifest = {sample['id']: sample for sample in existing}
    for style_id in ids:
        record = state['samples'][style_id]
        reviewed = reviews.get(record['id'], {})
        if reviewed.get('review') != 'approved' or reviewed.get('image_sha256') != record['image_sha256']:
            continue
        record = {**record, **reviewed}
        with Image.open(root / f"{record['id']}.png") as image:
            # Full-size lossless WebP preserves text and original pixels.
            image = image.convert('RGB')
            filename = f"{record['id']}-{record['image_sha256'][:10]}"
            full = ASSETS / f'{filename}.webp'
            thumbnail = ASSETS / f'{filename}-thumb.webp'
            if not full.exists():
                image.save(full, 'WEBP', lossless=True)
            if not thumbnail.exists():
                image.thumbnail((576, 768))
                image.save(thumbnail, 'WEBP', quality=90)
        manifest[record['id']] = {
            key: record[key] for key in ('id', 'direction', 'model', 'quality', 'width', 'height', 'review')
        } | {
            'generated_at': record['finished_at'],
            'url': f'/assets/styles/samples/{full.name}',
            'thumbnail': f'/assets/styles/samples/{thumbnail.name}',
            'prompt_sha256': record['prompt_sha256'],
            'image_sha256': record['image_sha256'],
            'review_note': record['review_note'],
        }
    persist(MANIFEST, list(manifest.values()))
    print(f'Published {len(manifest)} reviewed samples.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--approve', nargs='+')
    parser.add_argument('--reject', nargs='+')
    parser.add_argument('--note', default='')
    parser.add_argument('--run-root', type=Path, default=RUN_ROOT)
    args = parser.parse_args()
    state = json.loads((args.run_root / 'run.json').read_text(encoding='utf-8'))
    if args.approve and args.reject:
        parser.error('Approve or reject, not both')
    if args.approve or args.reject:
        if not args.note.strip():
            parser.error('Explicit visual review note required')
        publish(state, args.approve or args.reject, args.note, rejected=bool(args.reject), root=args.run_root)
    else:
        contact_sheets(state, root=args.run_root)


if __name__ == '__main__':
    main()
