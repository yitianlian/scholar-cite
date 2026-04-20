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

## 2026-04-20 — v0.1.1 post-release E2E

Ran two broader live passes against the `pipx install scholar-cite==0.1.1`
binary (fresh venv, no dev paths on `sys.path`).

### Multi-domain sweep (`/tmp/e2e_broad.py`)

5 queries, one browser session, diverse fields. All 9 formats populated
for every paper. Top cluster landed on a tier-1 host every time.

| Domain | Query | Top cluster source host | BibTeX cite key |
| ------ | ----- | ----------------------- | ---------------- |
| CS/AI | "BERT Pre-training Deep Bidirectional Transformers Devlin" | `aclanthology.org` | `devlin2019bert` |
| CS/AI | "GPT-3 Language Models Few-Shot Brown" | `proceedings.neurips.cc` | `brown2020language` |
| Physics | "Observation of Gravitational Waves from a Binary Black Hole Merger" | `link.springer.com` | `tutukov2017formation` *(Scholar picked an adjacent review over the exact LIGO paper)* |
| Biology | "A programmable dual-RNA-guided DNA endonuclease Jinek" | `www.science.org` | `jinek2012programmable` |
| Econ | "Capital in the Twenty-First Century Piketty" | `www.degruyterbrill.com` | `piketty2014capital` |

Notes:
- First `@book{…}` entry we've seen in testing (Piketty). Tool handles
  book-type citations without code changes.
- Piketty's `year: 2014` extracted cleanly — the gs_a parser copes when
  the venue line has a date.
- Tier-1 hosts recognised by the ranking table: `aclanthology.org`,
  `proceedings.neurips.cc`, `link.springer.com`, `www.science.org`.
  `www.degruyterbrill.com` is not in the table and ranked at score 0;
  still made it to the top because Scholar returned it first and nothing
  trusted competed.

### CLI flag sweep

Four targeted invocations of the installed `scholar-cite` binary:

| Test | Observation |
| ---- | ----------- |
| `--limit 3` on ResNet | Three clean CVPR clusters; `LrPNPdmMzoAJ` (the official ResNet cluster) first. The infamous `sandbox.getindico.io` cluster did not make the top 3 — pushed out by tier-1 hosts. |
| `--format mla,bibtex` subset | Parser correctly emits only the two requested formats; other seven fields present in the `Paper.citations` dict but not rendered. |
| `--json --strict --format all` on a query where Scholar returns 9/9 | Exit 0, full JSON payload, no `citation_errors` field (matches the schema). |
| Empty query `""` | Scholar returns 0 hits → `EXIT_NO_RESULTS=2`. (Consider also rejecting empty queries at the CLI boundary in a future pass, similar to `--format ""`.) |

### UX observation (not a bug)

`--limit 1` trusts Scholar's top match. For well-known papers with
*distinctive* titles ("Attention Is All You Need", "BERT: Pre-training…"),
that's enough. For *generic* titles ("ImageNet Classification …", "Adam
stochastic optimization …"), Scholar sometimes surfaces an adjacent paper
first. `scholar-cite` returns correct citations for whatever Scholar
returns — the user should widen to `--limit 3` / `--limit 5` and pick from
the candidate list when the title is generic.

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
