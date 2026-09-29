from django.test import SimpleTestCase

from .reference_roles import ROLES, reference_instruction, validate_reference_roles
from .image_prompt import automatic_image_template
from .outline_prompt import build_outline_prompt


class ReferenceRolesTests(SimpleTestCase):
    def test_each_selection_is_exclusive(self):
        for role, label in ROLES.items():
            with self.subTest(role=role):
                instruction = reference_instruction(1, [role])
                self.assertIn(f"参考图片仅用于：{label}。", instruction)
                for key, excluded in ROLES.items():
                    if key != role:
                        self.assertIn(excluded, instruction.split("不得参考未选择的维度：")[1])

    def test_empty_and_missing_images_do_not_enable_defaults(self):
        self.assertIn("用户未选择参考维度", reference_instruction(1, []))
        self.assertEqual(reference_instruction(0, ["style"]), "")

    def test_content_selection_extracts_readable_text_without_guessing(self):
        instruction = reference_instruction(1, ["content"])
        self.assertIn("图片中的文字与表达内容", instruction)
        self.assertIn("标题、正文、数字、标签和要点", instruction)
        self.assertIn("看不清或无法确认的文字不要猜测", instruction)
        self.assertNotIn("不复制参考图中的文字", instruction)

    def test_invalid_roles_fail_without_fallback(self):
        for invalid in ["subject", ["unknown"], [{}], [None]]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_reference_roles(invalid)

    def test_outline_and_image_share_subject_only_instruction(self):
        instruction = reference_instruction(1, ["subject"])
        outline = build_outline_prompt("整理桌面", image_count=1, reference_roles=["subject"])
        image = automatic_image_template({"preset": "pencil", "notes": ""}, 1, False, ["subject"])
        self.assertIn(instruction, outline)
        self.assertIn(instruction, image)
        self.assertNotIn("参考图只保留必要", image)
        self.assertNotIn("参考图片重点用于：图片风格", image)

    def test_cover_reference_is_separate(self):
        prompt = automatic_image_template({"preset": "pencil", "notes": ""}, 1, True, ["subject"])
        self.assertIn("参考图片仅用于：图片主体与关键特征。", prompt)
        self.assertIn("第一张已采用图片作为一致性参考", prompt)
