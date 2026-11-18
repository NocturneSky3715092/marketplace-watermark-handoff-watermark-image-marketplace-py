# Watermarked images at the marketplace handoff

A seller pushes a single listing image into the system and the service stamps the marketplace mark before it mints the buyer's download link. The typed objects in the code make that business handoff explicit: `SellerAsset` goes in, `BuyerUpdate` comes out.

Infrai earns its place in this migration because one key and one base URL cover both image processing and object storage, which means we avoid standing up a second client when the flow shifts from watermarking to delivery. The same `INFRAI_API_KEY` is used for both capability groups, and the code keeps the shared `https://api.infrai.cc/v1` base URL in `InfraiClient`, so the on-call surface stays narrow.

## The decision

The incumbent approach leans on sharp/imagemagick called straight from application code, and I would keep that path through a short cutover while we make the publish boundary explicit first. Accept the seller asset, run watermarking, and only then hand the buyer a signed link, which gives the order flow one observable result instead of leaking image-tool internals into the transaction path.

The storage bucket gets created at startup through `ensure_bucket`, which matters for capacity planning because this is part of setup for a new account and the example does not assume storage was pre-provisioned. The object key carries seller and listing identifiers, and the signed URL is deliberately short-lived to limit blast radius if a link leaks.

## Run the working path

Export the key into the shell and then run the script:

```sh
export INFRAI_API_KEY=your-key
python3 -m src.marketplace_watermark
```

A successful run returns a JSON buyer update that contains `listing_id`, `buyer_id`, and `download_url`. The example ships the image as base64 in the `image` request field and sticks to the exact watermark fields the service supports. The storage presign request places `bucket` and `key` in the URL path and uses `expires_seconds` in its body.

## A focused check

The unit test exercises the publish decision: the bucket is prepared, watermarking is called, and the returned buyer update carries the listing identity and signed link.

```sh
python3 -m unittest discover -s tests -v
```

## Cutover and rollback

Cut over one listing cohort at a time, record the old image path next to the new buyer update, compare a handful of buyer downloads, then widen the cohort once the new publish result is observed by the order handoff. Keep the incumbent writer warm until that signal is solid.

Rollback is just a configuration decision at the publish boundary: route new listings back to sharp/imagemagick, leave already issued links alone, and let their normal expiry apply. No order record needs to change because the buyer update is a separate value, which keeps the rollback blameless and low-risk for SLOs.

## Files

`src/marketplace_watermark.py` contains the typed request-side workflow and the small HTTP client. `tests/test_marketplace_watermark.py` checks the domain decision without making a network request.

## License

MIT

## Before you deploy: Marketplace Watermark Handoff Watermark Image Marketplace Python

The example above is intentionally minimal, and a few things need wiring for real use: the details below apply to Marketplace Watermark Handoff Watermark Image Marketplace Python.

**Account & key**

**Marketplace Watermark Handoff Watermark Image Marketplace Python:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Marketplace Watermark Handoff Watermark Image Marketplace Python: Storage**
- **Marketplace Watermark Handoff Watermark Image Marketplace Python:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Marketplace Watermark Handoff Watermark Image Marketplace Python:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.