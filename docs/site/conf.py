"""Sphinx configuration for the Tethys public docs site.

Renders the full ``docs/`` tree (ADRs, runbooks, research notes, explainers,
architecture, traceability, USER_GUIDE) at https://goldr0g3r.github.io/tethys/.

Build (from the repo root)::

    sphinx-build -W --keep-going -c docs/site -b html docs docs/_build/html

``-c docs/site`` points Sphinx at this file. ``docs`` (the second-to-last
arg) is the source root - the full ``docs/`` tree is the source, so
``docs/site/index.md`` can reference every other ``docs/**.md`` file via
absolute toctree paths (``/adr/README``, ``/runbooks/README``, ...).

References:

- Sphinx docs: https://www.sphinx-doc.org/en/master/usage/configuration.html
- MyST-Parser: https://myst-parser.readthedocs.io/en/latest/configuration.html
- sphinx-design: https://sphinx-design.readthedocs.io/
- sphinxcontrib-mermaid: https://sphinxcontrib-mermaid-demo.readthedocs.io/
- Furo theme: https://pradyunsg.me/furo/customisation/
- Parent plan section 11 (public deliverables) - this site is the headline.
- ADR-0008 (license-free toolchain) - every dep BSD/MIT.
"""

from __future__ import annotations

import datetime as _dt

project = "Tethys"
author = "Tethys contributors"
copyright = f"{_dt.datetime.now(_dt.timezone.utc):%Y}, {author}"  # noqa: A001
release = "0.1.0-dev"
version = "0.1.0"

# ---- Master document ----
# Source dir is `docs/`; this index lives at `docs/site/index.md` so the
# master doc path is `site/index` (no extension; relative to srcdir).
master_doc = "site/index"
root_doc = master_doc

# ---- Extensions ----
extensions = [
    "myst_parser",
    "sphinx_design",
    "sphinxcontrib.mermaid",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.intersphinx",
]

# ---- Source file handling ----
source_suffix = {
    ".md": "markdown",
    ".rst": "restructuredtext",
}

# ---- File patterns ----
# Things under `docs/` we deliberately don't want in the site.
exclude_patterns = [
    "_build",
    "site/_build",
    "site/.gitignore",
    "site/requirements.txt",
    # Raw data sources for tooling - rendered elsewhere or non-narrative.
    "traceability.csv",
    "research/phase-0-standards-matrix.csv",
    "misra-c-2023-rules.txt",
    # Architecture mermaid source is rendered inline via `{mermaid}`
    # directives where useful; the .mmd file itself is not a doc page.
    "architecture/dep-graph.mmd",
    # Slave Doxygen output area (Doxygen + Breathe integration is a
    # documented follow-up - left as scaffolding here).
    "../slave/docs/**",
]

# ---- MyST-Parser configuration ----
# Enables every MyST extension that the existing docs/ markdown uses.
# `linkify` auto-links bare URLs; `colon_fence` allows ``:::{note}`` blocks;
# `deflist` enables definition lists; `attrs_inline` permits ``{name}`` attrs.
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "linkify",
    "attrs_inline",
    "tasklist",
    "substitution",
    "fieldlist",
    "html_image",
]
# `myst_heading_anchors` was tripping a Sphinx 8.2 `KeyError: 'anchorname'`
# regression inside `sphinx.environment.adapters.toctree.document_toc` when
# rendered headings carry a manual HTML anchor (e.g. coding-standard.md's
# "1. Scope and applicability" with the `(#1-scope-...)` markdown links).
# We rely on auto-generated section IDs + `autosectionlabel` instead; the
# Furo theme renders the in-page TOC from the same section ids without
# needing MyST's extra anchor-injection pass.
myst_url_schemes = ("http", "https", "mailto", "ftp")
myst_linkify_fuzzy_links = False

# ---- autosectionlabel ----
# Prefix labels with the document path to avoid clashes between identical
# headings across the 90+ markdown files in docs/.
autosectionlabel_prefix_document = True
autosectionlabel_maxdepth = 3

# ---- Mermaid output ----
# Default to inline SVG via the JS runtime (Furo bundles it via the
# sphinxcontrib-mermaid <script> tag). No external service.
mermaid_output_format = "raw"
mermaid_version = "10.9.1"  # https://github.com/mermaid-js/mermaid/releases/tag/v10.9.1

# ---- Intersphinx mapping ----
# Empty by default: we don't cross-reference any external Sphinx project
# from our docs yet. The extension is loaded so any future ``:py:`` or
# similar cross-refs are easy to add — just append entries here.
intersphinx_mapping: dict[str, tuple[str, str | None]] = {}

# ---- HTML output ----
html_theme = "furo"
html_title = "Tethys - XCP for extreme environments"
html_short_title = "Tethys"
html_baseurl = "https://goldr0g3r.github.io/tethys/"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_show_sourcelink = False
html_show_sphinx = True
html_copy_source = False

# The Furo theme exposes a small set of options for tone-of-voice + repo
# links. Keep it neutral and let the content carry the message.
html_theme_options = {
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
    "source_repository": "https://github.com/goldr0g3r/tethys/",
    "source_branch": "main",
    "source_directory": "docs/",
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/goldr0g3r/tethys",
            "html": "",
            "class": "fa-brands fa-github",
        },
    ],
    "light_css_variables": {
        "color-brand-primary": "#0a4d8c",
        "color-brand-content": "#0a4d8c",
    },
    "dark_css_variables": {
        "color-brand-primary": "#5ab3ff",
        "color-brand-content": "#5ab3ff",
    },
}

# `html_extra_path` contents are copied verbatim into the build output root.
# `_extra/index.html` is a meta-refresh redirect to `/site/index.html`
# (Sphinx's `master_doc` lives at `site/index` because conf.py is under
# `docs/site/`). Without this redirect, `https://goldr0g3r.github.io/tethys/`
# would 404 instead of landing on the doc home.
html_extra_path: list[str] = ["_extra"]

# ---- Warnings ----
# `-W` on the command-line turns these into errors. We leave nitpicky off
# for now because the existing markdown has many cross-domain links the
# nitpick pass would flag; we revisit once the doc site is live.
nitpicky = False

# Suppress autosectionlabel duplicate warnings - many README files share
# the same generic section names ("Cross-references", "Acceptance", ...).
# autosectionlabel_prefix_document already disambiguates them in actual
# links; the warning fires regardless on every doc-level dup.
suppress_warnings = ["autosectionlabel.*", "myst.xref_missing", "misc.highlighting_failure"]


# ---- Sphinx 8.2 `document_toc` workaround ----
#
# `sphinx.environment.adapters.toctree.document_toc()` walks
# ``toc.findall(nodes.reference)`` and reads ``anchorname`` from every
# matched node. Because ``addnodes.download_reference`` *subclasses*
# ``nodes.reference``, any markdown-style relative link to a file outside
# ``docs/`` (e.g. ``[\`.clang-format\`](../.clang-format)`` in a heading
# of ``docs/coding-standard.md``) becomes a ``download_reference`` node
# embedded in the doc-level TOC. ``download_reference`` carries no
# ``anchorname`` attribute, so ``document_toc`` raises ``KeyError`` mid
# build (Sphinx 8.2.3 + 9.x both affected).
#
# Strip ``download_reference`` nodes out of every doc's TOC after Sphinx
# finishes the read phase. The download targets are preserved in the
# body of the doc; only the duplicate references that would have ended
# up in the sidebar TOC are removed.
def _strip_download_refs_from_tocs(app, env):  # type: ignore[no-untyped-def]
    """Remove ``download_reference`` nodes from each doc's TOC tree.

    Called via the ``env-check-consistency`` event, fired after every
    source file has been read but before writing starts. Mutates
    ``env.tocs`` in place; no side-effect on the doctrees themselves.
    """
    from sphinx import addnodes

    for _docname, toc in list(env.tocs.items()):
        for ref in list(toc.findall(addnodes.download_reference)):
            parent = ref.parent
            if parent is not None:
                index = parent.index(ref)
                # Replace the download_reference with its plain-text
                # children so the heading still reads correctly in the
                # sidebar TOC ("2.1 C / C++ - root .clang-format").
                parent.remove(ref)
                for child in reversed(ref.children):
                    parent.insert(index, child)


def setup(app):  # type: ignore[no-untyped-def]
    app.connect("env-check-consistency", _strip_download_refs_from_tocs)
    return {"version": "0.1", "parallel_read_safe": True, "parallel_write_safe": True}
