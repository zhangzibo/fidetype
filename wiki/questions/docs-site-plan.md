---
title: Documentation site plan
type: question
tags: [docs, website, github-pages, spec, sdk, p8, planning]
sources: []
updated: 2026-11-14
---

# Documentation site plan

**Question:** How do we organise the Fidetype documentation so that it reads like mature reference documentation (the Python docs, the ISO C standard and cppreference, the OpenTelemetry specification and docs site)? Which tool builds it on GitHub Pages?

**Status:** plan only (task P8-06). Nothing is built. GitHub Pages is not turned on. The build task is [P8-05](roadmap-standard.md#p8-docs-website-demo) (site + original UI) and P8-01 (generated spec, SDK docs, leaderboard, FEP index).

**Rule for this plan:** we copy the **structure** of the three references only. We do not copy their text, visual design, logos or branding. The same rule applies to the Brain2Qwerty project page that the user named as visual inspiration: no copy of Meta's layout, images or branding. The Fidetype design is original and needs the user's sign-off (D3 below).

## Summary
| Item | Proposal |
|---|---|
| Structure | 10 top-level sections: Get started, Concepts, Tutorials, How-to guides, Specification, SDKs (one section per language), Conformance, Benchmark, Proposals (FEPs), Project. Plus four indices: glossary, rule index, API index, changelog / "What's new". |
| Spec | One page per clause. A stable anchor for each rule id (`#TD-9`). A status badge on each page and section. One URL per spec version (`/spec/0.1/`, `/spec/1.0-rc1/`, `/spec/1.0-rc2/`). A generated rule-level diff between versions. |
| Tool | **Sphinx + MyST-Parser** (Markdown sources stay Markdown), with a small project-owned Sphinx extension for rule ids and badges, and an original theme. TypeDoc (TypeScript) and rustdoc (Rust) build their API pages, and the Sphinx build links them in. |
| User decisions | D1 turn on GitHub Pages; D2 domain name; D3 visual design sign-off; D4 spec licence on the site footer (follows the P9 licence decision). |

## 1. What each reference does well
Pages read on 2026-11-14 (structure only). The open-std.org server refused the connection, so the ISO C clause list comes from the published C drafts as we know them (N1570, N3220); check it before we cite it in public.

| Feature | Python docs | ISO C draft + cppreference | OpenTelemetry spec + docs site | Use in Fidetype |
|---|---|---|---|---|
| Top-level split | Split by reader task: What's new, Tutorial, Library reference, Language reference, HOWTOs, Setup, C API, FAQ, Deprecations ([home](https://docs.python.org/3/)) | ISO text: Scope, Normative references, Terms, Conformance, Environment, Language, Library, Annexes, Index. cppreference: Language, Headers, then one group per library area ([C index](https://en.cppreference.com/w/c)) | Docs site: What is it, Getting started, Concepts, Demo, Language APIs and SDKs, Collector, Specifications, Security, Contributing ([docs](https://opentelemetry.io/docs/)). Spec: Overview, Glossary, Principles, API, SDK, Data ([spec](https://opentelemetry.io/docs/specs/otel/)) | Split the **normative spec** from **user docs** (OTel). In user docs, split by reader task (Python) |
| Versioning | Version switcher on every page, from the development version to end-of-life versions | One N-numbered working draft per revision. Revision tags on entries, e.g. "(C99)", "(since C11)" ([history](https://en.cppreference.com/w/c/language/history)) | Spec version in the title (semver). Implementations state the spec version they implement ([repo](https://github.com/open-telemetry/opentelemetry-specification)) | One frozen URL per spec version. "Added in 1.0" / "Changed in 1.0" notes on rules (Python + cppreference) |
| Rule / clause ids | Stable anchors on every definition and heading, with a permalink mark ([json page](https://docs.python.org/3/library/json.html)) | Clause numbers (6.5.2.1) and paragraph numbers. cppreference cites the ISO clause on each page | Requirement key words (MUST, SHOULD) per BCP 14 | Clause numbers for sections; rule ids (`TD-9`) as anchors, with a permalink mark |
| Status labels | "Deprecations" page; deprecation notes on entries | Revision tags only | Status line under each page title; "Mixed" when sections differ ([document status](https://opentelemetry.io/docs/specs/otel/document-status/)); maturity levels; per-signal status table on each language page ([Python](https://opentelemetry.io/docs/languages/python/)) | A status badge per page and per section (Development, proposed Stable, Stable, Deprecated); "Mixed" on pages with more than one level |
| Per-page anatomy | Breadcrumb, title, source-code link, intro, examples, reference entries, "Added / Changed in version" notes, previous / next, "Show source" / "Report a bug" | cppreference: title + revision tag, synopsis, "defined in header", parameters, return value, notes, example, standard clause references, see also | Language page: status table, getting started, instrumentation, exporters, examples, API reference link, registry | Fixed templates: one for spec clauses, one for SDK API entries, one for concepts (section 2.3) |
| Glossary | Glossary page; terms link to it from everywhere | Clause 3 "Terms, definitions and symbols" | Top-level Glossary page | Glossary page generated from spec 1.4; term links from all pages |
| Indices | General index, module index, full contents, search | Index; symbol index | Search; registry | Rule index (every id → page), API index per language, search |
| What's new | One "What's new in X.Y" page per release, plus an index of all of them | Feature list per revision (cppreference history) | `CHANGELOG.md` in the spec repo | "What's new in NTS 1.0" page (from Appendix B + CHANGELOG), SDK changelogs |
| Conformance | Not applicable | Clause 4 "Conformance"; compiler support tables per revision | Spec compliance matrix per language | Conformance section with a matrix: SDK × profile × level (from spec 9.5, 11.7, Appendix C) |
| Proposals | PEP index (separate site) | Working-group papers (N-numbers) | OTEPs (in the spec repo) | FEP index with status per FEP |

> **Our take:** The three references agree on four things. (1) The normative text and the user guides are different documents. (2) Every rule and every definition has a stable link. (3) Status and version are visible on the page, not only in a changelog. (4) Indices (glossary, symbol or rule index, changelog) make a large document usable. Our spec already has rule ids, stability levels and a traceability table. The site must expose them; it does not need to invent them.

## 2. Information architecture

### 2.1 Top-level sections
| # | Section | Reader | Model | Content |
|---|---|---|---|---|
| 1 | **Get started** | New user | OTel "Getting started" | What Fidetype is, install, "emit a valid stream in 10 minutes", "add a trust layer" |
| 2 | **Concepts** | Anyone | OTel "Concepts" | Stream model, profiles, trust decisions, calibration and abstention, bindings, conformance levels, provenance (explanation, no rules) |
| 3 | **Tutorials** | Learner | Python "Tutorial" | Longer guided lessons: replay a public dataset; build a decoder adapter; build a browser consumer |
| 4 | **How-to guides** | Practitioner | Python "HOWTOs" | One task per page: LSL, WebSocket, NPZ to JSON Lines, fit a trust config, read a decision log, run the conformance suite in CI |
| 5 | **Specification** | Implementer | ISO C + OTel spec | NTS versions, one page per clause, glossary, rule index, registries, changelog, diffs |
| 6 | **SDKs** | Developer | OTel "Language APIs and SDKs" + Python "Library reference" | One sub-section per language: Python, TypeScript, Rust (later C, C#, Kotlin). Each: status table, install, quickstart, guide, API reference, changelog |
| 7 | **Conformance** | Implementer, auditor | OTel compliance matrix + C "Conformance" | Levels, profiles, how to run, vectors, compliance matrix, how to claim conformance |
| 8 | **Benchmark** | Researcher | (own) | Leaderboard, tasks, datasets and licences, how to submit |
| 9 | **Proposals (FEPs)** | Contributor | PEP / OTEP index | FEP index with status, template, process |
| 10 | **Project** | Everyone | Python "About" pages | Governance, contributing, code of conduct, security, licences, citation, roadmap, demo, diagrams |

The research wiki (`wiki/`) stays a research notebook. It is not part of the docs tree. The site links to it on GitHub ("Research notes"). User docs are new text, written from the wiki, not a copy of it.

### 2.2 Page tree and source map
Legend: **E** = exists (move or render as is), **A** = adapt (rewrite for users from the source), **N** = new (missing).

```
/                                   A  README.md (landing: what, why, 3 links)
/get-started/
  index                             A  README.md "What it does"
  install                           N
  first-stream                      A  examples/emit_ctc_stream.py, wiki/concepts/python-sdk.md
  add-trust-layer                   A  examples/streaming_trust.py
  whats-next                        N
/concepts/
  stream-model                      A  spec 1.0-rc1 s.2, wiki/concepts/nts-spec.md
  profiles (text, intent, control)  A  wiki/concepts/intent-events.md, control-events.md
  trust-decisions                   A  wiki/concepts/streaming-trust-layer.md
  calibration-and-abstention        A  wiki/concepts/conformal-risk-control.md
  bindings (files, LSL, WebSocket)  A  wiki/concepts/lsl-input.md, websocket-input.md
  conformance-levels                A  wiki/concepts/conformance-suite.md
  provenance-and-audit              A  wiki/concepts/provenance-ledger.md
  metrics (CER, WER, eWPM)          A  wiki/concepts/error-metrics.md
/tutorials/
  replay-public-dataset             A  examples/simulate_demo.py, src adapters b2t25 / toronto_semg
  write-a-decoder-adapter           N
  browser-consumer                  A  examples/ws-browser/
/how-to/
  stream-over-lsl                   A  examples/lsl_bridge.py
  stream-over-websocket             A  examples/ws-browser/
  brainflow-bridge                  A  src/fidetype/adapters/brainflow_bridge.py
  hypothesis-streams                A  examples/hypothesis_stream.py
  fit-a-trust-config                N
  read-a-decision-log               N
  conformance-in-ci                 N
/spec/
  index                             A  spec/README.md (versions table, status, how to comment)
  1.0-rc1/  (clauses 1-12, App. A-D) E  spec/nts-1.0-rc1.md, split per clause (section 3)
  0.1/                              E  spec/neuraltextstream-v0.1.md
  glossary                          N  generated from spec 1.0-rc1 s.1.4
  rules (rule index)                N  generated from the [XXX-n] ids
  registries                        E  spec 1.0-rc1 s.12 (also a page of its own)
  schemas                           E  spec/schemas/ (rendered + download)
  whats-new-1.0                     A  spec 1.0-rc1 App. B + spec/CHANGELOG.md
  changelog                         E  spec/CHANGELOG.md
  diff/0.1..1.0-rc1                 N  generated (section 3.5)
/sdk/
  index (status table, all langs)   N  from spec 1.0-rc1 s.9.5 + s.11.7
  python/  overview, quickstart     A  wiki/concepts/python-sdk.md
           api/ (autodoc)           N  src/fidetype (public API: fidetype.api, writer, streams, trust)
           cli                      N  src/fidetype/cli.py (argparse --help output)
  typescript/ overview, quickstart  E  sdk/typescript/README.md, wiki/concepts/typescript-sdk.md
           api/ (TypeDoc)           N
  rust/    overview, quickstart     E  sdk/rust/README.md, wiki/concepts/rust-sdk.md
           api/ (rustdoc)           N
  c/, csharp/, kotlin/              N  later (roadmap P2)
/conformance/
  index, levels-and-profiles        A  wiki/concepts/conformance-suite.md, spec/README.md
  vectors (browsable list)          A  spec/conformance/*/manifest + vector files
  compliance-matrix                 N  SDK x profile x level, from the cross-check output
  claiming-conformance              A  spec 1.0-rc1 s.9.4
/benchmark/
  index, leaderboard                E  benchmark/README.md, benchmark/site/ (leaderboard.json)
  datasets-and-licences             A  wiki/questions/public-datasets.md
  submit                            N
/feps/
  index (status table)              A  spec/README.md "Proposals"
  0001 ... 0005, template           E  spec/feps/*.md
/project/
  governance, contributing,         E  GOVERNANCE.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md,
  code-of-conduct, security            SECURITY.md
  licences, citation                E  LICENSE, LICENSES/, CITATION.cff
  roadmap                           A  wiki/questions/roadmap-standard.md (short public form)
  demo                              E  demo/index.html
  diagrams                          E  wiki/diagrams/index.html (built by tools/drawio/build.js)
  progress (optional)               E  wiki/progress/index.html
/genindex, /search, /404            N  generated
```

### 2.3 Page templates (per-page anatomy)
| Template | Parts, in order |
|---|---|
| Spec clause | Breadcrumb; clause number + title; status badge; "Applies to" (profiles, conformance classes); text with rule ids in the margin; "Tested by" (from Appendix C: checks and vectors per rule); "Added / Changed in" notes; previous / next clause; "Comment on this clause" (opens an issue with the clause and rule id filled in); "View source" |
| SDK API entry | Signature; one-line summary; parameters; returns; raises; spec rules it implements (links to rule anchors); example; "Added in SDK x.y"; source link |
| Concept / guide | Title; one-paragraph summary; diagram (from `wiki/diagrams/`) where useful; body; "Related rules" box; next steps |
| SDK language home | Status table (profile × stability, like the OTel per-signal table); install; quickstart; guides; API reference; changelog |

### 2.4 What is missing today
| Gap | Needed for | Size |
|---|---|---|
| Install page and a 10-minute quickstart per language (P8-02) | Get started | M |
| User-facing concept pages (the wiki pages are research notes, with experiment detail) | Concepts | M |
| How-to pages for tasks that have only an example script | How-to | M |
| Glossary page and term links | Spec, all pages | S (generated) |
| Rule index and per-rule anchors | Spec | S (generated) |
| Generated Python API reference (needs docstrings on the public API checked) | SDKs | M |
| TypeDoc / rustdoc output wired into the site | SDKs | S |
| CLI reference | SDKs | S |
| Compliance matrix page | Conformance | S |
| "What's new in 1.0" page | Spec | S |
| Benchmark submission guide | Benchmark | S |
| FAQ, deprecations page | Project, Spec | S |
| C SDK, collector (P3), adapter docs (P4) | Later phases | not now |

## 3. Specification presentation

### 3.1 One page per clause
- Split `spec/nts-1.0-rc1.md` at each `## N.` heading into one page per clause (1–12) and one per appendix (A–D). Subclauses (6.3, 7.4.5) stay sections in their page.
- **Source of truth stays one file.** The split happens at build time. Spec authors keep editing one Markdown file, and the repo view on GitHub stays as it is.
- A "single page" view of each version (the whole document on one page) is also built, for print and for full-text search in the browser. This is like the ISO single PDF.

### 3.2 Numbering and anchors
| Item | Form | Example | Rule |
|---|---|---|---|
| Clause | number from the heading | `/spec/1.0-rc1/trust-decisions/#6-3` | The number is in the heading text already. Anchors use the number, not the title, so a title edit does not break links |
| Rule | rule id | `/spec/1.0-rc1/trust-decisions/#TD-9` | Each `**[TD-9]**` becomes an anchor with a permalink mark. Ids are stable within 1.x (spec 1.3) |
| Short link | `/spec/rule/TD-9` | redirects to the newest version that has the rule | Lets issues and code comments link to a rule without a version |
| Term | glossary slug | `/spec/glossary/#blank-text` | From spec 1.4 |

- A build check fails if a rule id appears twice, or if an id in Appendix C has no anchor (and the reverse).
- The rule index page lists every id: id, clause, key word (MUST / SHOULD / MAY), status, "tested by" (vector ids), and gaps (G-n). The data come from the spec text and Appendix C.

### 3.3 Status badges
- Levels from spec 1.5: **Development**, **proposed Stable** (RC only), **Stable**, **Deprecated**, **Removed**.
- One badge under each page title. A page with more than one level shows **Mixed** and a badge on each section (the OTel model).
- The source of the levels is spec 2.3 ("Proposed stability in 1.0"). Proposed form: a small HTML comment or a MyST attribute on each heading, e.g. `{status=development}`. This needs a spec-side edit, so it is a P1 task, not a docs task. Until then, the build reads the table in 2.3.
- Colour is never the only signal: each badge has its text label (accessibility).

### 3.4 Versioned spec
| Version | URL | State |
|---|---|---|
| 0.1 | `/spec/0.1/` | current release (frozen) |
| 1.0 RC1 | `/spec/1.0-rc1/` | draft for comment (frozen when RC2 appears) |
| 1.0 RC2, … | `/spec/1.0-rc2/` | next drafts |
| latest | `/spec/latest/` | redirect to the newest **released** version (now 0.1) |
| draft | `/spec/draft/` | built from `main` |

- Spec versions are separate files in `spec/` (as today: `neuraltextstream-v0.1.md`, `nts-1.0-rc1.md`). So the site does **not** need a multi-version build tool for the spec. Each file is one version. Old files are never edited after release (an erratum is a note, the C "corrigendum" model).
- A version banner on each page: "Draft — not final" (RC), "Superseded by X" (old), "Current" (latest).
- A version switcher keeps the reader on the same clause, or on the same rule id, when the target version has it.
- The SDK API docs follow the SDK version, not the spec version. The SDK home page shows the spec versions each SDK supports (spec 11.7).

### 3.5 Diff between versions
- **Rule-level diff (main view):** a generated table per version pair: rule id, change (added / stricter / looser / clarified / deprecated / unchanged), old text, new text. 0.1 has no rule ids, so the 0.1 → 1.0 view uses Appendix B ("What changes") and the FEP numbers. From RC1 → RC2 on, the diff is computed by rule id.
- **Text diff (secondary view):** a side-by-side diff per clause, for RC → RC only.
- "What's new in NTS 1.0" is a written page, not a diff. It is for readers; the diff is for implementers.

## 4. Tooling for GitHub Pages
Facts below are from our knowledge as of 2026; check licences and project health again at build time (task T1).

| Tool | Licence | Maintenance cost for us | Versioning | API docs (Python / TS / Rust) | Rule-id anchors, glossary, indices | Offline build on Windows | Design freedom |
|---|---|---|---|---|---|---|---|
| **Sphinx + MyST-Parser** | BSD-2 (Sphinx), MIT (MyST) | Medium: Python config + one small extension. Same language as the reference implementation | Spec: one page set per file (no tool needed). Site versions: `sphinx-multiversion` (BSD) if needed | Python: `autodoc` + `napoleon`, native. TS: TypeDoc (Apache-2.0) output linked in. Rust: rustdoc (MIT / Apache-2.0) output linked in | Native: glossary + `term` role, general index, cross-reference roles, `versionadded` / `versionchanged` notes. Custom role for rule ids is about 100 lines | Yes: `uv run sphinx-build` (already use uv) | Full: own theme (Jinja templates + CSS) |
| MkDocs + Material | BSD-2 (MkDocs), MIT (Material) | Low to start. Risk: Material announced maintenance mode in favour of a successor (to verify); MkDocs core is slow-moving | `mike` (BSD-3) for site versions | Python: `mkdocstrings` (ISC). TS / Rust: link out | Glossary via abbreviations plugin; no general index; rule anchors via `attr_list` | Yes (Python) | Theme looks like Material unless we override much of it |
| Docusaurus | MIT | Medium: React + Node; frequent major upgrades | Built-in docs versioning (copies folders) | TS: TypeDoc plugin. Python / Rust: link out | Plugins / MDX components | Yes (Node) | Full, with React |
| Astro Starlight | MIT | Medium: Node; young project, fast-moving | Community plugin | TS: community TypeDoc plugin. Python / Rust: link out | MDX components | Yes (Node) | High; default look is recognisable |
| Hand-built static (Node, like `tools/drawio/build.js`) | ours (Apache-2.0) + markdown-it (MIT) | High over time: we write search, nav, indices, versions ourselves | Ours | All three: link out to generated output | Ours | Yes (Node, no extra deps) | Full |

### Recommendation: Sphinx + MyST-Parser, original theme
1. **Markdown stays Markdown.** MyST reads our existing `.md` files (spec, FEPs, READMEs). Authors and GitHub readers see no change.
2. **It has the reference-docs features we want, built in:** glossary with term links, general index, cross-reference roles, "Added / Changed in version" notes, permalinks on every heading. This is the toolchain behind the Python docs, so the structure we copy from them comes with it. We still write an original theme.
3. **Python is the reference implementation.** `autodoc` reads the docstrings of `fidetype` directly, so the Python API reference cannot drift from the code.
4. **Rule ids are one small extension.** A Sphinx role and a transform turn `[TD-9]` into an anchor, build the rule index, read Appendix C for "Tested by", and fail the build on duplicates. Sphinx is designed for this kind of extension.
5. **TS and Rust use their native tools.** TypeDoc and rustdoc are the standard API tools of those ecosystems. The build copies their HTML to `/sdk/typescript/api/` and `/sdk/rust/api/`; our theme wraps their landing pages. This is the OTel model (the site links each language's API reference).
6. **Offline on Windows.** `uv sync --group docs` then `uv run sphinx-build docs _site`. Node is needed only for TypeDoc; Cargo only for rustdoc. Each part can build alone; a missing toolchain skips that part with a warning.
7. **Licences are permissive** (BSD / MIT / Apache-2.0) and fit the Apache-2.0 repo.

Runner-up: **Astro Starlight** if the user wants a more app-like site and the rule-id and index features are acceptable as custom components. Not chosen: MkDocs Material (theme look and its maintenance status), Docusaurus (React upkeep, no Python autodoc), hand-built (we would rebuild indices, search and versions).

Deploy (later, needs D1): a GitHub Actions workflow builds the site on push to `main` and publishes with the official Pages actions. The existing static pages (`demo/`, `benchmark/site/`, `wiki/diagrams/index.html`, `wiki/progress/index.html`) are copied in as they are.

## 5. Phased task list
Sizes: **S** ≤ 0.5 agent-day, **M** 1–2 agent-days, **L** 3–5 agent-days. Suggested ids continue P8 (P8-07 …); the existing P8-01, P8-02, P8-05 stay as the umbrella tasks.

### Phase A: skeleton (no Pages, local build only)
| Task | Size | Done when |
|---|---|---|
| T1 Re-check tool licences and health; pin versions; `docs` dependency group in `pyproject.toml` | S | Versions pinned; `uv run sphinx-build` works on Windows |
| T2 `docs/` tree with the 10 sections and stub pages; landing page; navigation | M | Local build has every section; no broken links (`-W` = warnings are errors) |
| T3 Include existing files as they are (spec, FEPs, governance files, SDK READMEs, changelog) via MyST includes, no copies | S | Each existing file renders once; edits in the source show in the site |
| T4 Static pages copied in (demo, leaderboard, diagrams, progress) | S | Links work from the built site |

### Phase B: specification
| Task | Size | Done when |
|---|---|---|
| T5 Rule-id extension: anchors, permalink marks, rule index, duplicate / Appendix C cross-check | M | `#TD-9` works; index lists all ids; build fails on a duplicate |
| T6 Clause split of each spec version + single-page view + version banner + switcher (same clause / rule) | M | 0.1 and 1.0-rc1 browse per clause; switcher keeps position |
| T7 Status badges (read spec 2.3 now; per-heading attributes after a P1 edit) | S | Every spec page has a badge; Mixed pages show section badges |
| T8 Glossary from spec 1.4 + term links | S | Glossary page; terms link to it |
| T9 Rule-level diff generator + "What's new in 1.0" page | M | Diff page for 0.1 → 1.0-rc1 (Appendix B based); ready for RC1 → RC2 |

### Phase C: SDKs and conformance
| Task | Size | Done when |
|---|---|---|
| T10 Python API reference (autodoc) for the public API; fill missing docstrings (in `src/`, own task) | M | API pages for `fidetype.api`, writer, streams, trust; "Implements rule" links |
| T11 TypeDoc and rustdoc builds wired in; skip with a warning if Node / Cargo is missing | S | `/sdk/typescript/api/`, `/sdk/rust/api/` built locally |
| T12 SDK status table + compliance matrix (from the cross-check output) | S | One matrix page; numbers come from a run, not by hand |
| T13 CLI reference generated from argparse | S | `fidetype --help` tree on one page |

### Phase D: user docs (same as P8-02)
| Task | Size | Done when |
|---|---|---|
| T14 Install + 10-minute quickstarts (Python, TS, Rust) | M | A fresh subagent reaches a valid stream from the page alone (P8 exit criterion) |
| T15 Concept pages (8) rewritten for users from the wiki | L | Each page has a diagram link and "Related rules" |
| T16 How-to guides (7) and tutorials (3) | L | Each runs as written; examples are tested in CI |

### Phase E: design and publish
| Task | Size | Done when | User decision |
|---|---|---|---|
| T17 Original visual design: 2–3 mock-ups (type, colour, layout, logo-free wordmark), light / dark, phone width | M | User picks one | **D3** |
| T18 Theme implementation (Sphinx templates + CSS), accessibility check (contrast, keyboard, badges with text) | M | Headless Edge screenshots at desktop and phone width pass review | |
| T19 GitHub Actions deploy workflow + Pages settings | S | Site live at the chosen URL | **D1**, **D2** |
| T20 Link check, search check, 404 page, redirects (`/spec/rule/<id>`, `/spec/latest/`) | S | No broken links on the live site | |

### Decisions the user must make
| # | Decision | Options | Needed before |
|---|---|---|---|
| D1 | Turn on GitHub Pages for the repo (Settings → Pages → source "GitHub Actions") | yes / not yet | T19 |
| D2 | Domain | `zhangzibo.github.io/fidetype` (free, now) or a custom domain (cost, DNS; ties to the repo rename and the "Fidetype" trademark question in P7 / P9) | T19 (custom domain can come later) |
| D3 | Visual design sign-off | pick one of the T17 mock-ups | T18 |
| D4 | Spec text licence shown on the site | follows the P9 licence decision (Apache-2.0 today) | T19 |
| D5 | Is the progress dashboard public on the site? | include / leave out | T4 |

## Links
- Roadmap: [P8 Docs, website, demo](roadmap-standard.md#p8-docs-website-demo)
- Spec docs this plan presents: [NTS specification](../concepts/nts-spec.md), [conformance suite](../concepts/conformance-suite.md)
- SDK pages: [Python](../concepts/python-sdk.md), [TypeScript](../concepts/typescript-sdk.md), [Rust](../concepts/rust-sdk.md)
- Growth context: [open-source playbook](open-source-playbook.md)
