---
name: Bug
about: Report a defect or regression
title: "fix(<scope>): <short title>"
labels: type/fix
assignees: ''
---

## Environment

- Tethys version / commit: (e.g. `main@<sha>` or `v0.1.0`)
- Profile: (marine | space | dev-bench)
- Transport: (UDP | TCP | CAN-FD | SocketCAN | UART/SxI + COP-1 | 1-wire FT CAN | loopback)
- Master OS: (Windows / Linux / macOS, version)
- Slave target: (posix-sim / STM32F4 / STM32F7 / STM32H7)
- Python version: (e.g. 3.11.x)
- CMake version: (e.g. 4.3.2)

## Steps to reproduce

1. ...
2. ...
3. ...

## Expected behaviour

(What did you expect to happen? Cite the spec / ADR / requirement if applicable.)

## Actual behaviour

(What actually happened? Include relevant logs, MDF4 timestamps, `DAQ_GAP` events, transport-event traces.)

## Severity

- [ ] Crash / data corruption (P0)
- [ ] Functional regression (P1)
- [ ] Workaround exists (P2)
- [ ] Cosmetic / docs only (P3)

## Suspected root cause

(Optional - if you have a theory.)

## References

- Sub-plan or research note that may be affected: (link)
- Related ADRs: (link)
