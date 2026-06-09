# ADR-001: Pin pac CLI to 1.52.1 on .NET 9 (macOS)

> ADR template: Context → Decision → Consequences → Status.

- **Status**: Accepted
- **Date**: 2026-05-27

## Context

macOS Tahoe 26.x, Apple Silicon. After installing the latest `pac` CLI
(2.7.4, targeting `net10.0`) via `dotnet tool install --global`, every
auth-touching command crashed with
`System.NullReferenceException` in
`Microsoft.Identity.Client.Platforms.Features.RuntimeBroker.RuntimeBroker..ctor`,
called from `AddAutomaticOSProfileIfAllowedAsync`.

This is .NET 10 + MSAL + macOS interaction: MSAL eagerly constructs a Windows
RuntimeBroker handle even on non-Windows OSes, and the .NET 10 host triggers
the failure path. Reproduces on a clean install.

## Considered options

| Option | Pros | Cons |
|---|---|---|
| A. Use latest pac (2.7.4) on .NET 10 | future-proof | blocked — crashes |
| B. Pin pac to last 1.x build (1.52.1, net9.0) + install .NET 9 runtime | works today | manual symlink workaround for keg-only Homebrew formula |
| C. Switch to VS Code extension `pac` | bundled runtime | not scriptable in CLI/CI workflows the same way |
| D. Wait for pac 2.x macOS fix | zero work | unknown timeline, blocks Day 0 |

## Decision

Choose **Option B**: pin `Microsoft.PowerApps.CLI.Tool` to **1.52.1**, install
`dotnet@9` (Homebrew formula) alongside the existing .NET 10 SDK, and symlink
the .NET 9 runtime into `/usr/local/share/dotnet/shared/...` so the default
`dotnet` host can find it without `DOTNET_ROOT` gymnastics.

Login uses `--deviceCode` to bypass the macOS auth broker entirely.

Exact commands are reproducible from `docs/local-setup.md` → "Problems
encountered" section 2.

## Consequences

- We can run all required pac verbs (`auth`, `solution`, `code`, `pcf`,
  `pipeline`, `env`, `org`, `tool`) end-to-end on macOS.
- We're one version behind the latest pac. Acceptable: 1.52.1 supports every
  command we need (`pac code init`, `pac solution init/pack/unpack/import/
  export`, `pac pipeline ...`).
- Two `.NET` runtimes installed (9 and 10) — ~700 MB extra disk. Acceptable.
- The symlink workaround means a Homebrew upgrade of `dotnet@9` to a new
  patch (e.g. 9.0.17) will require re-running the symlink step. Documented
  in `docs/local-setup.md`.

Revisit: when pac 2.x publishes a build that works on macOS + .NET 10
(track https://github.com/microsoft/powerplatform-cli/issues), drop this
workaround.
