# Academic site blog

Hugo builds the blog at `/blog/`. The combined preview contains the academic homepage, publications, CV, research page and their original assets at their existing URLs. The blog starts with an empty index, series and tag directories, and an RSS feed at `/blog/index.xml`.

## Build and review locally

Run these commands from the repository root with Python 3.9 or later, Git and curl. The download helper extracts Hugo 0.170.1 into the temporary directory and verifies the platform archive against the SHA-256 pinned in `support/hugo.py`. It supports macOS and Linux amd64/arm64. The build uses Hugo’s bundled Chroma and the Python standard library. [Official release and checksums](https://github.com/gohugoio/hugo/releases/expanded_assets/v0.170.1)

```sh
work=$(mktemp -d)
python3 -B _blog/support/hugo.py "$work/bin/hugo"
python3 -B _blog/support/build.py --hugo "$work/bin/hugo" --output "$work/site-preview"
python3 -B _blog/support/qa.py --hugo "$work/bin/hugo" --site "$work/site-preview"
python3 -m http.server 8000 --bind 127.0.0.1 --directory "$work/site-preview"
```

Open `http://127.0.0.1:8000/blog/`. The server root is the combined artifact, so the link to the academic homepage, the stylesheet, and the feed resolve as they will on Pages. Stop the server with Ctrl-C. For another build, choose a fresh output directory outside the checkout.

The builder copies only paths listed in `support/legacy.sha256`. It checks each file before copying and reserves the root `blog` route, including case variants and equivalent HTML/Markdown names. Hugo runs in a temporary source directory containing the config, layouts, stylesheet and flat Markdown collection. It rejects duplicate output paths. Only a successful build moves the finished site into the requested destination.

The manifest describes the public files at `2cd22bf18155916a75dd08027f4a14126f340e13`. QA compares the worktree and artifact with the actual Git blobs at that commit, including a worktree check for `.gitignore`. A future change to the legacy site needs a reviewed update to its manifest and QA baseline. A clone used for QA must contain the baseline commit.

## Write a post

Each post is a Markdown file directly inside `_blog/content/`. The reserved `_index.md` supplies the blog title. To start a real article, run the following with the intended filename.

```sh
"$work/bin/hugo" new content --source _blog --noBuildLock article-name.md
```

| Front matter | Meaning |
| --- | --- |
| `title` | Reader-facing post title |
| `date` | Publication date or timestamp with offset, used for newest-first lists and RSS |
| `slug` | Unique URL segment in `/blog/<slug>/`. The `series` and `tags` routes are reserved. |
| `series` | Optional series label, as a string or a list |
| `tags` | List of topic labels, including an empty list |
| `draft` | Boolean. The archetype sets `true`. Set `false` when the post is ready for publication. |
| `summary` | Short description shown on the index, term pages, individual post and RSS item |

Write the body below the TOML front matter. Use fenced code labels `cpp` or `c++`, `coq`, `rocq`, and `bash`. The Rocq render hook selects the Coq lexer. Code blocks scroll horizontally on narrow screens. [Hugo syntax highlighting](https://gohugo.io/content-management/syntax-highlighting/)

The production build excludes drafts and future-dated posts. Draft source committed to this public repository is still readable on GitHub. Keep unpublished drafts in your private writing workspace or private local files, not in this public repository. The `draft` flag controls rendering, not confidentiality. QA creates its own public and draft Markdown under a temporary directory. An optional `--browser-site "$work/browser"` on the QA command retains the rendered test blog separately for inspection. Serve that directory on loopback and open `/blog/qa-wide/` to repeat the phone checks in [QA-REPORT.md](QA-REPORT.md).

## Current GitHub Pages behavior

The recorded Pages source is **Deploy from a branch → master → / (root)**, with API build type `legacy`. A push to `master` can trigger GitHub’s branch build and publication of the root. The existing HTML is static. The branch build does not invoke Hugo, and the default Jekyll filter skips `_blog/` and `.github/`. Merging just this scaffold would therefore leave the generated `/blog/` unavailable from that source. [Pages publishing sources](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site) · [Jekyll entry filter](https://github.com/jekyll/jekyll/blob/v3.10.0/lib/jekyll/entry_filter.rb)

**Blog build, QA and Pages** runs on pull requests, pushes to `master`, or manual dispatch. The build job has only `contents: read`, checks out without persistent credentials, runs the same combined build and QA, and uploads the ordinary `site-preview` artifact. Only the exact repository `yaohway/yaohway.github.io` on `refs/heads/master` with a `push` or `workflow_dispatch` event can package a Pages artifact or enter the deployment job. Pull requests and feature-branch dispatches cannot deploy. All actions are pinned to immutable commits. [Workflow](../.github/workflows/blog-preview.yml)

The deployment job depends on successful build/QA, uses the `github-pages` environment, and alone receives `pages: write` and `id-token: write`. It reads the current Pages mode and refuses deployment unless the owner has already selected Actions (`build_type=workflow`). It never creates or changes Pages configuration. Only the explicit combined directory is packaged, never the repository root. Deployments are serialized without cancelling an in-progress deployment.

## Administrator cutover to Actions

This draft PR is preparation, not permission to merge or deploy. The recorded account `evanmak` has push access and no admin/maintain grant. The owner or authorized maintainer must perform the source cutover; no new credentials are needed.

1. Keep the PR unmerged until its hosted build/QA passes, its artifact is reviewed, and the owner agrees to cutover. Record the current Pages source and last successful legacy build commit with the commands below. Initially this PR builds an **empty blog**, because no article has been supplied.
2. Configure/review the `github-pages` environment's production branch protection for `master` (and any required human approval). Immediately before the agreed merge, the owner selects **Settings → Pages → Build and deployment → Source → GitHub Actions**. Do not accept/create a suggested starter workflow. Existing published content is not replaced merely by changing this setting, but no new legacy build should be relied upon during cutover.
3. At the agreed time, merge the reviewed PR to `master`. This push runs build, QA, Pages packaging and the guarded deployment. Do not merge beforehand expecting a preview-only change: this version includes production automation. If the source remains legacy, the deployment preflight fails without changing settings. After a failed preflight, the owner can set the approved source and manually dispatch **Blog build, QA and Pages** on `master` at the reviewed commit.
4. Watch both build and deployment to success; confirm the recorded deployment URL. Compare all legacy served paths with `support/legacy.sha256` and check `/blog/`, `/blog/series/`, `/blog/tags/`, and `/blog/index.xml`. Later accepted pushes to `master` deploy automatically, so review article source before committing it.

```sh
gh api repos/yaohway/yaohway.github.io/pages --jq '{build_type,source,html_url}'
gh api repos/yaohway/yaohway.github.io/pages/builds/latest --jq '{status,commit}'
```

Official guidance: [publishing source settings](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site), [custom Pages workflow requirements](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## Administrator rollback to branch publishing

1. Stop any in-flight publishing run and disable **Blog build, QA and Pages** in **Actions**. Confirm that `master` still contains the verified legacy site at its root. If those files have since changed, restore the intended versions through the repository’s normal review process.
2. Open **Settings → Pages → Build and deployment → Source → Deploy from a branch**. Select branch **master**, folder **/ (root)**, and **Save**. [Branch and folder settings](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)
3. Watch the branch Pages build to completion. If saving the source produces no build, an authorized administrator can request one with `gh api --method POST repos/yaohway/yaohway.github.io/pages/builds`. Verify `build_type=legacy`, `source.branch=master`, `source.path=/`, and the successful build commit using the read commands above. [Pages build requests](https://docs.github.com/en/rest/pages/pages#request-a-github-pages-build)
4. Compare the public homepage, assets and PDFs with the recorded hashes. With this scaffold on the legacy root, the expected result for the generated `/blog/` and its feed is HTTP 404 after the branch deployment propagates.
