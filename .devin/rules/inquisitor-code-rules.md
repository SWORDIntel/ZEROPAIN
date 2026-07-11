# INQUISITOR Code Rules

These rules are extracted from the INQUISITOR static analysis tool and must be followed in all code.

---

## RULE #2: No Fake/Partial Implementations

**Severity:** ERROR

Never produce fake, stub, placeholder, or partial implementations. All code must be fully functional and production-ready.

### Forbidden Code Patterns
- `kzalloc(256, GFP_KERNEL)` — Magic number allocation. Use proper type size or find real API.
- `void *api_ctx;` — Untyped API context. Use proper type or find real API.
- `ctx->field = true; return 0;` — Flag setting without actual work. Implement actual functionality.
- `return 0; /* placeholder|stub|fake|for now */` — Fake success return. Implement actual functionality.
- `kzalloc(512, GFP_KERNEL)` — Magic number allocation. Use proper type size.
- `ctx->active = true;` — Flag setting without work. Implement actual functionality.

### Partial Implementation Markers (WARNING)
- `TODO:` or `TODO ` — Incomplete implementation marker
- `FIXME:` or `FIXME ` — Broken/incomplete code marker
- `XXX:` or `XXX ` — Problematic code marker
- `HACK:` or `HACK ` — Non-production code marker
- `TEMP:` or `TEMP ` — Temporary code marker
- `raise NotImplementedError` (Python) — Incomplete implementation
- `throw new NotImplementedException` (Java/C#) — Incomplete implementation
- `#pragma message("TODO/FIXME")` (C/C++) — Incomplete code marker

**Exemptions:** Test files, documentation files (.md, .txt, .rst)

### Bad Implementation Patterns — Security (ERROR)
- **Hardcoded passwords** — `password = "..."` with 3+ chars
- **Hardcoded API keys** — `api_key = "..."` with 10+ chars
- **Hardcoded secrets** — `secret = "..."` with 8+ chars
- **Hardcoded tokens** — `token = "..."` with 10+ chars
- **eval() usage** — Arbitrary code execution risk
- **exec() usage** — Arbitrary code execution risk

**Exemptions:** Example/demo files, placeholder values (containing "example", "your_", "placeholder")

### Bad Implementation Patterns — Code Quality (WARNING)
- `shell=True` in subprocess calls — Command injection risk
- `except: pass` — Silent exceptions, errors ignored
- `catch (...) {}` — Empty catch blocks, errors ignored
- Unchecked `int()` conversion — May raise ValueError
- Unchecked `.split()[n]` — May raise IndexError
- `open()` without `with` statement or explicit close — Unclosed files
- `malloc()` without corresponding `free()` — Memory leak
- Magic numbers in `sleep()` — Hardcoded sleep duration
- Magic numbers in `range()` — Large hardcoded range limits (100+)

**Exemptions:** Test files (for eval, exec, shell=True), optional imports (for silent exceptions), code with nearby error handling (for unchecked conversions)

### Python AST Analysis
- **Missing Error Handling (WARNING):** Functions with risky operations (`open()`, `int()`, `float()`, `json.loads()`, `pickle.loads()`, `.read()`, `.write()`, `.execute()`, `.loads()`, `.dumps()`) must have try/except blocks.
- **Missing Input Validation (INFO):** Public functions with 2+ parameters must include input validation (`isinstance()`, `type()`, `len()`, `hasattr()`, or `if` statements comparing parameters). Applies to functions with 5+ lines of code.

**Exemptions:** Test functions (starting with `test_`), private functions (starting with `_`), simple functions (<5 lines)

---

## RULE #13: Error Handling

**Severity:** WARNING

Functions that return errors must check and handle all error returns. In Go, functions returning `error` must include `if err != nil` checks. In Python, risky operations must be wrapped in try/except.

---

## RULE #15: No Future-Tense Comments

**Severity:** ERROR

Comments must not suggest future implementation. Forbidden comment patterns:
- "Would call"
- "Would use"
- "Would be"
- "Would trigger"
- "Would access"
- "Would happen"

Applies to both `//` single-line and `/* */` block comments.

---

## RULE #17: JSON Parsing Patterns

**Severity:** WARNING

JSON parsing must handle malformed input. Use try/except around `json.loads()` and validate structure after parsing.

---

## RULE #18: Network Operations

**Severity:** WARNING

Network operations must handle connection failures, timeouts, and malformed responses. Always set reasonable timeouts and check response status.

---

## RULE #20: Resource Management

**Severity:** WARNING

All allocated resources (files, connections, memory) must be properly cleaned up. Use `defer` (Go), `with` (Python), or `finally` blocks to ensure cleanup on all code paths.

---

## RULE #21: Edge Case Handling

**Severity:** WARNING

Handle edge cases including: division by zero, array/slice bounds, nil/null pointer dereference, empty string/slice operations, integer overflow.

---

## RULE #22: File I/O

**Severity:** WARNING

File I/O operations must handle: file not found, permission errors, disk full, and ensure files are properly closed.

---

## RULE #28: Encryption/Crypto

**Severity:** ERROR

Cryptographic operations must use CNSA 2.0 compliant algorithms. See RULE #108 for specific algorithm requirements.

---

## RULE #31: No Magic Number Allocations

**Severity:** ERROR

Do not use hardcoded sizes in memory allocations. Use `sizeof(type)` or proper size constants instead of magic numbers like 256 or 512.

---

## RULE #34-39: Domain-Specific Patterns

**Severity:** WARNING

- **RULE #36 (Configuration):** Configuration management must validate inputs and handle missing/invalid config gracefully.
- **RULE #38 (Logging):** Logging must not expose sensitive data. Use redaction patterns for keys, tokens, and secrets in log output.

---

## RULE #44: No Untyped Contexts

**Severity:** ERROR

Do not use `void *` for API contexts. Always use properly typed pointers or structs.

---

## RULE #51: No Fake Function Names

**Severity:** ERROR

Function names must not suggest fake implementations. Forbidden name patterns:
- Function names containing "stub"
- Function names containing "placeholder"
- Function names containing "fake"

---

## RULE #58-63: Fake Implementation Detection

**Severity:** ERROR

Functions must not return hardcoded values without computation. Functions must not set flags without performing actual work. Functions must not return success codes without executing real logic.

---

## RULE #60: No Placeholder Comments

**Severity:** ERROR

Comments must not indicate placeholder or temporary code. Forbidden patterns in comments:
- "For now"
- "Simplified"
- "Placeholder"
- "Stub"

Applies to both `//` single-line and `/* */` block comments.

---

## RULE #88: Concurrency Safety

**Severity:** ERROR

Shared state (maps, slices, channels in Go; shared variables in any language) must be protected with mutex locks or atomic operations. Concurrent modification of shared state without synchronization is forbidden.

---

## RULE #103: No Simulation/Demonstration Language

**Severity:** ERROR

Absolute prohibition of simulation, demonstration, or mock language in code and comments.

### Forbidden Words (in code and comments)
- "simulate", "simulation", "simulating"
- "demonstrate", "demonstration", "demonstrates"
- "mock", "mocking", "mockup"
- "placeholder"
- "stub"
- "for now" (in comments)
- "simplified"

### Forbidden Phrases (in comments)
- "would be"
- "would call"
- "would use"
- "would trigger"
- "would access"
- "would happen"
- "This simulates"
- "This demonstrates"
- "This would"
- "In production, would"
- "Actual .* would"

**Exceptions:**
- "mock" is allowed in test files
- Allowed in license enforcement / spider code

---

## RULE #105: Mandatory Atomic Types for Concurrent Access

**Severity:** ERROR

In C kernel code, struct fields with names containing `active`, `count`, `counter`, `flag`, `ref`, or `refs` must use `atomic_t` instead of `u32`, `u64`, or `int`.

Pattern: `(u32|u64|int) field_active;` or `(u32|u64|int) field_count;` → must be `atomic_t field_active;`

---

## RULE #106: Kernel Code Correctness

**Severity:** ERROR

In C kernel code (files without Windows headers like `windows.h`, `winsock2.h`):

### Required Patterns
- **Booleans:** Use `int` with `1`/`0` instead of `bool` with `true`/`false`
- **Memory allocation:** Use `kmalloc()` with `GFP_KERNEL` or `GFP_ATOMIC` instead of `malloc()`
- **Memory deallocation:** Use `kfree()` instead of `free()`
- **Printing:** Use `pr_info()`, `pr_warn()`, `pr_err()` instead of `printf()`
- **Error codes:** Use kernel error constants (`-EINVAL`, `-ENOMEM`, `-EFAULT`) instead of numeric returns like `-1` or `1`

### Skip Conditions
Files containing any of these are Windows userspace code (skip kernel checks):
- `#include <windows.h>`
- `#include <winsock2.h>`
- `#include <winternl.h>`
- `#include <winsvc.h>`
- `#include "win7_compat.h"`
- `WIN32` or `_WIN32` defines
- Files building to `.exe`

---

## RULE #108: CNSA 2.0 Compliance

**Severity:** ERROR

All cryptographic operations must comply with CNSA 2.0 standards.

### Deprecated Algorithms (FORBIDDEN)
- SHA-1 (including `crypto/sha1`, `hashlib.sha1`)
- MD5 (including `crypto/md5`, `hashlib.md5`)
- HMAC-SHA256 (use HMAC-SHA384 or HMAC-SHA512)
- AES-128 (use AES-256)
- RSA-2048 (use RSA-3072 or higher)
- ECDSA P-256 (use P-384)
- ECDH P-256 (use P-384)
- 3DES
- DES

### Required Algorithms
- **HMAC:** HMAC-SHA384 or HMAC-SHA512
- **AES:** AES-256 (preferably AES-256-GCM)
- **ECDSA:** P-384
- **ECDH:** P-384
- **Signing:** ECDSA P-384 or ML-DSA-87

### Deprecated Imports
- `crypto/sha1` → use `crypto/sha512`
- `crypto/md5` → use `crypto/sha512`
- `hashlib.sha1` → use `hashlib.sha384` or `hashlib.sha512`
- `hashlib.md5` → use `hashlib.sha384` or `hashlib.sha512`
- `hmac.sha256` → use `hmac.sha384` or `hmac.sha512`

### Context Exceptions (NOT violations)
- **SSL cipher negation:** `!MD5`, `!DES`, `!DSS` in cipher strings means EXCLUDE — this is correct configuration
- **Log redaction:** Patterns containing "redact" or "REDACTED" are security best practices
- **Malware detection:** Code that detects/reports malware's algorithm usage (YARA rules, regex patterns, keyword lists) is legitimate analysis, not a violation
- **Metadata access:** Accessing `description` fields in dictionaries/objects is not crypto usage

---

## RULE #109: Testing Requirements

**Severity:** WARNING

Code must have appropriate test coverage. Tests must be meaningful (not just stubs) and cover both happy paths and error cases.

---

## RULE #110: Error Handling Completeness

**Severity:** WARNING

All error-returning function calls must have their errors checked. In Go, functions returning `error` must be handled with `if err != nil`. Common error-returning functions include: `Open`, `Read`, `Write`, `Close`, `Create`, `Remove`, `Marshal`, `Unmarshal`, `Parse`, `New`, `Make`, `Allocate`, `Get`, `Set`, `Update`, `Delete`, `Dial`, `Listen`.

---

## RULE #113: Resource Cleanup

**Severity:** WARNING

All resources must be cleaned up on all code paths. Track allocations and ensure corresponding cleanup:
- **Allocation functions:** `Open`, `Create`, `New`, `Make`, `Allocate`, `Dial`, `Listen`
- **Cleanup functions:** `Close`, `Free`, `Release`, `Cleanup`, `Destroy`

Use `defer` (Go), `with` (Python), or `finally` blocks to guarantee cleanup.

---

## Rust Safety Rules

**Severity:** WARNING

### Unsafe Blocks
All `unsafe` blocks in Rust must have a justification comment on the preceding line explaining why unsafe is necessary. The comment must contain "justification" or "reason".

### unwrap() Usage
Avoid `.unwrap()` in production code — it may panic. Use proper error handling with `match` or the `?` operator instead.

---

## Edge Case Rules

**Severity:** ERROR/WARNING

- **Division/modulo by zero (ERROR):** Check for zero before division (`/`) or modulo (`%`) operations
- **Array/slice bounds (WARNING):** Verify index is within bounds before array/slice access
- **Nil pointer dereference (WARNING):** Check for nil before accessing pointer fields
- **Empty string/slice operations (WARNING):** Check for empty string/slice before operations like `Split`, `Trim`, `Replace`, `Index`, `Contains`

---

## Concurrency Rules

**Severity:** ERROR

- Shared state (maps, slices, channels) must not be modified without mutex protection
- Use `sync.Mutex` or `sync.RWMutex` for shared state access in Go
- Use atomic operations (`atomic_t` in C, `sync/atomic` in Go) for counters and flags
- Increment/decrement of shared state must be protected

---

## File Exclusions

The following patterns are excluded from all checks:
- `**/vendor/**` — Third-party code
- `**/node_modules/**` — Third-party code
- `**/*_test.go` — Test files (may use mocks)
- `**/test_*.py` — Test files
- `**/tests/**` — Test directory
- `**/__pycache__/**` — Python cache
- `**/target/**` — Rust build artifacts
- `**/.git/**` — Git directory
- `**/ENUMERATOR/c_enumerator/**` — Windows userspace code (uses malloc/free/printf/bool correctly)
- `**/archive/**` — Legacy/archive code (excluded by default)
- `**/migrations/**` — Database migrations
- `**/generated/**` — Generated code
- `legacy_*` — Legacy files
- `*_backup.*` — Backup files

---

## Supported File Types

**Include:** `.py`, `.c`, `.h`, `.go`, `.cpp`, `.hpp`, `.rs`
**Exclude:** `.min.js`, `.min.css`
