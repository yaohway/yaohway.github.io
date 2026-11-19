"""Extract the pinned official Hugo binary into a local tool directory."""

import argparse
import hashlib
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile

VERSION = "0.170.1"
ARCHIVES = {
    "darwin-universal.pkg": "f7672f5e47f13c488ecd9ae96450ed9d2044629d60fe23570312e896c1918d73",
    "linux-amd64.tar.gz": "841a5462853aefc9942e4de1e8a5d75584b6a5181941e6ad3f1d745190e03cd8",
    "linux-arm64.tar.gz": "6f57f13bc47c000c0d36c7f5a446d6c06f7956d8e102cc2a13735e0c0225b2d2",
}


def check_version(binary):
    version = subprocess.check_output([str(binary), "version"], text=True).strip()
    if not re.match(rf"^hugo v{re.escape(VERSION)}(?:[-+ ]|$)", version):
        raise ValueError(f"expected Hugo {VERSION}, got {version}")
    return version


def fetch(binary):
    binary = binary.absolute()
    if binary.exists() or binary.is_symlink():
        raise ValueError(f"tool destination already exists: {binary}")
    if platform.system() == "Darwin":
        asset = "darwin-universal.pkg"
    elif platform.system() == "Linux" and platform.machine() in ("x86_64", "aarch64"):
        arch = {"x86_64": "amd64", "aarch64": "arm64"}[platform.machine()]
        asset = f"linux-{arch}.tar.gz"
    else:
        raise ValueError("supported release binaries: macOS universal, Linux amd64/arm64")

    binary.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=binary.parent) as directory:
        work = Path(directory)
        archive = work / f"hugo_{VERSION}_{asset}"
        url = f"https://github.com/gohugoio/hugo/releases/download/v{VERSION}/{archive.name}"
        subprocess.run(["curl", "--fail", "--silent", "--show-error", "--location",
                        "--proto", "=https", "--retry", "2", "--output", str(archive), url],
                       check=True)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest != ARCHIVES[asset]:
            raise ValueError(f"SHA-256 mismatch for {archive.name}: {digest}")
        print(f"Verified {archive.name}  {digest}", flush=True)
        if asset.endswith(".pkg"):
            # Expand the payload locally. No package installation or installer scripts.
            subprocess.run(["pkgutil", "--expand-full", str(archive), str(work / "pkg")], check=True)
            candidate = work / "pkg/Payload/hugo"
        else:
            candidate = work / "hugo"
            with tarfile.open(archive, "r:gz") as bundle:
                member = bundle.getmember("hugo")
                if not member.isfile():
                    raise ValueError("expected a regular hugo binary in the archive")
                with bundle.extractfile(member) as source, candidate.open("xb") as target:
                    shutil.copyfileobj(source, target)
        candidate.chmod(0o755)
        print(check_version(candidate))
        candidate.rename(binary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path, help="new file, e.g. /tmp/site-tools/hugo")
    try:
        fetch(parser.parse_args().binary)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")
