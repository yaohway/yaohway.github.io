"""Exercise the combined artifact and generate disposable Markdown for blog QA."""

import argparse
from email.utils import parsedate_to_datetime
from functools import partial
import hashlib
from html.parser import HTMLParser
from http.client import HTTPConnection
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from threading import Thread
from urllib.parse import quote, unquote, urljoin, urlsplit
from xml.etree import ElementTree as ET

from build import (BLOG, ROOT, build_site, check_blog_files, check_blog_route,
                   check_regular, legacy_hashes, new_output, render_blog)

BASE = "2cd22bf18155916a75dd08027f4a14126f340e13"
ORIGIN = "https://yaohway.github.io"


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.links = []
        self.post_links = []
        self.in_heading = False
        self.fences = []
        self.in_fence = False
        self.feed(path.read_text())
        self.close()

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "h2":
            self.in_heading = True
        if tag in {"a", "link"} and "href" in attrs:
            self.links.append(attrs["href"])
            if tag == "a" and self.in_heading:
                self.post_links.append(attrs["href"])
        if tag == "code" and "data-lang" in attrs:
            self.in_fence = True
            self.fences.append((attrs["data-lang"], set()))
        if tag == "span" and self.in_fence:
            self.fences[-1][1].update(re.findall(r"\bcolor:\s*(#[0-9a-fA-F]+)", attrs.get("style", "")))

    def handle_endtag(self, tag):
        if tag == "h2":
            self.in_heading = False
        if tag == "code":
            self.in_fence = False


def check_originals(site):
    manifest = legacy_hashes()
    records = subprocess.check_output(["git", "ls-tree", "-rz", BASE], cwd=ROOT)
    originals = set()
    for record in records.rstrip(b"\0").split(b"\0"):
        meta, name = record.decode().split("\t")
        mode, kind, oid = meta.split()
        require(kind == "blob" and mode in {"100644", "100755"}, f"unexpected base file: {name}")
        data = subprocess.check_output(["git", "cat-file", "blob", oid], cwd=ROOT)
        check_regular(ROOT / name)
        require((ROOT / name).read_bytes() == data, f"tracked file differs from base: {name}")
        if name != ".gitignore":
            originals.add(name)
            require(manifest.get(name) == hashlib.sha256(data).hexdigest(), f"manifest mismatch: {name}")
            require((site / name).read_bytes() == data, f"artifact differs from base: {name}")
    require(originals == set(manifest), "manifest paths differ from the reviewed base")
    print(f"PASS {len(originals) + 1} original worktree files and {len(originals)} served files match {BASE}")


def check_site(site):
    files = set(legacy_hashes()) | {"blog/" + name for name in check_blog_files(site / "blog")}
    directories = {parent.as_posix() for name in files for parent in Path(name).parents}
    for path in site.rglob("*"):
        rel = path.relative_to(site).as_posix()
        require(not path.is_symlink(), f"symlink in artifact: {rel}")
        require(rel in (directories if path.is_dir() else files), f"unexpected artifact path: {rel}")
    for name in files:
        check_regular(site / name)

    blog = site / "blog"
    page = Page(blog / "index.html")
    channel = ET.parse(blog / "index.xml").find("channel")
    require(channel.findtext("link") == ORIGIN + "/blog/", "RSS site URL")
    self_link = channel.find("{http://www.w3.org/2005/Atom}link")
    require(self_link.get("href") == ORIGIN + "/blog/index.xml", "RSS self URL")
    items = channel.findall("item")
    require([item.findtext("link") for item in items] ==
            [ORIGIN + link for link in page.post_links], "home order differs from RSS")
    dates = [parsedate_to_datetime(item.findtext("pubDate")) for item in items]
    require(dates == sorted(dates, reverse=True), "feed dates out of order")
    if not items:
        require("No posts yet." in (blog / "index.html").read_text(), "missing empty state")
    for html in blog.rglob("*.html"):
        links = Page(html).links
        require("/blog/index.xml" in links and "/blog/blog.css" in links, f"missing feed/CSS: {html}")
        for link in links:
            url = urlsplit(urljoin(ORIGIN + "/" + html.relative_to(site).as_posix(), link))
            if url.netloc != "yaohway.github.io" or url.scheme not in {"https", "http"}:
                continue
            decoded = unquote(url.path)
            target = site / decoded.lstrip("/")
            require(".." not in target.parts, f"invalid link in {html.name}: {link}")
            if target.is_dir():
                target = target / "index.html"
            require(target.is_file(), f"broken link in {html.name}: {link}")
    print(f"PASS exact artifact inventory ({len(files)} files), HTML links and RSS ({len(items)} items)")
    return files


def check_http(site, files):
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    with HTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(site))) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        connection = HTTPConnection(*server.server_address, timeout=10)
        try:
            routes = {"/" + name: name for name in files}
            for name in files:
                if name.endswith("/index.html") or name == "index.html":
                    routes["/" + name[:-len("index.html")]] = name
            for url, name in sorted(routes.items()):
                connection.request("GET", quote(url))
                response = connection.getresponse()
                require(response.status == 200 and response.read() == (site / name).read_bytes(),
                        f"HTTP route changed: {url}")
            absent = ["/.gitignore", "/.git/HEAD", "/_blog/hugo.toml", "/.github/workflows/blog-preview.yml",
                      "/_blog/support/build.py", "/_blog/QA-REPORT.md", "/blog/qa-draft-only/"]
            for url in absent:
                connection.request("GET", url)
                response = connection.getresponse()
                response.read()
                require(response.status == 404, f"unexpected HTTP {response.status} at {url}")
        finally:
            connection.close()
            server.shutdown()
            thread.join()
    print(f"PASS loopback HTTP: {len(routes)} routes returned byte-identical bodies, {len(absent)} exclusions returned 404")


def write_post(content, filename, fields, body):
    front = "\n".join(f"{key} = {json.dumps(value)}" for key, value in fields.items())
    (content / filename).write_text(f"+++\n{front}\n+++\n\n{body}\n")


def make_fixtures(work):
    content = work / "content"
    content.mkdir()
    shutil.copyfile(BLOG / "content/_index.md", content / "_index.md")
    wide = "0123456789abcdef" * 16
    fences = {"cpp": f'constexpr auto digits = "{wide}";',
              "coq": f"Lemma sample : True. (* {wide} *)\nProof. exact I. Qed.",
              "rocq": f"Definition sample : nat := 42. (* {wide} *)",
              "bash": f"printf '%s\\n' \"{wide}\""}
    ticks = "```"
    code = "\n\n".join(f"{ticks}{lang}\n{sample}\n{ticks}" for lang, sample in fences.items())
    common = dict(title="Earlier fixture", date="2022-01-05", slug="qa-earlier",
                  series=["QA notebook"], tags=["Build notes"], draft=False, summary="First summary.")
    write_post(content, "aaa.md", dict(common, tags=["Build notes", "Café"]), "Earlier body.")
    standalone = dict(title="Independent fixture", date="2023-02-10", slug="qa-independent",
                      tags=[], draft=False, summary="A note without a series.")
    write_post(content, "middle.md", standalone, "Standalone body.")
    latest = dict(common, title="Later & wider", date="2024-03-15T09:30:00-07:00", slug="qa-wide",
                  series="QA notebook", tags=["Build notes", "Types"], summary="Code & proofs.", weight=99)
    write_post(content, "zzz.md", latest, code)
    draft = dict(common, title="QA draft title", date="2025-04-20", slug="qa-draft-only", draft=True,
                 series=["QA hidden series"], tags=["QA hidden tag"], summary="QA hidden summary")
    write_post(content, "unpublished.md", draft, "QA hidden body")
    (content / "scratch.txt").write_text("QA unmounted file")
    (content / "private-probe").mkdir()
    write_post(content / "private-probe", "nested.md", dict(common, slug="qa-unmounted"), "QA unmounted body")
    return content


def check_fixtures(blog):
    latest, middle, earlier = (f"/blog/qa-{name}/" for name in ("wide", "independent", "earlier"))
    expected = [latest, middle, earlier]
    require(Page(blog / "index.html").post_links == expected, "fixture date order")
    for taxonomy, term in [("series", "qa-notebook"), ("tags", "build-notes"), ("tags", "types")]:
        route = f"/blog/{taxonomy}/{term}/"
        require(route in Page(blog / taxonomy / "index.html").links, f"missing term: {term}")
        require(route in Page(blog / "qa-wide/index.html").links, f"missing post taxonomy link: {term}")
        posts = [latest] if term == "types" else [latest, earlier]
        require(Page(blog / taxonomy / term / "index.html").post_links == posts, f"term order: {term}")
    single = (blog / "qa-wide/index.html").read_text()
    require("Later &amp; wider" in single and "Code &amp; proofs." in single
            and "2024-03-15T" in single, "individual post metadata")
    channel = ET.parse(blog / "index.xml").find("channel")
    items = channel.findall("item")
    require([item.findtext("guid") for item in items] == [ORIGIN + path for path in expected], "RSS GUIDs")
    require(items[0].findtext("title") == "Later & wider" and
            items[0].findtext("description") == "Code & proofs.", "RSS title/summary escaping")
    for path in blog.rglob("*"):
        if path.is_file():
            text = path.as_posix() + path.read_text().casefold()
            for marker in ("qa-draft", "qa draft", "qa hidden", "qa-hidden", "qa-unmounted", "qa unmounted"):
                require(marker not in text, f"excluded fixture leaked into {path.name}")
    blocks = Page(blog / "qa-wide/index.html").fences
    require([lang for lang, _ in blocks] == ["cpp", "coq", "coq", "bash"], f"lexer selection: {blocks}")
    require(all(len(colors) >= 2 for _, colors in blocks), f"expected colored Chroma tokens: {blocks}")
    print("PASS newest first, individual pages, optional series, multi-tag terms, RSS, draft/resource exclusion")
    print("PASS Chroma token colors per fence:", [(lang, len(colors)) for lang, colors in blocks])


def check_collisions(hugo, work):
    for number, name in enumerate(["blog", "blog/index.html", "Blog.html", "BLOG.htm", "blog.md", "Blog.markdown"]):
        root = work / f"legacy-collision-{number}"
        path = root / name
        path.parent.mkdir(parents=True)
        path.touch()
        try:
            check_blog_route(root)
        except ValueError as error:
            require("legacy route collision" in str(error), str(error))
        else:
            raise ValueError(f"accepted legacy collision: {name}")
    for name, slug in [("duplicate slug", "qa-same"), ("taxonomy route", "tags")]:
        case = work / slug
        content = case / "input"
        content.mkdir(parents=True)
        shutil.copyfile(BLOG / "content/_index.md", content / "_index.md")
        fields = dict(title="Collision", date="2020-01-01", slug=slug, tags=[], draft=False, summary="Probe")
        write_post(content, "one.md", fields, "")
        if name == "duplicate slug":
            write_post(content, "two.md", fields, "")
        try:
            render_blog(hugo, content, case, case / "output")
        except subprocess.CalledProcessError as error:
            diagnostic = next((line for line in error.output.splitlines()
                               if "duplicate" in line.lower() and slug in line), "")
            require(diagnostic, f"unexpected collision diagnostic: {error.output[:1200]}")
            print(f"PASS {name}: {diagnostic.strip()}")
        else:
            raise ValueError(f"Hugo accepted {name}")
    print("PASS legacy file, directory and HTML route collisions")


def run(hugo, site, browser_site):
    check_originals(site)
    check_http(site, check_site(site))
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory).resolve()
        fixture_site = work / "fixture-site"
        build_site(hugo, fixture_site, make_fixtures(work))
        check_site(fixture_site)
        check_fixtures(fixture_site / "blog")
        check_collisions(hugo, work)
        if browser_site:
            target = new_output(browser_site)
            shutil.copytree(fixture_site / "blog", target / "blog")
            print(f"Browser fixtures: {target}/blog/qa-wide/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hugo", type=Path, required=True)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--browser-site", type=Path, help="retain rendered fixtures in a new directory")
    args = parser.parse_args()
    try:
        run(args.hugo.resolve(), args.site.resolve(), args.browser_site)
    except subprocess.CalledProcessError as error:
        parser.exit(1, error.output or f"{error}\n")
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
