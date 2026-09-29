from django.test import SimpleTestCase
from .copy_validation import validate_copy_result


class CopyValidationTests(SimpleTestCase):
    def test_rich_plain_copy_warns_without_modifying_content(self):
        result = {"titles": ["📌 防护清单"], "copywriting": "- 出行：使用安全带。\n- 居家：检查报警器。", "tags": ["健康"]}
        original = {**result}
        validation = validate_copy_result(result, {"emoji_level": "丰富"})
        self.assertEqual(len(validation["warnings"]), 1)
        self.assertIn("正文未包含表情或信息符号", validation["warnings"][0])
        self.assertEqual(result, original)
        self.assertFalse(validation["semantic_verified"])

    def test_neutral_symbols_and_compound_emoji_satisfy_presence_check(self):
        for symbol in ("1️⃣", "✅", "📌", "🏠", "✓", "→", "•", "①", "❶", "👩‍💻", "👍🏽"):
            with self.subTest(symbol=symbol):
                validation = validate_copy_result({"copywriting": f"{symbol} 检查出行准备。"}, {"emoji_level": "丰富"})
                self.assertEqual(validation["warnings"], [])

    def test_numbers_punctuation_and_markdown_do_not_count_as_symbols(self):
        for text in ("1. 出行\n2. 居家", "- 注意事项", "**准备**：了解情况！", "# 标题\n健康管理"):
            with self.subTest(text=text):
                self.assertTrue(validate_copy_result({"copywriting": text}, {"emoji_level": "丰富"})["warnings"])

    def test_other_levels_do_not_require_symbols(self):
        for level in ("无", "克制", None):
            self.assertEqual(validate_copy_result({"copywriting": "检查准备"}, {"emoji_level": level})["warnings"], [])

    def test_no_emoji_still_rejects_neutral_emoji(self):
        for symbol in ("1️⃣", "✅", "📌", "🏠"):
            with self.subTest(symbol=symbol), self.assertRaises(ValueError):
                validate_copy_result({"copywriting": f"{symbol} 提醒"}, {"emoji_level": "无"})

    def test_length_warning_coexists_with_symbol_warning(self):
        validation = validate_copy_result({"copywriting": "简短提醒"}, {"emoji_level": "丰富", "length": "详细"})
        self.assertEqual(len(validation["warnings"]), 2)
