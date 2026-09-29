from django.test import SimpleTestCase

from .outline_modes import (
    content_form_name,
    information_density_name,
    normalize_content_form,
    normalize_information_density,
)


class OutlineModeTests(SimpleTestCase):
    def test_defaults_are_automatic(self):
        self.assertEqual(normalize_content_form(None), "auto")
        self.assertEqual(normalize_information_density("自动推荐"), "auto")

    def test_known_values_have_user_labels(self):
        self.assertEqual(content_form_name("single_infographic"), "单页知识信息图")
        self.assertEqual(information_density_name("high"), "高密度")

    def test_unknown_values_are_rejected(self):
        with self.assertRaises(ValueError):
            normalize_content_form("unknown")
        with self.assertRaises(ValueError):
            normalize_information_density("unknown")
