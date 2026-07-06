# Original User Request

## 2026-07-06T10:38:33Z

Implement the DSMIL adapter for interface integration and expand simulation fidelity by adding PK/PD tunables and making patient simulations scalable.

### Requirements

#### R1. Interface Integration and DSMIL Adapter
Land the DSMIL adapter and expose the CLI and TUI entrypoints. Ensure there is a unified dashboard for the compound browser, builder, optimization, and simulation tools, aiming for web/TUI parity.

#### R2. Simulation Fidelity & Scalability
Expand the compound templates to include receptor affinities, metabolic pathways, and patient-specific PK/PD tunables (e.g., weight, age, sex, comorbidities).
Make patient simulations scalable (remove hardcoded limits like "100k") so the scale can be defined dynamically.
Add medically accurate tolerance and addiction progression models with adjustable slopes.

### Acceptance Criteria

#### Integration & Fidelity
- [ ] The CLI and TUI are fully accessible via the DSMIL adapter and offer a unified dashboard experience.
- [ ] Compound templates and simulation logic incorporate the new PK/PD tunables (affinities, pathways, patient parameters).
- [ ] The patient simulation framework can dynamically scale to any requested number of patients without being hardcoded to 100k.
- [ ] Tolerance and addiction progression models are integrated and configurable.
- [ ] Existing core tests (ZEROPAIN and KEYSTONE native tests) still pass.
