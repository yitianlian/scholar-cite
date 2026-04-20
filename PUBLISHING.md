# Publishing to PyPI

Two supported paths:

1. **Trusted Publishing via GitHub Actions (recommended)** — no API tokens
   anywhere, PyPI authenticates the GitHub Actions workflow via OIDC. Setup
   is a single form on PyPI. Release is a tag push. See
   [Trusted Publishing setup](#trusted-publishing-setup) below.
2. **Manual `twine upload` from your laptop** — covered further down. Good
   fallback if GitHub Actions is unavailable.

## Trusted Publishing setup

One-time PyPI configuration. No tokens, no `~/.pypirc`, no secrets shared
anywhere — PyPI trusts **this exact workflow file in this exact repo**.

### 1. Register the PyPI account (once per person)

https://pypi.org/account/register/ → enable 2FA.

### 2. Add a "Pending publisher" for this repo

Because the `scholar-cite` project doesn't exist on PyPI yet, you register
it as a pending publisher. Go to:

https://pypi.org/manage/account/publishing/

Scroll to **"Add a new pending publisher"** and fill in exactly:

| Field | Value |
| ----- | ----- |
| PyPI Project Name | `scholar-cite` |
| Owner | `yitianlian` |
| Repository name | `scholar-cite` |
| Workflow name | `publish-to-pypi.yml` |
| Environment name | *(leave blank)* |

Submit. Nothing else to configure.

### 3. Publish v0.1.0 (one-off, because the tag already exists)

The workflow was added after v0.1.0 was tagged, so the `on: push: tags`
trigger missed the train. Dispatch it manually once:

```bash
gh workflow run publish-to-pypi.yml --ref v0.1.0 -F ref=v0.1.0
gh run watch                                   # optional: tail the live log
```

Check https://pypi.org/project/scholar-cite/ — it should appear within
~30 s of the workflow's "Publish" step finishing.

### 4. Future releases

Just tag + push. The workflow triggers automatically:

```bash
# bump version in src/scholar_cite/__init__.py and pyproject.toml,
# update CHANGELOG, commit that.
git tag -a v0.1.1 -m "scholar-cite v0.1.1"
git push origin v0.1.1      # ← this triggers publish-to-pypi.yml
```

## Manual fallback (no GitHub Actions)

Use this path if you need to publish from a laptop without GitHub Actions
(e.g. Actions is down, or you're releasing a hotfix from a personal fork).

### One-time setup

### 1. Register the accounts

- **PyPI**: https://pypi.org/account/register/
- **TestPyPI** (separate account, same username fine): https://test.pypi.org/account/register/

Enable 2FA on both — PyPI requires it for API tokens.

### 2. Generate API tokens

- PyPI: https://pypi.org/manage/account/token/ — create a token.
  - For the very first upload, the scope must be **"Entire account"** because
    the project doesn't exist on PyPI yet.
  - After the first upload, rotate it to a project-scoped token for
    `scholar-cite` (safer blast radius).
- TestPyPI: https://test.pypi.org/manage/account/token/ — same idea.

Tokens look like `pypi-AgEIcHlwaS5vcmc...` (PyPI) or
`pypi-AgENdGVzdC5weXBpLm9yZw...` (TestPyPI).

### 3. Store credentials

Pick **one** of these:

**Option A — `~/.pypirc`** (persists, used by twine automatically):

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-AgEI...

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-AgEN...
```

`chmod 600 ~/.pypirc` so only you can read it.

**Option B — env vars** (ephemeral, good for CI):

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-AgEI...   # or pypi-AgEN... for TestPyPI
```

## Per-release workflow

From the project root, with the dev venv active:

### 1. Bump the version

Edit `src/scholar_cite/__init__.py` and `pyproject.toml`. Keep them in sync.

```python
# src/scholar_cite/__init__.py
__version__ = "0.1.1"
```

```toml
# pyproject.toml
version = "0.1.1"
```

Update `CHANGELOG.md`: move the `[Unreleased]` section contents under a new
`[0.1.1] — YYYY-MM-DD` heading.

### 2. Build the artefacts

```bash
rm -rf dist/ build/
python -m build          # produces dist/scholar_cite-0.1.1-*.whl + .tar.gz
twine check dist/*       # should print PASSED for both
```

### 3. Dry-run to TestPyPI (first time strongly recommended)

```bash
twine upload --repository testpypi dist/*
```

Verify in a fresh venv:

```bash
python -m venv /tmp/sc-test && /tmp/sc-test/bin/pip install \
    --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    scholar-cite
/tmp/sc-test/bin/playwright install chromium
/tmp/sc-test/bin/scholar-cite --version
```

The `--extra-index-url` is important because TestPyPI doesn't mirror common
dependencies like `typer`; fall back to the real PyPI for those.

### 4. Real upload

```bash
twine upload dist/*
```

Post-upload: https://pypi.org/project/scholar-cite/ should show the new
version within a few seconds. After that:

```bash
pipx install scholar-cite          # anyone in the world can now run this
playwright install chromium
```

### 5. Tag + GitHub release

```bash
git tag -a v0.1.1 -m "scholar-cite v0.1.1"
git push origin v0.1.1

gh release create v0.1.1 \
    --title "scholar-cite v0.1.1" \
    --notes-file <(sed -n '/^## \[0.1.1\]/,/^## \[/p' CHANGELOG.md | head -n -1) \
    dist/scholar_cite-0.1.1-py3-none-any.whl \
    dist/scholar_cite-0.1.1.tar.gz
```

The sed snippet pulls just this version's section out of the CHANGELOG so
you don't maintain a separate release-notes file.

## Undoing a bad release

PyPI does not allow re-uploading the same version number, even after
deletion. If you ship a broken release:

1. Yank the version (go to https://pypi.org/manage/project/scholar-cite/ →
   release → "Options" → "Yank release"). Yanked versions remain installable
   only when someone pins to them explicitly — `pipx install scholar-cite`
   will skip them.
2. Bump the patch and publish a fix.

## Name squatting / first-release note

As of 2026-04-19, `scholar-cite` is **available** on PyPI (`curl` to
`https://pypi.org/pypi/scholar-cite/json` returns 404). The first
`twine upload dist/*` claims it. If you plan to publish, do so promptly.
