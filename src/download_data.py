from __future__ import annotations

import argparse
import tarfile
import time
import urllib.request
from pathlib import Path


RAW_URL = "https://data.recsys.synerise.com/dataset/synerise_dataset.tar.gz"
CHALLENGE_URL = "https://data.recsys.synerise.com/dataset/challenge_dataset.tar.gz"


def _is_valid_tar(path: Path) -> bool:
    return path.exists() and tarfile.is_tarfile(path)


def download_file(url: str, destination: Path, force: bool = False, retries: int = 3) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_name(destination.name + ".part")

    if destination.exists() and not force:
        if _is_valid_tar(destination):
            print(f"[skip] already downloaded: {destination}")
            return destination
        print(f"[warn] invalid cached archive detected, redownloading: {destination}")
        destination.unlink()

    if force:
        for path in (destination, temp_path):
            if path.exists():
                path.unlink()

    def _report(block_count: int, block_size: int, total_size: int) -> None:
        if total_size <= 0:
            return
        downloaded = block_count * block_size
        progress = min(downloaded / total_size, 1.0)
        print(f"\r[download] {progress:.1%}", end="")

    last_error = None
    for attempt in range(1, retries + 1):
        if temp_path.exists():
            temp_path.unlink()
        try:
            print(f"[download] attempt {attempt}/{retries}: {url}")
            urllib.request.urlretrieve(url, temp_path, _report)
            if not _is_valid_tar(temp_path):
                raise RuntimeError(f"downloaded file is not a valid tar archive: {temp_path}")
            print(f"\n[saved] {temp_path}")
            temp_path.replace(destination)
            return destination
        except Exception as exc:
            last_error = exc
            print(f"\n[retry] download failed on attempt {attempt}: {exc}")
            if attempt < retries:
                time.sleep(min(10 * attempt, 30))

    raise RuntimeError(f"Failed to download {url} after {retries} attempts") from last_error


def extract_archive(archive_path: Path, output_dir: Path, force: bool = False) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    sentinel = output_dir / ".extracted"
    if sentinel.exists() and not force:
        print(f"[skip] already extracted: {output_dir}")
        return output_dir

    print(f"[extract] {archive_path} -> {output_dir}")
    with tarfile.open(archive_path, "r:gz") as archive:
        archive.extractall(output_dir)
    sentinel.write_text("ok", encoding="utf-8")
    print(f"[ready] {output_dir}")
    return output_dir


def download_dataset(variant: str = "raw", extract: bool = True, force: bool = False) -> Path:
    if variant not in {"raw", "challenge"}:
        raise ValueError("variant must be one of: raw, challenge")

    url = RAW_URL if variant == "raw" else CHALLENGE_URL
    archive_path = Path("data/raw") / Path(url).name
    extract_dir = Path("data/raw") / ("synerise_dataset" if variant == "raw" else "challenge_dataset")
    archive = download_file(url, archive_path, force=force)
    if extract:
        return extract_archive(archive, extract_dir, force=force)
    return archive


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download official Synerise RecSys 2025 datasets.")
    parser.add_argument("--variant", choices=["raw", "challenge"], default="raw")
    parser.add_argument("--extract", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = download_dataset(variant=args.variant, extract=args.extract, force=args.force)
    print(f"[done] {output}")


if __name__ == "__main__":
    main()
