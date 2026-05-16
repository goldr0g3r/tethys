# `master/docs/` - Sphinx-pulled module docs

> Local module documentation for the `tethys-master` Python package.
> The public Sphinx site at [`docs/site/`](../../docs/site/) pulls these
> Markdown files into its toctree during Phase 11 (parent plan section 11);
> until then they ship as standalone Markdown that renders on the GitHub
> source view.
>
> Parent plan section 14 (`master/docs/`: local docstrings; Sphinx pulls
> from here).
> Companion files: [`master/README.md`](../README.md) (quickstart) and
> [`docs/USER_GUIDE.md`](../../docs/USER_GUIDE.md) (whole-project recipe).

## Files

| File | Audience | Length budget |
| --- | --- | --- |
| [`index.md`](index.md) | Anyone landing on the master package's docs page. | <= 1 page |
| [`installation.md`](installation.md) | Engineer installing `tethys-master` for the first time. | <= 1 page |
| [`cli.md`](cli.md) | CLI user; mirrors `tethys-master --help`. | <= 2 pages |
| [`api.md`](api.md) | Library user importing `tethys_master.protocol.XcpClient` etc. | <= 3 pages |
| [`gui.md`](gui.md) | GUI user; PySide6 walk-through. | <= 2 pages |
| [`transports.md`](transports.md) | Picking a transport (UDP / SocketCAN / UART). | <= 2 pages |
| [`profiles.md`](profiles.md) | Marine vs space profile semantics on the master side. | <= 2 pages |

Each file follows the Tethys doc style established by
[`docs/learn/xcp-101.md`](../../docs/learn/xcp-101.md) and
[`docs/runbooks/release-process.md`](../../docs/runbooks/release-process.md):

- Top-of-file metadata block: audience, scope, length budget.
- Numbered top-level sections with anchors.
- Code samples in both PowerShell and bash where they differ.
- Every external claim cites a source.
- Standards citations follow [`.cursor/rules/always-cite-standards.mdc`](../../.cursor/rules/always-cite-standards.mdc).

## How the Sphinx site picks these up (Phase 11)

The Phase 11 PR will extend [`docs/site/conf.py`](../../docs/site/conf.py)
with a `myst_parser` include directive:

```python
# docs/site/conf.py (Phase 11 add)
suppress_warnings = ["myst.xref_missing"]
myst_enable_extensions = ["colon_fence", "deflist", "linkify"]

# Pull master/docs into the site under /master-tool/.
master_docs_glob = [
    "../../master/docs/index.md",
    "../../master/docs/installation.md",
    "../../master/docs/cli.md",
    "../../master/docs/api.md",
    "../../master/docs/gui.md",
    "../../master/docs/transports.md",
    "../../master/docs/profiles.md",
]
```

Until then the [`docs/site/index.md`](../../docs/site/index.md) toctree
includes only the canonical site files; the seven `master/docs/*.md`
files live and render alone in the source tree.

## Cross-references

- Parent plan section 3.1 (PC master tool scope).
- Parent plan section 14 (`master/docs/` slot).
- [`master/README.md`](../README.md) - quickstart.
- [`docs/USER_GUIDE.md`](../../docs/USER_GUIDE.md) - whole-project recipe.
- [`docs/learn/xcp-101.md`](../../docs/learn/xcp-101.md) - protocol primer.
- [`docs/site/index.md`](../../docs/site/index.md) - public Sphinx site.
