# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Static HTML and CSS served from `docs/` on GitHub Pages. One file per page,
no framework, no build step.

## Users

Robot Framework engineers (QA and test automation) who write suites with a
coding agent such as Claude Code, deciding whether to give that agent this
plugin.

## Product Purpose

robotframework-lint-lsp makes coding agents leave fewer lint issues in
Robot Framework files: a language server pushes short robocop findings
after each edit, and a hook applies robocop's safe fixes without spending
agent turns. Success: fewer issues left, at about the cost of no lint.

## Positioning

Built and tuned for agents, not editors: output sized for an agent's
context, and fixes applied by a hook because measured agents read fix
commands but did not run them.

## Operating Context

Installed with pip plus a Claude Code plugin; also usable from opencode,
Crush, Codex and any LSP client. Evaluated with an A/B harness that runs the
paid claude CLI on one fixed task.

## Evidence on Hand

- A/B results measured 2026-11-14: `docs/benchmarks/results`,
  `docs/benchmarks/benchmarks.archify.md`, harness `docs/benchmarks/`.
- One task only; Haiku 25 runs per arm, per-model check 3 runs per arm.
  Do not claim results beyond that task.
- No testimonials, users or adoption numbers exist; do not invent them.

## Product Principles

- Every claim cites a measured run.
- Agent output stays small.
- Fix it for the agent when a fix is safe.
