"""Explicit, resumable style acceptance runs; never called by normal requests."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import time

from PIL import Image

from .generators.gpt_images import GptImagesClient
from .styles import CATALOG

ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = ROOT / 'output' / 'style-samples-20260927'
TOPIC = '桌面绿植照料'
PAGE = {
    'index': 0, 'type': 'content',
    'content': (
        '单页布局：自动\n'
        '上图文字：\n桌面绿植照料\n观察叶片\n检查盆土\n按需浇水\n'
        '画面描述：一盆绿色桌面植物、一个小浇水壶和一位照料植物的成年人。'
        '只使用上面四行文字，文字清楚且层级分明；主体统一，按所选风格表现。'
        '这是虚构的风格展示素材，不是真实客户案例或聊天截图；'
        '不要添加品牌、账号、评价、价格、销售数据、功效承诺、二维码或多余文字。'
    ),
}


def sample_prompt(style_id):
    from .image_prompt import render_page_prompt
    return render_page_prompt(PAGE, TOPIC, {'preset': style_id, 'notes': ''})


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def persist(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def run(config, ids, *, root=RUN_ROOT, interval=5, generate=None):
    root.mkdir(parents=True, exist_ok=True)
    manifest = root / 'run.json'
    state = json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {'samples': {}}
    model = config.get('model', '')
    if not model.startswith('gpt-image-'):
        raise ValueError('This acceptance runner requires the configured GPT image model.')
    config = {**config, 'image_size': '2K', 'quality': 'low', 'output_format': 'png'}
    generate = generate or GptImagesClient(config).generate_image
    catalog = {style['id']: style for style in CATALOG}
    for position, style_id in enumerate(ids):
        style = catalog[style_id]
        prompt = sample_prompt(style_id)
        previous = state['samples'].get(style_id)
        if previous:
            if previous['status'] != 'generated':
                raise RuntimeError(f'{style_id}: previous attempt needs inspection; refusing automatic retry.')
            if previous['prompt_sha256'] != digest(prompt) or previous['model'] != model:
                raise RuntimeError(f'{style_id}: sample parameters changed; preserve the existing run.')
            if not (root / f'{style_id}.png').is_file():
                raise RuntimeError(f'{style_id}: recorded output missing; refusing duplicate paid request.')
            continue
        item = {
            'id': style_id, 'name': style['name'], 'model': model,
            'resolution': '2K', 'quality': 'low', 'aspect_ratio': '3:4',
            'started_at': datetime.now(timezone.utc).isoformat(),
            'prompt_sha256': digest(prompt), 'direction': style['direction'],
            'status': 'requesting', 'review': 'pending',
        }
        state['samples'][style_id] = item
        persist(manifest, state)
        (root / f'{style_id}.txt').write_text(prompt, encoding='utf-8')
        print(f'Generating {position + 1}/{len(ids)}: {style_id}', flush=True)
        try:
            data = generate(prompt, aspect_ratio='3:4', model=model)
            # Preserve returned bytes even if the resolution audit below fails.
            (root / f'{style_id}.png').write_bytes(data)
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                width, height = image.size
                if width < 1536 or height < 2048:
                    raise ValueError(f'Output below requested 2K dimensions: {width}x{height}')
            item.update(status='generated', width=width, height=height,
                        image_sha256=hashlib.sha256(data).hexdigest(),
                        finished_at=datetime.now(timezone.utc).isoformat())
            persist(manifest, state)
            print(f'Saved {style_id}: {width}x{height}', flush=True)
        except Exception as error:
            # Do not persist upstream messages or configuration: they may contain secrets.
            item.update(status='failed', error_type=type(error).__name__)
            persist(manifest, state)
            print(f'STOPPED at {style_id}: {type(error).__name__}. No retry sent.', flush=True)
            raise RuntimeError(f'Generation stopped at {style_id}; inspect service task/billing before retrying.') from None
        if position < len(ids) - 1:
            time.sleep(interval)
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ids', nargs='+')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--run-root', type=Path, default=RUN_ROOT)
    args = parser.parse_args()
    ids = args.ids or [item['id'] for item in CATALOG]
    if set(ids) - {item['id'] for item in CATALOG}:
        parser.error('Unknown style ID')
    if not args.execute:
        print(json.dumps({'count': len(ids), 'ids': ids, 'resolution': '2K', 'quality': 'low'}))
        return
    from providers.config import load_shared_providers_config
    settings = load_shared_providers_config('image')
    config = settings['providers'][settings['active_provider']]
    if config.get('enabled') is False:
        raise RuntimeError('Active image provider is disabled.')
    run(config, ids, root=args.run_root)


if __name__ == '__main__':
    import os
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()
    main()
