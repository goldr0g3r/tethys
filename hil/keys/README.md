# HIL keys (AES-128 seed-and-key, space profile)

> **NEVER commit a key into this directory.**
> The directory is reserved for the space profile's AES-128 seed-and-key
> handshake (per [ADR-0006](../../docs/adr/0006-aes-128-seed-and-key.md));
> the `.gitignore` blocks every file except this README and the
> `.gitignore` itself so a `git add hil/keys/*` cannot leak.

## What lives here

Per-scenario, per-bench, **16 raw bytes** generated locally:

```text
hil/keys/<scenario>.key      # 16 bytes; not committed
```

Each key matches the `auth.key_file` path declared in a scenario JSON
under [`../scenarios/`](../scenarios/) (e.g.
[`space-reaction-wheel.json`](../scenarios/space-reaction-wheel.json) →
`hil/keys/space-test.key`).

## Generating a key

```bash
# POSIX (preferred):
openssl rand 16 > hil/keys/space-test.key
chmod 600 hil/keys/space-test.key

# Windows PowerShell:
[byte[]] $bytes = New-Object byte[] 16
(New-Object System.Security.Cryptography.RNGCryptoServiceProvider).GetBytes($bytes)
[System.IO.File]::WriteAllBytes("hil/keys/space-test.key", $bytes)
```

## Why raw bytes (not PEM / base64)

ADR-0006 mandates a **16-byte symmetric key**. The slave reads exactly
16 bytes from the seed; PEM/base64 wrappers would require extra parser
code on the slave and that code would not pass MISRA C:2023's
`no-recursion-no-goto` rule for the space profile.

## What if a key leaks

1. Treat the key as compromised; rotate immediately.
2. Open a `security` issue with the
   [`incident-and-defect.md`](../../docs/runbooks/incident-and-defect.md)
   template.
3. Force-push a history-cleaned branch (with project owner approval) if
   the key reached `main`.

## Cross-references

- [ADR-0006 AES-128 seed-and-key (space profile)](../../docs/adr/0006-aes-128-seed-and-key.md).
- [`.cursor/rules/space-profile-invariants.mdc`](../../.cursor/rules/space-profile-invariants.mdc).
- [NIST FIPS-197](https://csrc.nist.gov/publications/detail/fips/197/final) — AES specification.
- [`docs/runbooks/incident-and-defect.md`](../../docs/runbooks/incident-and-defect.md).
