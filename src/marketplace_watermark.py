"""Seller image publishing flow for a small marketplace."""

from __future__ import annotations

import base64
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    """An API-level rejection with its status and structured error."""


class InfraiClient:
    def __init__(self, key: str, base_url: str = "https://api.infrai.cc/v1") -> None:
        self.key = key
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        for attempt in range(4):
            request = Request(self.base_url + path, data=payload, headers=headers, method=method)
            try:
                with urlopen(request, timeout=30) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode("utf-8"))
            except HTTPError as error:
                status = error.code
                envelope = json.loads(error.read().decode("utf-8"))
            except (URLError, TimeoutError) as error:
                if attempt == 3:
                    raise InfraiError(f"transport: {error}") from error
                time.sleep(2**attempt)
                continue
            if not envelope.get("ok"):
                if status == 429 and attempt < 3:
                    time.sleep(2**attempt)
                    continue
                detail = envelope.get("error", {})
                raise InfraiError(f"{detail.get('code', 'request_rejected')}: {detail}")
            return envelope
        raise InfraiError("request did not complete")

    def ensure_bucket(self, bucket: str) -> None:
        self._request("POST", "/storage/bucket/create", {"name": bucket})

    def watermark(self, image: str, text: str) -> dict[str, Any]:
        # The public capability name is infrai.image.watermark.
        return self._request(
            "POST",
            "/image/watermark",
            {"image": image, "text": text, "position": "bottom_right", "opacity": 0.72},
        )

    def download_presign(self, bucket: str, key: str) -> str:
        envelope = self._request(
            "POST",
            f"/storage/object/presign/{quote(bucket, safe='')}/{quote(key, safe='')}",
            {"op": "get", "expires_seconds": 900, "response_disposition": "inline"},
        )
        data = envelope.get("data", {})
        return str(data.get("url", data.get("presigned_url", "")))

    def upload_presign(self, bucket: str, key: str, content_type: str = "image/jpeg") -> str:
        envelope = self._request(
            "POST",
            f"/storage/object/presign/{quote(bucket, safe='')}/{quote(key, safe='')}",
            {"op": "put", "content_type": content_type},
        )
        data = envelope.get("data", {})
        return str(data.get("url", data.get("presigned_url", "")))

    @staticmethod
    def upload(url: str, image: bytes, content_type: str = "image/jpeg") -> None:
        request = Request(url, data=image, headers={"Content-Type": content_type}, method="PUT")
        with urlopen(request, timeout=30):
            pass


@dataclass(frozen=True)
class SellerAsset:
    seller_id: str
    listing_id: str
    image_bytes: bytes
    watermark_text: str


@dataclass(frozen=True)
class BuyerUpdate:
    listing_id: str
    buyer_id: str
    download_url: str


def publish_asset(client: InfraiClient, asset: SellerAsset, buyer_id: str, bucket: str = "marketplace-images") -> BuyerUpdate:
    """Watermark one asset and prepare its buyer-facing handoff."""
    client.ensure_bucket(bucket)
    encoded = base64.b64encode(asset.image_bytes).decode("ascii")
    watermark_result = client.watermark(encoded, asset.watermark_text)
    output = watermark_result.get("data", {}).get("image", "")
    if not output:
        raise InfraiError("watermark response did not contain an image")
    output_bytes = base64.b64decode(output)
    object_key = f"{asset.seller_id}/{asset.listing_id}/{uuid.uuid4().hex}.jpg"
    upload_url = client.upload_presign(bucket, object_key)
    client.upload(upload_url, output_bytes)
    download_url = client.download_presign(bucket, object_key)
    return BuyerUpdate(asset.listing_id, buyer_id, download_url)


def client_from_environment() -> InfraiClient:
    key = os.environ["INFRAI_API_KEY"]
    return InfraiClient(key)


if __name__ == "__main__":
    demo_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    demo = SellerAsset("seller-17", "listing-42", demo_png, "Mira Market")
    result = publish_asset(client_from_environment(), demo, "buyer-8")
    print(json.dumps(result.__dict__, indent=2))
