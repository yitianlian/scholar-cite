# scholar-cite

[English](README.md) · [简体中文](README.zh-CN.md)

> 一个 Python CLI，给定论文标题，从 **Google Scholar** 抓取全部 9 种引用格式 —— `BibTeX`、`EndNote`、`RefMan`（RIS）、`RefWorks`、`MLA`、`APA`、`Chicago`、`Harvard`、`Vancouver`。

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-48%20passing-brightgreen.svg)](#运行测试)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**状态**：MVP。9 种格式在真实 Google Scholar 上端到端验证通过（见
[`docs/test-run-2026-04-19.md`](docs/test-run-2026-04-19.md) 与
[`docs/e2e-verification.md`](docs/e2e-verification.md)）。代码组织见
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

---

## 目录

1. [为什么要有这个工具](#为什么要有这个工具)
2. [安装](#安装)
3. [快速上手](#快速上手)
4. [用法](#用法)
5. [工作原理](#工作原理)
6. [格式缺失时会怎样](#格式缺失时会怎样)
7. [按来源质量排序候选](#按来源质量排序候选)
8. [Claude Code 与 Codex 集成](#claude-code-与-codex-集成)
9. [已实现与计划中](#已实现与计划中)
10. [运行测试](#运行测试)
11. [项目结构](#项目结构)
12. [文档索引](#文档索引)
13. [License](#license)

---

## 为什么要有这个工具

Google Scholar 的 "Cite" 弹窗对任何一篇论文都能给出 9 种干净的引用格式。但**批量拿**很痛苦：没有公开 API，纯 HTTP 请求一两次就会被 403，导出接口又返回 `text/plain` 下载，`requests` 和 headless 浏览器都应付不了。`scholar-cite` 把这些全部包住，你只需要：

```bash
scholar-cite cite "Attention Is All You Need" --format bibtex
```

就能得到一条可用的 BibTeX。

## 安装

整体**两步**：

1. 安装 Python 包（所有 Python 依赖会自动装齐）
2. 下载 Playwright 驱动的 Chromium 浏览器二进制（约 150 MB，只用装一次）

要求 Python ≥ 3.10（在 3.10 – 3.14 上测过）。

### 安装前 FAQ

**能直接 `pip install scholar-cite` 吗？**
**可以** —— 从 v0.1.0 起已经发到 PyPI：<https://pypi.org/project/scholar-cite/>。见下面选项 A。

**要 API key 或 token 吗？**
**不要。** Google Scholar 没有公开 API，本工具驱动真浏览器解析 Scholar 自己的 HTML，不走任何认证。首次运行时浏览器窗口里如果弹验证码，你手动点一下就行，cookies 会持久化到本地，之后几天都不会再问。

**依赖要手动装吗？**
不要。`pip` / `pipx` 会读 `pyproject.toml` 自动拉齐所有 Python 依赖（`typer`、`scholarly`、`requests`、`beautifulsoup4`、`lxml`、`playwright`）。**唯一**需要手动的一步是第 2 步的 `playwright install chromium` —— pip 的 wheel 不适合塞 150 MB 的浏览器二进制，所以 Playwright 提供了单独的命令。

**什么是 Playwright？为什么必须要？**
[Playwright](https://playwright.dev/python/) 是微软出的浏览器自动化库，Python 端就是 `playwright` 这个包。用它是因为：
- Google Scholar **对纯 HTTP 请求会直接返回 403**，连 `scholarly` 库都会中招。
- Scholar **能识别 headless 浏览器**，会弹一个 "Please show you're not a robot" 的反爬页。
- 真 Chromium（headful）加上轻量 stealth 补丁（隐藏 `navigator.webdriver` 等标志）就能稳定跑通。Scholar 真的弹验证码时，会显示在可见窗口里，你点一次，cookies 存到 `~/.cache/scholar-cite/cookies.json`，后续运行静默复用。

我们**不**用 Selenium、pyppeteer、纯 `requests`。实现细节见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

### 选项 A：从 PyPI 装（推荐）

```bash
pipx install scholar-cite
playwright install chromium
```

`pipx` 会把 scholar-cite 隔离在独立 virtualenv 里，把 `scholar-cite` 可执行文件加到 `PATH`。偏好 `pip` 的话把 `pipx` 换成 `pip` 自己管 venv 也行。

想追 `main` 分支的最新代码（而不是 PyPI 最新发布），用 `pipx install git+https://github.com/yitianlian/scholar-cite.git`。

### 选项 B：本地 build wheel 再装

适合需要把同一个 `.whl` 拷到其他机器的场景。

```bash
git clone https://github.com/yitianlian/scholar-cite.git
cd scholar-cite
pip install build
python -m build                     # 产出 dist/scholar_cite-0.1.0-*.whl

pipx install dist/scholar_cite-0.1.0-py3-none-any.whl
playwright install chromium
```

### 选项 C：开发态 editable 安装

```bash
git clone https://github.com/yitianlian/scholar-cite.git
cd scholar-cite
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"             # 带 pytest + ruff
playwright install chromium
pytest -q                           # 48 条测试，全都不碰真 Scholar
```

### 首次运行

第一次 `scholar-cite cite "..."` 会弹出一个 Chromium 窗口。Scholar 如果提示 "Please show you're not a robot"，在窗口里把验证码做完就行。工具最多等 5 分钟。Cookies 存到 `~/.cache/scholar-cite/cookies.json`，后续运行自动复用（经验上大概能撑一周左右）。随时可以用 `scholar-cite auth status` 看当前 cookie 状态，`scholar-cite auth reset` 清空强制重来。

## 快速上手

```bash
# 默认：浏览器路径，BibTeX 打到 stdout
scholar-cite cite "Attention Is All You Need"

# 全部 9 种格式
scholar-cite cite "Attention Is All You Need" --format all
```

## 用法

```bash
# 单篇 → BibTeX 到 stdout（默认格式）
scholar-cite cite "<paper title>"

# 指定要哪些格式（逗号分隔 或 'all'）
scholar-cite cite "..." --format all
scholar-cite cite "..." --format apa,mla,bibtex

# 限制或扩大候选数量（Scholar 通常一篇论文有多个 cluster）
scholar-cite cite "..." --limit 3

# 机器可读输出（partial 时带 citation_errors 字段）
scholar-cite cite "..." --format all --json

# 写文件
scholar-cite cite "..." --format bibtex -o refs.bib

# 跳过浏览器，只用 scholarly HTTP 后端 —— 没有静默回退
scholar-cite cite "..." --no-browser

# 严格：任何请求的格式缺失就 exit 4 且不写任何输出
scholar-cite cite "..." --format all --strict

# 管理浏览器 cookie 缓存
scholar-cite auth status
scholar-cite auth reset

# 查看版本
scholar-cite --version
```

### Exit codes

| Code | 含义 |
| ---- | ---- |
| 0 | 成功（可能有格式缺失 warning，但 stdout 仍产出）|
| 2 | 搜索没有结果 |
| 4 | `--strict` 打开且至少一个请求的格式缺失 |

### 输出示例（`--format all`）

```
[1] Attention is all you need
    A Vaswani — proceedings.neurips.cc
    cluster_id: 5Gohgn6QFikJ
    ──────────────────────────────────────────────────
    MLA:       Vaswani, Ashish, et al. "Attention is all you need." Advances ...
    APA:       Vaswani, A., Shazeer, N., Parmar, N., ... (2017). Attention is ...
    Chicago:   ...
    Harvard:   ...
    Vancouver: ...
    Bibtex:
        @article{vaswani2017attention,
          title={Attention is all you need},
          author={Vaswani, Ashish and Shazeer, Noam and ...},
          ...
        }
    Endnote:   ...
    Refman:    ...
    Refworks:
        # Google Scholar's RefWorks export is an external redirect.
        # Import URL:
        http://www.refworks.com/express?sid=google&...
```

## 工作原理

有两条 backend，可靠性差别很大：

1. **Playwright 浏览器（默认，推荐）**。真 Chromium（非 headless）跑 Scholar 搜索页、cite 弹窗、导出 URL。stealth 补丁让它不容易被识别；实在弹验证码就等用户一次性解决，cookies 之后沿用。
2. **scholarly HTTP（`--no-browser`，显式开启）**。[`scholarly`](https://scholarly.readthedocs.io/) 库的纯 HTTP session，能跑通时更快，但 Scholar 经常封。这条路径**不**会静默回退到浏览器，失败直接按格式维度暴露给调用方。

两条路径最终都走 `search.py` 里同一条管线，且**都会先按来源质量排序**再应用 `--limit`。详细架构见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

## 格式缺失时会怎样

Scholar 偶尔会给出不完整的格式（某些 cluster 根本没有某个导出链接、某些 URL 403 等）。`scholar-cite` 不会静默丢弃：

- **纯文本**输出里，每个失败的格式会原位显示 `[MISSING: <reason>]`。
- **JSON**输出会多一个 `citation_errors` 字段。
- **stderr** 打印一条 summary，列出哪些论文有哪些格式缺失。
- 加 `--strict` 就把这种部分失败升级为非零退出码（4），并拒绝写任何输出（保护自动化流水线）。

## 按来源质量排序候选

Google Scholar 经常把同一篇论文索引成多个 cluster（arXiv 预印本、官方会议版、第三方镜像），而**引用质量因 cluster 而异** —— 我们在真实使用中见过镜像给出的引用作者顺序反了、伪造了 volume 号、venue 字符串被糟蹋等情况。`scholar-cite` 按主机名把候选分层：

| 层级 | 代表主机 |
| ---- | ---- |
| 权威会议主页 | `openaccess.thecvf.com`、`cv-foundation.org`、`aclanthology.org`、`proceedings.neurips.cc`、`proceedings.mlr.press`、`ieeexplore.ieee.org`、`dl.acm.org`、`nature.com` |
| 预印本 | `arxiv.org`、`biorxiv.org` |
| 未知 | 其他（保留 Scholar 原顺序）|
| 已知低质量 | `sandbox.getindico.io`、`scholar.google.com`（自引用）|

真实案例：搜 "Deep Residual Learning for Image Recognition" 用 `--limit 1` 以前会落到某个 indico 镜像 cluster 上，得到 `@inproceedings{kaiming2016deep, ..., volume={34}}`。加了排序之后，同一查询稳定落到干净的 `he2016deep` cluster（官方 CVPR 主机）。对应回归测试见 `tests/test_ranking.py::test_rank_papers_handles_resnet_style_scenario`。

## Claude Code 与 Codex 集成

本仓库自带一个 agent skill，让 **Claude Code** 或 **OpenAI Codex CLI** 在你让它"帮我找引用"时自动调用 `scholar-cite`，不用每次解释工具。

### skill 放在哪里

两个 agent 分别从**各自**的目录自动发现 project-scoped skill。内容完全一致，所以仓库里保留一份真文件，另一份用符号链接：

```
scholar-cite/
├── .claude/
│   └── skills/
│       └── scholar-cite/
│           ├── SKILL.md     ← 真文件（Claude Code 读这里）
│           └── flags.md
└── .agents/
    └── skills/
        └── scholar-cite  →  ../../.claude/skills/scholar-cite   （符号链接）
                           （Codex CLI 读这里）
```

### 怎么 "安装" 这个 skill

什么都不用装。两家 agent 都会在 session 开始时扫描自己的 skill 目录。clone 本仓库、在你喜欢的 agent 里打开就行：

| Agent | skill 查找路径 | 操作 |
| ---- | ---- | ---- |
| Claude Code | 项目内 `.claude/skills/<name>/SKILL.md`；用户级 `~/.claude/skills/<name>/SKILL.md` | 在 Claude Code 里打开本仓库，skill 会自动出现在可用列表里，Claude 匹配到描述就通过 `Skill` 工具调起。 |
| Codex CLI | 项目内 `.agents/skills/<name>/SKILL.md`；用户级 `~/.agents/skills/<name>/SKILL.md` | 在仓库目录下 `codex` 打开，skill 会在 session 启动时被扫描到，运行时也会监听变化。 |

**想让 skill 全局可用**（跨项目，不止本仓库）：

```bash
# Claude Code
ln -s "$PWD/.claude/skills/scholar-cite" "$HOME/.claude/skills/scholar-cite"

# Codex CLI
mkdir -p "$HOME/.agents/skills"
ln -s "$PWD/.claude/skills/scholar-cite" "$HOME/.agents/skills/scholar-cite"
```

CLI 本身还是要在 `PATH` 上 —— 见上面的[安装](#安装)章节。

### skill 教了 agent 哪些东西

- 什么时候应该调用（中英文触发词）
- **不该**用的场景（arXiv 预印本 → `arxiv` skill；headless CI 下无法用；要 PDF 不适用）
- 常用命令和对应 flag
- 首次运行的验证码行为和 5 分钟等待时间
- 6 种常见故障的处理表
- exit code 合约，这样 agent 能正确判断成功/失败

要看 agent 实际读到什么，直接读
[`.claude/skills/scholar-cite/SKILL.md`](.claude/skills/scholar-cite/SKILL.md)
（完整 flag 参考 + Python API 在
[`flags.md`](.claude/skills/scholar-cite/flags.md)）。

## 已实现与计划中

| 功能 | 状态 |
| ---- | ---- |
| Scholar 搜索（浏览器 + scholarly 双路径） | ✅ |
| `cluster_id` 提取 | ✅ |
| Cite 弹窗 HTML 解析（5 种文本格式）| ✅ |
| 4 种导出格式通过 `BrowserContext.request` 拿到 | ✅ |
| Playwright cookie 持久化 / 验证码手动恢复 | ✅ |
| 候选 cluster 按来源质量排序 | ✅ |
| `auth status` / `auth reset` 子命令 | ✅ |
| `--format` / `--limit` / `-o` / `--json` / `--no-browser` / `--strict` / `--version` | ✅ |
| 批量模式（`-f titles.txt`）| ⏳ 计划中 |
| 交互式选择器（`-i`）| ⏳ 计划中 |
| 剪贴板（`-c`）| ⏳ 计划中 |
| 按 `cluster_id` 做 key 的 SQLite 缓存 | ⏳ 计划中 |
| SerpAPI 备用后端 | ⏳ 计划中 |

## 运行测试

```bash
pip install -e ".[dev]"
pytest -q
```

全部 48 条测试，parsing/fetching/CLI 分支都有覆盖。CI 不碰真 Google Scholar —— 使用保存的 HTML fixture 和 fake fetcher。

```bash
ruff check src/ tests/      # 静态检查
ruff format src/ tests/     # 格式化
```

## 项目结构

```
scholar-cite/
├── LICENSE                    MIT
├── CHANGELOG.md               版本变化
├── README.md                  英文 README
├── README.zh-CN.md            ← 你现在看的这份
├── pyproject.toml
├── docs/
│   ├── ARCHITECTURE.md        当前代码导览（想改代码先读这里）
│   ├── design.md              原始设计规格（planning-era）
│   ├── test-run-2026-04-19.md 首次 9 种格式活体验证
│   └── e2e-verification.md    修复后 E2E 证据 + wheel 安装烟雾测试
├── examples/
│   └── demo_five_papers.py    拿 5 篇经典论文 BibTeX 的示例脚本
├── src/scholar_cite/
│   ├── cli.py                 Typer CLI（`cite` / `auth status` / `auth reset`）
│   ├── search.py              browser + scholarly 编排
│   ├── citation.py            cite 弹窗解析 + 9 种格式组装
│   ├── browser_fetcher.py     Playwright session + cookie 持久化
│   ├── ranking.py             按主机名做来源质量排序
│   └── models.py              Paper / CitationSet 数据类
└── tests/
    ├── fixtures/
    │   └── cite_popup_sample.html
    ├── test_browser_fetcher.py
    ├── test_citation.py
    ├── test_cli.py
    ├── test_ranking.py
    └── test_search.py
```

## 文档索引

| 文档 | 里面写了什么 |
| ---- | ---- |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 模块地图、单查询生命周期、异常策略、缓存布局 |
| [`docs/design.md`](docs/design.md) | 原始 14 节设计规格（planning-era 快照） |
| [`docs/test-run-2026-04-19.md`](docs/test-run-2026-04-19.md) | 首次 9 种格式 pipeline 活体运行 |
| [`docs/e2e-verification.md`](docs/e2e-verification.md) | 修复后 E2E 证据 + wheel 安装烟雾测试 |
| [`.claude/skills/scholar-cite/SKILL.md`](.claude/skills/scholar-cite/SKILL.md) | agent skill —— Claude Code 从 `.claude/skills/` 自动发现，Codex CLI 从 `.agents/skills/` 自动发现（符号链接到同一文件）|
| [`.claude/skills/scholar-cite/flags.md`](.claude/skills/scholar-cite/flags.md) | 完整 flag 参考 + 供 skill 引用的 Python API 片段 |
| [`CHANGELOG.md`](CHANGELOG.md) | 发布级别的变更摘要 |
| [`PUBLISHING.md`](PUBLISHING.md) | 如何发一个新版本（改 version、`twine check`、TestPyPI dry-run、PyPI 正式 upload、打 GitHub release）|

## License

[MIT](LICENSE)。Google Scholar 的 HTML 结构以及你对上游数据的使用方式，受 Google 自己的服务条款约束。
