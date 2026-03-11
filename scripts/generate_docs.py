#!/usr/bin/env python3
"""
generate_docs.py — Sync documentation from Playbook & Kernel into site_docs/.

This script:
1. Copies mapped files from ai_ml_playbook/ and sgr_kernel/ into site_docs/{ru,en}/
2. Rewrites internal Markdown links to prevent 404s
3. Generates CHANGELOG.md from git tags (with real tag dates)
4. Copies static assets (CSS) into site_docs/
5. Generates bilingual index pages
"""

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

from lang_splitter import split_by_language

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).parent.parent

# Expect PLAYBOOK_DIR as child or sibling
PLAYBOOK_DIR = ROOT_DIR / "ai_ml_playbook"
if not PLAYBOOK_DIR.exists():
    PLAYBOOK_DIR = ROOT_DIR.parent / "ai_ml_playbook"

DOCS_DIR = ROOT_DIR / "site_docs"
SITE_DIR = ROOT_DIR / "site"

LANGUAGES = ["ru", "en"]

GITHUB_ORG = "scarseze"
KERNEL_REPO = "sgr-kernel"
PLAYBOOK_REPO = "ai_ml_playbook"

# ---------------------------------------------------------------------------
# Mapping: source path (relative to Playbook OR Kernel) -> dest in site_docs/{lang}/
# ---------------------------------------------------------------------------
MAPPINGS = {
    "ONBOARDING.md":                          "getting-started/installation.md",
    "README.md":                              "getting-started/quickstart.md",
    "docs/architecture.md":                   "docs/architecture.md",
    "docs/why_sgr.md":                        "docs/why_sgr.md",
    "docs/l8_distinguished_invariants.md":    "docs/l8_distinguished_invariants.md",
    "docs/L8_ARCHITECTURE_ANNEX.md":          "docs/L8_ARCHITECTURE_ANNEX.md",
    "docs/swarm_protocol.md":                 "docs/swarm-protocol.md",
    "AGENTS.md":                              "docs/agents.md",
    "Glossary.md":                            "docs/glossary.md",
    "docs/workflows/rag_development_flow.md": "docs/memory.md",
    "docs/telemetry.md":                      "docs/telemetry.md",
    "docs/compliance/152fz.md":               "compliance/152fz.md",
    "docs/compliance/gdpr.md":                "compliance/gdpr.md",
    "docs/compliance/hipaa.md":               "compliance/hipaa.md",
    "docs/enterprise/features.md":            "enterprise/features.md",
    "docs/enterprise/migration.md":           "enterprise/migration.md",
    "docs/sa_portfolio/SA_PORTFOLIO.md":      "docs/sa_portfolio/SA_PORTFOLIO.md",
    "docs/sa_portfolio/api_contracts.md":     "docs/sa_portfolio/api_contracts.md",
    "docs/sa_portfolio/data_models.md":       "docs/sa_portfolio/data_models.md",
    "docs/sa_portfolio/event_catalog.md":     "docs/sa_portfolio/event_catalog.md",
    "docs/sa_portfolio/security_overview.md": "docs/sa_portfolio/security_overview.md",
    "CONTRIBUTING.md":                        "community/contributing.md",
    "CODE_OF_CONDUCT.md":                     "community/code-of-conduct.md",
    "CHANGELOG.md":                           "changelog.md",
}

# Extended mapping for link resolution (includes generated files)
ALL_MAPPINGS = MAPPINGS


def log(message: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")


def run_git(*args: str) -> str:
    """Run a git command in the kernel repo root and return stdout."""
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=ROOT_DIR
    )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Link rewriting
# ---------------------------------------------------------------------------
def fix_markdown_links(
    content: str, dst_rel: str, src_rel: str, origin_repo: str
) -> str:
    """Rewrite relative Markdown links so they resolve inside site_docs/."""
    dst_dir = Path(dst_rel).parent
    src_dir = Path(src_rel).parent

    def _replacer(match):
        text, url = match.group(1), match.group(2)

        # Skip absolute, anchor-only, and mailto links
        if url.startswith(("http://", "https://", "mailto:", "#", "www.")):
            return match.group(0)

        base, _, fragment = url.partition("#")
        anchor = f"#{fragment}" if fragment else ""

        # Resolve relative to source file's original location
        resolved = os.path.normpath(str(src_dir / base)).replace("\\", "/")
        if resolved.startswith("./"):
            resolved = resolved[2:]

        if resolved in ALL_MAPPINGS:
            target = ALL_MAPPINGS[resolved]
            rel = os.path.relpath(target, dst_dir).replace("\\", "/")
            return f"[{text}]({rel}{anchor})"

        # Fallback: link to GitHub
        repo = PLAYBOOK_REPO if origin_repo == PLAYBOOK_REPO else KERNEL_REPO
        gh = f"https://github.com/{GITHUB_ORG}/{repo}/blob/main/{resolved}{anchor}"
        return f"[{text}]({gh})"

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _replacer, content)


# ---------------------------------------------------------------------------
# Changelog
# ---------------------------------------------------------------------------
def get_tag_date(tag: str) -> str:
    """Return the date of a git tag in YYYY-MM-DD format."""
    date = run_git("log", "-1", "--format=%ad", "--date=short", tag)
    return date if date else datetime.now().strftime("%Y-%m-%d")


def generate_changelog() -> str:
    log("Generating CHANGELOG.md from git tags...")
    raw = run_git("tag", "--sort=-v:refname")
    tags = [t for t in raw.split("\n") if t.strip()]

    changelog = "# Changelog\n\nAll notable changes to SGR Kernel.\n\n"

    if not tags:
        changelog += "*No releases yet.*\n"
        return changelog

    for i, tag in enumerate(tags[:10]):
        tag_date = get_tag_date(tag)

        if i + 1 < len(tags):
            prev = tags[i + 1]
            commits = run_git(
                "log", f"{prev}..{tag}", "--pretty=format:%h - %s (%ad)", "--date=short"
            )
        else:
            # First tag ever — show commits up to that tag only
            commits = run_git(
                "log", tag, "--pretty=format:%h - %s (%ad)", "--date=short", "-20"
            )

        url = f"https://github.com/{GITHUB_ORG}/{KERNEL_REPO}/releases/tag/{tag}"
        changelog += f"## [{tag}]({url}) - {tag_date}\n\n"

        lines = [ln for ln in commits.split("\n") if ln.strip()][:20]
        if lines:
            for line in lines:
                changelog += f"- {line}\n"
        else:
            changelog += "- *No commits in this range.*\n"
        changelog += "\n"

    return changelog


# ---------------------------------------------------------------------------
# File sync
# ---------------------------------------------------------------------------
def copy_docs():
    """Sync mapped documentation files into site_docs/{ru,en}/."""
    log("Syncing Playbook + Kernel -> site_docs/...")

    for src_rel, dst_rel in MAPPINGS.items():
        # Resolve source: try Playbook first, then Kernel root
        if src_rel == "CHANGELOG.md":
            src_path = ROOT_DIR / src_rel
            origin = KERNEL_REPO
        else:
            src_path = PLAYBOOK_DIR / src_rel
            origin = PLAYBOOK_REPO
            if not src_path.exists():
                src_path = ROOT_DIR / src_rel
                origin = KERNEL_REPO

        if src_path.exists():
            for lang in LANGUAGES:
                dst_path = DOCS_DIR / lang / dst_rel
                dst_path.parent.mkdir(parents=True, exist_ok=True)

                if src_path.suffix == ".md":
                    lang_path = src_path.with_name(f"{src_path.stem}.{lang}.md")
                    if lang_path.exists():
                        section = lang_path.read_text(encoding="utf-8")
                    else:
                        raw = src_path.read_text(encoding="utf-8")
                        ru_content, en_content = split_by_language(raw)
                        section = ru_content if lang == "ru" else en_content
                    
                    fixed = fix_markdown_links(section, dst_rel, src_rel, origin)
                    dst_path.write_text(fixed, encoding="utf-8")
                    log(f"  [OK] {src_rel} -> {lang}/{dst_rel}")
                else:
                    # Wrap non-markdown (YAML etc.) in a code fence
                    body = src_path.read_text(encoding="utf-8")
                    wrapped = f"# {Path(src_rel).name}\n\n```yaml\n{body}\n```\n"
                    dst_path.write_text(wrapped, encoding="utf-8")
                    log(f"  [OK] Wrapped {src_rel} -> {lang}/{dst_rel}")
        else:
            log(f"  [STUB] {src_rel} (not found)")
            for lang in LANGUAGES:
                dst_path = DOCS_DIR / lang / dst_rel
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                title = Path(dst_rel).stem.replace("-", " ").title()
                dst_path.write_text(
                    f"# {title}\n\n*Documentation coming soon.*\n", encoding="utf-8"
                )


def copy_static_assets():
    """Copy stylesheets into site_docs/ so MkDocs can find them."""
    src_css = ROOT_DIR / "docs" / "stylesheets" / "extra.css"
    if src_css.exists():
        dst_css = DOCS_DIR / "stylesheets" / "extra.css"
        dst_css.parent.mkdir(parents=True, exist_ok=True)
        dst_css.write_text(src_css.read_text(encoding="utf-8"), encoding="utf-8")
        log("  [OK] Copied extra.css -> site_docs/stylesheets/extra.css")
    else:
        log("  [WARN] docs/stylesheets/extra.css not found, skipping")


# ---------------------------------------------------------------------------
# Index pages
# ---------------------------------------------------------------------------
def generate_index_pages():
    log("Generating index pages...")

    pages = {
        "ru": """\
---
title: SGR Kernel - Enterprise Multi-Agent Swarm
description: "Correctness is a Basic Right"
---

# SGR Kernel v3.0

**Enterprise-платформа для оркестрации мульти-агентных систем** с гарантией безопасности, комплаенса и воспроизводимости.

![Tests](https://img.shields.io/badge/tests-151%20PASSED-brightgreen)
![Compliance](https://img.shields.io/badge/compliance-GDPR%7CHIPAA%7C152--FZ-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)

| Характеристика | Значение |
|----------------|----------|
| Комплаенс | 152-ФЗ, GDPR, HIPAA |
| Память | PostgreSQL + WAL |
| Мониторинг | Prometheus + Grafana |

## 💡 Why SGR?

Потому что «работает на моей машине» — это не гарантия.
Современные системы оркестрации решают задачи **планирования** и **транспорта**. SGR Kernel — это **слой корректности** (Correctness Layer), который добавляет формальные гарантии:

| Гарантия | Что это значит |
|----------|---------------|
| ✅ Execution Exclusivity | Задачу выполняет только один воркер |
| ✅ Bounded Duplication | Дублирование ≤ 1 попытки на цикл аренды |
| ✅ Atomic Visibility | Результаты видны только после полного коммита |
| ✅ Eventual Progress | Задача завершится, даже если воркер упал |

Это не «ещё один оркестратор». Это **формальная граница доверия** между намерением и выполнением.

```mermaid
graph LR
    A[Задача] --> B{SGR Kernel}
    B -->|I1: Exclusivity| C[Один воркер]
    B -->|I3: Bounded Dup| D[≤ 1 дубль]
    B -->|I4: Atomic Vis| E[Коммит-маркер]
    B -->|I5: Progress| F[Гарантия завершения]
    C & D & E & F --> G[Корректный результат]
    
    style B fill:#2563eb,stroke:#1e40af,color:white
    style G fill:#16a34a,stroke:#15803d,color:white
```

## Быстрый старт

```bash
git clone https://github.com/scarseze/sgr-kernel.git
cd SGR Kernel
docker-compose up -d
```

> **Философия:** Безопасность, аудируемость и корректность AI-систем должны быть доступны каждому — не как Enterprise-фича за $199/мес, а как базовое право.

[Начать работу](getting-started/installation.md) | [Узнать больше: Почему SGR?](docs/why_sgr.md) | [Комплаенс](compliance/152fz.md)
""",
        "en": """\
---
title: SGR Kernel - Enterprise Multi-Agent Swarm
description: "Correctness is a Basic Right"
---

# SGR Kernel v3.0

**Enterprise platform for multi-agent swarm orchestration** with guaranteed security, compliance, and reproducibility.

![Tests](https://img.shields.io/badge/tests-151%20PASSED-brightgreen)
![Compliance](https://img.shields.io/badge/compliance-GDPR%7CHIPAA%7C152--FZ-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)

| Feature | Value |
|---------|-------|
| Compliance | 152-FZ, GDPR, HIPAA |
| Memory | PostgreSQL + WAL |
| Monitoring | Prometheus + Grafana |

## 💡 Why SGR?

Because "it works on my machine" is not a guarantee.
Modern orchestration systems solve **planning** and **transport** problems. SGR Kernel is a **Correctness Layer** that adds formal execution guarantees:

| Guarantee | Meaning |
|-----------|---------|
| ✅ Execution Exclusivity | Task is executed by exactly one worker |
| ✅ Bounded Duplication | Duplications ≤ 1 attempt per lease cycle |
| ✅ Atomic Visibility | Results are visible only after a full commit |
| ✅ Eventual Progress | The task will finish, even if the worker crashes |

It's not "just another orchestrator". It's the **formal trust boundary** between intent and execution.

```mermaid
graph LR
    A[Task] --> B{SGR Kernel}
    B -->|I1: Exclusivity| C[One Worker]
    B -->|I3: Bounded Dup| D[≤ 1 duplicate]
    B -->|I4: Atomic Vis| E[Commit Marker]
    B -->|I5: Progress| F[Completion Guarantee]
    C & D & E & F --> G[Correct Result]
    
    style B fill:#2563eb,stroke:#1e40af,color:white
    style G fill:#16a34a,stroke:#15803d,color:white
```

## Quick Start

```bash
git clone https://github.com/scarseze/sgr-kernel.git
cd SGR Kernel
docker-compose up -d
```

> **Philosophy:** Security, auditability, and correctness of AI systems should be available to everyone — not as an Enterprise feature for $199/mo, but as a basic right.

[Get Started](getting-started/installation.md) | [Read more: Why SGR?](docs/why_sgr.md) | [Compliance](compliance/152fz.md)
""",
    }

    for lang, content in pages.items():
        out = DOCS_DIR / lang / "index.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        log(f"  [OK] Generated {lang}/index.md")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    log("=" * 50)
    log("SGR Kernel - Documentation Generator")
    log("=" * 50)

    copy_docs()
    copy_static_assets()
    generate_index_pages()

    version = os.getenv("GITHUB_REF_NAME", "dev")
    (ROOT_DIR / "VERSION").write_text(version)
    log(f"  [OK] Version: {version}")

    log("=" * 50)
    log("DONE")
    log("=" * 50)


if __name__ == "__main__":
    main()
