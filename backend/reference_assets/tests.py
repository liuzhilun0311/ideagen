from django.test import TestCase

from accounts.models import User
from .models import ImageAnalysis, ReferenceAsset


class ReferenceAssetModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            id="u_reference_test",
            username="reference-test",
            password_hash="test",
        )

    def test_analysis_and_asset_have_owner_scoped_defaults(self):
        analysis = ImageAnalysis.objects.create(owner=self.user)
        asset = ReferenceAsset.objects.create(owner=self.user, analysis=analysis)

        self.assertEqual(analysis.content, {})
        self.assertEqual(analysis.layout, {})
        self.assertEqual(analysis.visual_style, {})
        self.assertEqual(asset.owner_id, self.user.id)
        self.assertEqual(asset.analysis_id, analysis.id)
