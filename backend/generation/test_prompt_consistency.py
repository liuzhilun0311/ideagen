from pathlib import Path

from django.test import SimpleTestCase


class DefaultPromptConsistencyTests(SimpleTestCase):
    def test_all_default_templates_keep_the_existing_format_contract(self):
        root = Path(__file__).parent / 'prompts'
        values = {
            'topic': 'Example topic', 'outline': 'Example outline',
            'page_content': 'Example page', 'page_type': 'cover',
            'full_outline': 'All pages', 'user_topic': 'Example topic',
            'growth_rules': '',
            'platform_name': '抖音',
        }
        for name in ('outline_prompt.txt', 'content_prompt.txt',
                     'image_prompt.txt', 'image_prompt_short.txt'):
            with self.subTest(name=name):
                result = (root / name).read_text(encoding='utf-8').format(**values)
                self.assertIn('上图文字', result)
                self.assertIn('画面描述', result)
                self.assertNotIn('{topic}', result)
                self.assertNotIn('{full_outline}', result)

    def test_short_image_prompt_uses_current_page_without_full_outline(self):
        template = (Path(__file__).parent / 'prompts' / 'image_prompt_short.txt').read_text(encoding='utf-8')
        result = template.format(page_content='PAGE', page_type='cover',
                                 full_outline='SHARED OUTLINE', user_topic='TOPIC')
        self.assertNotIn('SHARED OUTLINE', result)
        self.assertIn('TOPIC', result)
        self.assertIn('PAGE', result)


class DefaultPromptHierarchyTests(SimpleTestCase):
    root = Path(__file__).parent / 'prompts'

    def _source(self, name):
        return (self.root / name).read_text(encoding='utf-8')

    def _render(self, name):
        return self._source(name).format(
            topic='提升生活质量的 6 个小习惯',
            outline='[内容]\n上图文字：\n标题：规律作息\n正文：固定一个可执行的入睡时间。\n画面描述：日夜节奏关系图',
            page_content='[内容]\n上图文字：\n标题：规律作息\n正文：固定一个可执行的入睡时间。\n画面描述：日夜节奏关系图',
            page_type='content',
            full_outline='封面\n<page>\n规律作息\n<page>\n总结',
            user_topic='提升生活质量的 6 个小习惯',
            growth_rules='平台与获客目标规则',
            platform_name='抖音',
        )

    def test_outline_prompt_requires_page_roles_components_and_visual_anchor(self):
        text = self._render('outline_prompt.txt')
        for phrase in ('页面角色', '单页布局', '短标签', '视觉主体'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_image_prompt_variants_keep_visible_text_and_layout_contract(self):
        for name in ('image_prompt.txt', 'image_prompt_short.txt'):
            with self.subTest(name=name):
                text = self._render(name)
                for phrase in ('上图文字', '画面描述', '主结构', '视觉主体', '最终风格'):
                    self.assertIn(phrase, text)
                self.assertIn('不得成为可见文字', text)
                self.assertIn('提升生活质量的 6 个小习惯', text)
                self.assertIn('规律作息', text)

    def test_image_prompt_appends_growth_rules_without_leaking_control_fields(self):
        from .generation_context import build_generation_context
        from .styles import format_image_prompt, style_prompt

        context = build_generation_context(
            "AI 工具获客",
            "单页布局：强钩子封面\n上图文字：提高效率",
            {"platform": "douyin", "goal": "follow"},
            {},
            {"preset": "infographic", "notes": ""},
        )
        template = style_prompt(
            "{page_content}\n{growth_rules}",
            {"preset": "infographic", "notes": ""},
            generation_context=context,
        )
        result = format_image_prompt(template, {
            "page_content": "上图文字：提高效率",
            "page_type": "cover",
            "full_outline": "",
            "user_topic": "AI 工具获客",
        })
        self.assertIn("douyin", result)
        self.assertIn("follow", result)
        self.assertIn("禁止渲染", result)
        self.assertIn("平台风险表达底线", result)

    def test_content_prompt_supports_xiaohongshu_scan_structure_without_breaking_json(self):
        source = self._source('content_prompt.txt')
        text = self._render('content_prompt.txt')
        for phrase in ('发布平台以本次平台规则为准', '按本次长度选项安排短段落', '同级列表统一采用一种编号或项目符号', '本次表情与符号丰富度', 'titles', 'copywriting', 'tags'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertIn('{{', source)
        self.assertIn('"titles"', text)
        self.assertNotIn('{topic}', text)
        self.assertNotIn('{outline}', text)
