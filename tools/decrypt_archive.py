"""CLI tool to inspect and decrypt FWT yearly archive packages.

Enables compliance auditors and administrators to decrypt and inspect any
archive package (.enc) independently of the web application.

Usage:
  uv run --project backend python tools/decrypt_archive.py archives/archive_2024_xxx.enc [--output decrypted.json] [--key KEY]
"""

import argparse
import json
import os
import sys

from fw.modules.archive.crypto import compute_sha256, decrypt_payload


def main():
    parser = argparse.ArgumentParser(description="Decrypt and inspect a Field Worker Tracker yearly archive package.")
    parser.add_argument("archive_file", help="Path to the encrypted .enc archive file")
    parser.add_argument("--output", "-o", default=None, help="Path to save the decrypted JSON file (optional)")
    parser.add_argument("--key", "-k", default=None, help="Encryption key (defaults to ARCHIVE_ENCRYPTION_KEY or dev key)")
    args = parser.parse_args()

    if not os.path.exists(args.archive_file):
        print(f"Error: Archive file not found: {args.archive_file}")
        sys.exit(1)

    key = args.key or os.environ.get("ARCHIVE_ENCRYPTION_KEY") or "insecure-archive-key-change-in-production-min-32-bytes"

    with open(args.archive_file, "rb") as f:
        encrypted_bytes = f.read()

    checksum = compute_sha256(encrypted_bytes)
    print(f"Archive file:     {args.archive_file}")
    print(f"File size:        {len(encrypted_bytes):,} bytes")
    print(f"SHA-256 Checksum: {checksum}")

    print("Decrypting payload using AES-256-GCM...")
    try:
        decrypted_bytes = decrypt_payload(encrypted_bytes, key)
    except Exception as e:
        print(f"Decryption failed: {e}")
        print("Please verify that you provided the correct ARCHIVE_ENCRYPTION_KEY.")
        sys.exit(1)

    try:
        data = json.loads(decrypted_bytes.decode("utf-8"))
    except Exception as e:
        print(f"Failed to parse decrypted JSON: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("ARCHIVE PACKAGE CONTENTS")
    print("=" * 60)
    print(f"Archived Year:        {data.get('year')}")
    print(f"Generated At (UTC):   {data.get('archived_at_utc')}")
    print(f"Total Record Count:   {data.get('record_count')}")
    counts = data.get("counts", {})
    print(f"  - Raw Mobile Events: {counts.get('mobile_event_logs', 0):,}")
    print(f"  - Site Visits:       {counts.get('site_visits', 0):,}")
    print(f"  - Tracking Gaps:     {counts.get('tracking_gaps', 0):,}")
    print("=" * 60)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Decrypted contents written to: {args.output}")
    else:
        print("To save the full decrypted JSON, specify --output <path.json>")


if __name__ == "__main__":
    main()
