from __future__ import annotations

import hashlib
import json
import re
import subprocess
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


REPOSITORY_OWNER = "mme1212012-boop"
REPOSITORY_NAME = "bibi"
RELEASE_API_URL = (
    f"https://api.github.com/repos/{REPOSITORY_OWNER}/{REPOSITORY_NAME}/releases/latest"
)
INSTALLER_NAME = "Bibi-Setup.exe"
INSTALLER_DOWNLOAD_URL = (
    f"https://github.com/{REPOSITORY_OWNER}/{REPOSITORY_NAME}"
    f"/releases/latest/download/{INSTALLER_NAME}"
)
MAX_INSTALLER_SIZE = 500 * 1024 * 1024
_VERSION_PATTERN = re.compile(r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_DIGEST_PATTERN = re.compile(r"^sha256:([0-9a-fA-F]{64})$")


@dataclass(frozen=True)
class ReleaseUpdate:
    version: str
    download_url: str
    sha256: str


def _version_key(value: str) -> tuple[int, int, int]:
    match = _VERSION_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError(f"Phiên bản không đúng định dạng x.y.z: {value}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def parse_release_update(release: object, current_version: str) -> ReleaseUpdate | None:
    current_key = _version_key(current_version)
    if not isinstance(release, dict):
        raise ValueError("Dữ liệu bản phát hành GitHub không hợp lệ.")

    tag = release.get("tag_name")
    if not isinstance(tag, str):
        raise ValueError("Bản phát hành GitHub thiếu tag phiên bản.")
    latest_key = _version_key(tag)
    if latest_key <= current_key:
        return None

    assets = release.get("assets")
    if not isinstance(assets, list):
        raise ValueError("Bản phát hành GitHub không có danh sách file.")
    asset = next(
        (
            item
            for item in assets
            if isinstance(item, dict) and item.get("name") == INSTALLER_NAME
        ),
        None,
    )
    if asset is None:
        raise ValueError(f"Bản phát hành mới thiếu file {INSTALLER_NAME}.")

    url = asset.get("browser_download_url")
    if not isinstance(url, str):
        raise ValueError("Bản phát hành thiếu liên kết tải bộ cài.")
    parsed_url = urllib.parse.urlparse(url)
    expected_path = (
        f"/{REPOSITORY_OWNER}/{REPOSITORY_NAME}/releases/download/{tag}/{INSTALLER_NAME}"
    )
    if (
        parsed_url.scheme != "https"
        or parsed_url.netloc.lower() != "github.com"
        or parsed_url.path != expected_path
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise ValueError("Liên kết bộ cài không thuộc GitHub Releases của Bibi.")

    digest = asset.get("digest")
    digest_match = _DIGEST_PATTERN.fullmatch(digest) if isinstance(digest, str) else None
    if digest_match is None:
        raise ValueError("Bản phát hành thiếu mã SHA-256 hợp lệ cho bộ cài.")

    return ReleaseUpdate(tag.removeprefix("v"), url, digest_match.group(1).lower())


def check_latest_update(current_version: str) -> ReleaseUpdate | None:
    request = urllib.request.Request(
        RELEASE_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Bibi-Updater",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            release = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise RuntimeError(f"Không kiểm tra được bản cập nhật (HTTP {exc.code}).") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Không kiểm tra được bản cập nhật: {exc}") from exc
    return parse_release_update(release, current_version)


def download_update(
    update: ReleaseUpdate,
    destination: Path,
    stop_event: threading.Event,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    total_size = 0
    request = urllib.request.Request(
        update.download_url,
        headers={"User-Agent": "Bibi-Updater"},
    )

    try:
        if stop_event.is_set():
            raise InterruptedError("Đã hủy tải bản cập nhật.")
        with (
            urllib.request.urlopen(request, timeout=60) as response,
            destination.open("wb") as output,
        ):
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_INSTALLER_SIZE:
                raise ValueError("Bộ cài tải về vượt quá giới hạn kích thước.")
            while chunk := response.read(1024 * 1024):
                if stop_event.is_set():
                    raise InterruptedError("Đã hủy tải bản cập nhật.")
                total_size += len(chunk)
                if total_size > MAX_INSTALLER_SIZE:
                    raise ValueError("Bộ cài tải về vượt quá giới hạn kích thước.")
                digest.update(chunk)
                output.write(chunk)
        if digest.hexdigest() != update.sha256:
            raise ValueError("SHA-256 bộ cài không khớp; đã hủy cập nhật.")
        return destination
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def launch_installer(installer_path: Path) -> None:
    if not installer_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy bộ cài cập nhật: {installer_path}")
    subprocess.Popen(
        [
            str(installer_path),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
        ],
        close_fds=True,
    )
