# Local blog QA · 19 November 2026

**Pass.** The combined artifact contains 86 files and zero posts. All 81 original served files match the public-site base byte for byte. All 82 original tracked files, including `.gitignore`, also match in the worktree. The empty production blog opened in Orca with the heading “Blog” and the message “No posts yet.”

## Scope and inventory

The supported Orca CLI identified the public `yaohway/yaohway.github.io` worktree on `evanmak/hugo-blog-scaffold` at base `2cd22bf18155916a75dd08027f4a14126f340e13`. There was no repository `AGENTS.md`. The base contains static W3layouts HTML with relative asset references, five stylesheets, ten scripts, five font files, 43 images, 13 PDFs and the template license. The four HTML routes are `/index.html`, `/cv.html`, `/publications.html` and `/research.html`. Inspection found no generator project, root blog file or directory, GitHub workflow, or `.nojekyll` in the base.

The recorded Pages configuration supplied for this task was `build_type=legacy`, `master:/`. The recorded `gh` identity was `evanmak`, with `push=true` and `admin=false`. All site reads and QA used the local public-site checkout and disposable synthetic content. The external tool downloads came from the public Hugo release.

## Build and route evidence

The run used macOS arm64, Python 3.9.6, and official Hugo `v0.170.1-c8b03de9564cf846a3986e879727d638bb96ab33`. The macOS package was expanded locally. The Linux amd64 archive selected by CI also matched its pin and contained the expected regular `hugo` ELF executable. [Release digests](https://github.com/gohugoio/hugo/releases/expanded_assets/v0.170.1)

| Check | Observed result |
| --- | --- |
| macOS package SHA-256 | `f7672f5e47f13c488ecd9ae96450ed9d2044629d60fe23570312e896c1918d73` |
| Linux amd64 archive SHA-256 | `841a5462853aefc9942e4de1e8a5d75584b6a5181941e6ad3f1d745190e03cd8` |
| Legacy manifest | 81 paths. Manifest file SHA-256 `a2e864827438354aec0146d12404ec44901cf8ed09e1a2f8ad5c3657e68a00d5` |
| Base, worktree and artifact `index.html` | SHA-256 `b56ae3cc895f44d730146902d116af5eceb60b077cb22061f150d837c1f75aa9` |
| Base and worktree `.gitignore` | SHA-256 `cec9bc049ba09e71939866fb783dc1592757e89f84be358ebc5a53587ca00db1` |
| Combined builds | 86 files, 23,409,759 bytes. A second clean build passed `diff -qr` with exit 0. |
| New artifact paths | `blog/index.html`, `blog/index.xml`, `blog/series/index.html`, `blog/tags/index.html`, `blog/blog.css` |
| Loopback HTTP | 90 distinct URLs returned 200 with the expected bytes. This covered every public file, `/`, and the three blog directory URLs. Seven probes for source, Git metadata, workflow, QA and draft paths returned 404. |
| Input isolation | A synthetic changed legacy file failed its SHA-256 check. An existing output directory was refused. The clean artifact matched the exact expected file and directory inventory. |
| Workflow | Locally parsed YAML showed one preview job, pull-request and manual triggers, `contents: read`, credential persistence disabled and two full-SHA action references. Upload selects only the combined production directory. |

## Populated fixture evidence

QA generated three public posts and one newer draft outside the checkout. The populated build contained 93 files. The production artifact was built separately.

| Check | Observed result |
| --- | --- |
| Home and individual posts | The index linked `qa-wide` (2024), `qa-independent` (2023) and `qa-earlier` (2022) in that order despite conflicting filename order and weight. The latest post displayed its title, date, summary, body, series and tags at its explicit slug. |
| Taxonomies | Two posts shared a series and tag in newest-first order. A second tag selected just the latest post. Unicode term links resolved. The independent post built with an empty tag list and omitted series. |
| RSS | Zero items in production, three in the fixture feed. The XML parser verified order, absolute item URLs and GUIDs, publication dates, the self link and literal ampersands in the parsed title and summary. |
| Draft and source exclusions | The draft URL, title, body, summary and draft-only terms were absent from all rendered files. A nested Markdown probe and sidecar text were excluded. A separate future-dated post was excluded. |
| Chroma | The four fences `cpp`, `coq`, `rocq` and `bash` selected `cpp`, `coq`, `coq` and `bash`. Their token spans had 4, 3, 3 and 2 distinct color values. A separate `c++` alias check also produced colored tokens. |
| Authoring | `hugo new content --source <scratch-source> --noBuildLock qa-author-note.md` created all required metadata with a generated date and slug, optional series commented out, and boolean `draft = true`. |
| Collision detection | Six legacy probes were rejected, covering a file, directory, HTML and Markdown spellings and case variants. Duplicate post slugs and a post slug of `tags` each failed the real Hugo build with a duplicate target path diagnostic. |

## Mobile browser measurements

Orca 1.4.263 loaded the rendered wide-code post over loopback in Chromium 150.0.7871.250. Each fence contained a 256-character token or comment. Both phone viewports reported a coarse pointer. Dimensions below are CSS pixels. Width pairs give `clientWidth / scrollWidth`.

| Viewport | DPR | Document | Body | Each code block’s client width | Code scroll widths, C++ / Coq / Rocq / bash | Document horizontal offset |
| --- | ---: | --- | --- | ---: | --- | ---: |
| 320 × 568 | 2 | 320 / 320 | 320 / 320 | 286 | 2470 / 2470 / 2556 / 2374 | 0 |
| 390 × 844 | 3 | 390 / 390 | 390 / 390 | 349 | 2470 / 2470 / 2556 / 2374 | 0 |

All eight block measurements reported `overflow-x: auto`. Setting each block’s `scrollLeft` to 96 moved it 96 pixels. The probe restored the starting positions. Both viewport screenshots were visually checked. The production preview, screenshots and test fixtures were kept separate.

## Reproduction

From the repository root, use a new temporary directory for each run.

```sh
work=$(mktemp -d)
python3 -B _blog/support/hugo.py "$work/bin/hugo"
python3 -B _blog/support/build.py --hugo "$work/bin/hugo" --output "$work/site-preview"
python3 -B _blog/support/qa.py --hugo "$work/bin/hugo" --site "$work/site-preview" --browser-site "$work/browser"
python3 -m http.server 8001 --bind 127.0.0.1 --directory "$work/browser"
```

In a second shell in the same Orca worktree, create a tab and set `page_id` to the returned `result.browserPageId`. Use the Orca CLI executable selected by the session.

```sh
orca tab create --url http://127.0.0.1:8001/blog/qa-wide/ --json
orca viewport --page "$page_id" --width 320 --height 568 --scale 2 --mobile --json
orca eval --page "$page_id" --expression "$(cat _blog/support/mobile-qa.js)" --json
orca viewport --page "$page_id" --width 390 --height 844 --scale 3 --mobile --json
orca eval --page "$page_id" --expression "$(cat _blog/support/mobile-qa.js)" --json
```

## Verification limits

The browser checks used real Chromium layout and scrolling under mobile emulation. Physical phones and mobile Safari were outside this run. HTTP evidence covers local artifact routes and bytes. GitHub-hosted Actions, Pages CDN behavior, and the administrator cutover and rollback were not exercised. The implementation ends at a local review artifact. The separate publishing procedure is in the [administrator runbook](README.md#administrator-cutover-to-actions).

## Independent live-site preservation check

After local worker QA, the coordinator fetched the currently served public `index.html`, `cv.html`, `publications.html`, and `research.html` over HTTPS on 19 November 2026. Each response matched its original tracked file byte-for-byte by SHA-256. This confirms that copying the existing HTML preserves its current rendered source rather than substituting unbuilt generator input. No remote deployment or Pages configuration change was made.
