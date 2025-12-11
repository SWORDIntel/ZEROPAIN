# ZeroPain submodule notes

- Upstream: https://github.com/SWORDIntel/ZEROPAIN
- Pinned commit: 95a30c11c4749d85611064ec2f33e3d51a003973
- Location: lab/ZEROPAIN (git submodule)

## Update guidance
- To pull upstream changes: `git submodule update --remote lab/ZEROPAIN`
- After updating, re-pin by committing the new submodule SHA in the superproject.
- Keep `requirements.lock.txt` in sync with upstream `requirements.txt` when dependencies change.

## Usage
- Install deps from `requirements.lock.txt` (mirrors upstream requirements).
- Consult upstream README for pipeline usage; DSMIL integrations will wrap CLI/TUI/web entrypoints via the pharma adapter.

