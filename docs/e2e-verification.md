# E2E Verification Log

Captures the live checks run against Google Scholar after each significant
change. Each entry is a timestamped snapshot; cookies persist between them,
so earlier runs warm up the session for later ones.

---

## 2026-04-19 — Post-review fixes + packaging

### Unit suite

```
$ pytest tests/ -q
......................................                                   [100%]
38 passed in 0.21s
```

### 1. `auth status` — hardened against corrupt caches

```
$ scholar-cite auth status
{
  "path": "/Users/…/scholar-cite/cookies.json",
  "exists": true,
  "saved_at": 1776607974,
  "cookie_count": 6,
  "domains": [".google.com", ".scholar.google.com", "www.google.com", "www.refworks.com"]
}
```

### 2. Ranking — ResNet `--limit 1` lands on the clean cluster

Prior to the cv-foundation fix, the unknown `sandbox.getindico.io` cluster
could win. After adding `cv-foundation.org` + `thecvf.com` at tier-1:

```
$ scholar-cite cite "Deep Residual Learning for Image Recognition" --format bibtex --limit 1
[browser] parsed 10 result(s), kept top 1 after source-quality ranking; fetching citations…
[browser]   [1/1] LrPNPdmMzoAJ — 9/9 formats

    Bibtex:
        @inproceedings{he2016deep,
          title={Deep residual learning for image recognition},
          author={He, Kaiming and Zhang, Xiangyu and Ren, Shaoqing and Sun, Jian},
          booktitle={Proceedings of the IEEE conference on computer vision and pattern recognition},
          pages={770--778},
          year={2016}
        }
```

Author order correct (`He, Kaiming`), no fabricated `volume=34`, clean cite key.

### 3. `--strict` + `--json` — complete result, exit 0

```
$ scholar-cite cite "Attention Is All You Need" --format all --limit 1 --json --strict
[browser]   [1/1] 5Gohgn6QFikJ — 9/9 formats
Found 1 result(s).
[
  {
    "cluster_id": "5Gohgn6QFikJ",
    "title": "Attention is all you need",
    …
    "citations": {
      "mla":       "Vaswani, Ashish, et al. …",
      "apa":       "Vaswani, A., Shazeer, N., …",
      "chicago":   "Vaswani, Ashish, Noam Shazeer, …",
      "harvard":   "Vaswani, A., Shazeer, N., …",
      "vancouver": "Vaswani A, Shazeer N, …",
      "bibtex":    "@article{vaswani2017attention, …",
      "endnote":   "%0 Journal Article\r\n%T Attention is all you need\r\n…",
      "refman":    "TY  - JOUR\r\nT1  - Attention is all you need\r\n…",
      "refworks":  "# Google Scholar's RefWorks export is an external redirect.\n# Import URL:\nhttp://www.refworks.com/express?…"
    }
  }
]
```

All 9 fields populated. No `citation_errors` key, which the schema promises
only when something is missing.

### 4. Install-from-wheel smoke test

```
$ python -m build
Successfully built scholar_cite-0.1.0.tar.gz and scholar_cite-0.1.0-py3-none-any.whl

$ python -m venv /tmp/sc_install_test
$ /tmp/sc_install_test/bin/pip install dist/scholar_cite-0.1.0-py3-none-any.whl
Successfully installed scholar-cite-0.1.0 …

$ /tmp/sc_install_test/bin/scholar-cite cite "Generative Adversarial Nets" --format bibtex --limit 1
[browser]   [1/1] GTujzvUZN6YJ — 9/9 formats

    Bibtex:
        @article{goodfellow2014generative,
          title={Generative adversarial nets},
          author={Goodfellow, Ian J and Pouget-Abadie, Jean and …},
          journal={Advances in neural information processing systems},
          volume={27},
          year={2014}
        }
```

The wheel is self-sufficient: a fresh venv with only the wheel installed runs
the full browser pipeline and produces a correct citation.

### Wheel + sdist contents

```
dist/
├── scholar_cite-0.1.0-py3-none-any.whl   (23.8 KB)
└── scholar_cite-0.1.0.tar.gz              (39.0 KB)
```

Wheel includes every module under `scholar_cite/`, the MIT `LICENSE` (under
`licenses/`), and a proper `entry_points.txt` that registers the
`scholar-cite` console script. The sdist additionally carries `docs/`,
`examples/`, `tests/`, `CHANGELOG.md`, and the bare `pyproject.toml`.

## Known cosmetic issues (not blockers)

The citation *content* is always correct, but the top-level `Paper` metadata
that comes from parsing Scholar's search-result row can be noisy:

- `authors` sometimes includes tail fragments like `"N Parmar … - Advances
  in neural …"` because Scholar's `gs_a` string format varies.
- `year` can be `null` when the second `gs_a` segment is `proceedings.neurips.cc`
  rather than a date.

These affect only the wrapper metadata in `--json` output, not the nine
citation strings. Tracked as a cleanup item; out of scope for the current
review fixes.
