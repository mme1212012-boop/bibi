import hashlib
import io
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from updater import INSTALLER_NAME, ReleaseUpdate, download_update, parse_release_update


class FakeResponse(io.BytesIO):
    def __init__(self, contents):
        super().__init__(contents)
        self.headers = {"Content-Length": str(len(contents))}


def make_release(tag="v1.0.1", url=None, digest="sha256:" + "a" * 64):
    return {
        "tag_name": tag,
        "assets": [
            {
                "name": INSTALLER_NAME,
                "browser_download_url": url
                or f"https://github.com/mme1212012-boop/bibi/releases/download/{tag}/{INSTALLER_NAME}",
                "digest": digest,
            }
        ],
    }


class UpdaterTests(unittest.TestCase):
    def test_detects_newer_release_and_reads_digest(self):
        update = parse_release_update(make_release(), "1.0.0")

        self.assertIsNotNone(update)
        self.assertEqual(update.version, "1.0.1")
        self.assertEqual(update.sha256, "a" * 64)

    def test_ignores_current_or_older_release(self):
        self.assertIsNone(parse_release_update(make_release("v1.0.0"), "1.0.0"))
        self.assertIsNone(parse_release_update(make_release("v0.9.9"), "1.0.0"))

    def test_rejects_non_github_asset_url(self):
        release = make_release(url="https://example.com/Bibi-Setup.exe")

        with self.assertRaisesRegex(ValueError, "không thuộc GitHub Releases"):
            parse_release_update(release, "1.0.0")

    def test_requires_asset_digest(self):
        release = make_release(digest=None)

        with self.assertRaisesRegex(ValueError, "SHA-256"):
            parse_release_update(release, "1.0.0")

    def test_download_verifies_digest_before_returning_installer(self):
        contents = b"verified installer"
        response = FakeResponse(contents)
        update = ReleaseUpdate(
            "1.0.1",
            "https://github.com/mme1212012-boop/bibi/releases/download/v1.0.1/Bibi-Setup.exe",
            hashlib.sha256(contents).hexdigest(),
        )

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "Bibi-Setup.exe"
            with patch("updater.urllib.request.urlopen", return_value=response):
                result = download_update(update, target, threading.Event())

            self.assertEqual(result, target)
            self.assertEqual(target.read_bytes(), contents)

    def test_download_deletes_installer_when_digest_is_wrong(self):
        response = FakeResponse(b"unverified installer")
        update = ReleaseUpdate(
            "1.0.1",
            "https://github.com/mme1212012-boop/bibi/releases/download/v1.0.1/Bibi-Setup.exe",
            "0" * 64,
        )

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "Bibi-Setup.exe"
            with patch("updater.urllib.request.urlopen", return_value=response):
                with self.assertRaisesRegex(ValueError, "không khớp"):
                    download_update(update, target, threading.Event())

            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
