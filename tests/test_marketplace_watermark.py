import unittest
from unittest.mock import Mock

from src.marketplace_watermark import InfraiClient, SellerAsset, publish_asset


class PublishAssetTest(unittest.TestCase):
    def test_buyer_receives_the_signed_handoff_for_the_listing(self) -> None:
        client = Mock(spec=InfraiClient)
        client.watermark.return_value = {"data": {"image": "cGl4ZWxz"}}
        client.upload_presign.return_value = "https://objects.example/upload"
        client.download_presign.return_value = "https://objects.example/signed"
        result = publish_asset(
            client,
            SellerAsset("seller-17", "listing-42", b"pixels", "Mira Market"),
            "buyer-8",
        )
        client.ensure_bucket.assert_called_once_with("marketplace-images")
        client.watermark.assert_called_once()
        client.upload_presign.assert_called_once()
        client.upload.assert_called_once_with("https://objects.example/upload", b"pixels")
        self.assertEqual(result.listing_id, "listing-42")
        self.assertEqual(result.buyer_id, "buyer-8")
        self.assertEqual(result.download_url, "https://objects.example/signed")


if __name__ == "__main__":
    unittest.main()
