# Project: ZEROPAIN DSMIL Integration & Simulation Fidelity Expansion

## Architecture
- **DSMIL Adapter**: Bridging interface between DSMIL pharma controller and ZEROPAIN CLI/TUI modules.
- **Patient Simulation**: Scalable patient generation and simulation engine, utilizing PK/PD tunables and progression models.
- **TUI Dashboard**: Interactive terminal application allowing compound browsing, custom compound building, protocol optimization, and population simulations.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| 1 | Core Implementation | Implement DSMIL adapter, unified dashboard, PK/PD tunables, simulation scalability, progression models | None | IN_PROGRESS |
| 2 | Verification & Audit | Run all unit tests, challengers, and forensic auditor to verify correctness and integrity | M1 | PLANNED |

## Interface Contracts
### DSMIL Adapter ↔ ZeroPain CLI/TUI
- CLI entrypoint: `python src/zeropain_pipeline.py --dsmil-adapter` or direct module invoke.
- TUI dashboard: Exposes unified view with compound browser, builder, optimization, simulation options.
- Data format: JSON config files mapping to `PatientGenerationConfig`, `ProtocolConfig`, and `CompoundProfile`.
