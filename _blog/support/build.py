"""Build the reviewed legacy files and the Hugo blog into a new directory."""

import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile

from hugo import check_version

BLOG = Path(__file__).resolve().parents[1]
ROOT = BLOG.parent
MANIFEST = BLOG / "support/legacy.sha256"
BLOG_FILES = {"index.html", "index.xml", "blog.css", "series/index.html", "tags/index.html"}


def legacy_hashes():
    hashes = {}
    for line in MANIFEST.read_text().splitlines():
        digest, name = line.split("  ", 1)
        hashes[name] = digest
    return hashes


def check_blog_route(root):
    for entry in root.iterdir():
        if entry.name.casefold() in {"blog", "blog.html", "blog.htm", "blog.md", "blog.markdown"}:
            raise ValueError(f"legacy route collision at /{entry.name}")


def check_regular(path):
    if path.resolve() != path or not path.is_file():
        raise ValueError(f"expected a regular file without symlinks: {path}")


def copy_legacy(root, site):
    for name, expected in legacy_hashes().items():
        rel = Path(name)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"invalid legacy path: {name}")
        path = root / rel
        check_regular(path)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"legacy SHA-256 mismatch: {name}")
        target = site / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            output.write(data)


def check_blog_files(blog):
    files = set()
    for path in blog.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symlink in blog output: {path}")
        if path.is_dir():
            continue
        check_regular(path)
        rel = path.relative_to(blog)
        files.add(rel.as_posix())
        if rel.as_posix() in BLOG_FILES:
            continue
        is_post = len(rel.parts) == 2
        is_term = len(rel.parts) == 3 and rel.parts[0] in {"tags", "series"}
        if (not (is_post or is_term) or rel.name != "index.html"
                or any(part.startswith((".", "_")) for part in rel.parts)):
            raise ValueError(f"unexpected blog output: {rel}")
    if BLOG_FILES - files:
        raise ValueError(f"missing blog output: {sorted(BLOG_FILES - files)}")
    return files


def render_blog(hugo, content, work, output):
    # Give Hugo only the flat Markdown collection, templates, config and one public
    # stylesheet. Scratch files, page-bundle resources and sibling directories
    # cannot enter the artifact through an implicit Hugo mount.
    source = work / "source"
    (source / "content").mkdir(parents=True)
    for path in [BLOG / "hugo.toml", BLOG / "static/blog.css", *(BLOG / "layouts").rglob("*")]:
        if path.is_dir() and not path.is_symlink():
            continue
        check_regular(path)
        target = source / path.relative_to(BLOG)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    for path in content.glob("*.md"):
        if not path.name.startswith("."):
            check_regular(path)
            shutil.copyfile(path, source / "content" / path.name)
    result = subprocess.run([
        str(hugo), "--source", str(source), "--destination", str(output),
        "--cacheDir", str(work / "cache"), "--noBuildLock", "--environment", "production",
        "--buildDrafts=false", "--buildFuture=false", "--buildExpired=false",
        "--printPathWarnings", "--panicOnWarning",
    ], cwd=source, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
    print(result.stdout, end="", flush=True)
    check_blog_files(output)


def new_output(path):
    target = path.resolve()
    if target.is_relative_to(ROOT) or path.is_symlink() or target.exists():
        raise ValueError(f"choose a new output directory outside the checkout: {path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def build_site(hugo, output, content=BLOG / "content"):
    check_blog_route(ROOT)
    print(check_version(hugo), flush=True)
    output = new_output(output)
    with tempfile.TemporaryDirectory(dir=output.parent) as directory:
        work = Path(directory)
        site = work / "site"
        copy_legacy(ROOT, site)
        render_blog(hugo, content, work, work / "rendered")
        (work / "rendered").rename(site / "blog")
        site.rename(output)
    print(f"Built {output} with {len(legacy_hashes())} verified legacy files", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hugo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        build_site(args.hugo.resolve(), args.output)
    except subprocess.CalledProcessError as error:
        parser.exit(1, error.output or f"{error}\n")
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
