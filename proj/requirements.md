

# ADR-000 — External Function Stub Generator · Context & Decision

| Status | Created    | Decided | Version |
| ------ | ---------- | ------- | ------- |
| Draft  | YYYY-MM-DD | —       | 0.1     |

## 1 · Context — Why do we need this?

1. **Embedded unit-test pain points**  
   * Third-party HAL / AUTOSAR layers expose hundreds of APIs with no implementation ⇒ builds break.  
   * Hand-writing stubs is slow and error-prone, blocking CI pipelines.

2. **Gaps in existing tools**  
   * Commercial suites (TESSY, Parasoft, QA·C) are closed-source and costly.  
   * Open-source frameworks (CMock, FFF) require full header trees; they can’t filter *only* the symbols actually referenced.

3. **Opportunity**  
   * Scan **AST** and collect only the truly referenced external symbols.  
   * Auto-derive signatures → emit compilable empty implementations → keep CI green.

## 2 · Decision — Key points

| Topic                | Decision                                                     |
| -------------------- | ------------------------------------------------------------ |
| **Parser front-end** | Start with *pycparser* (C89/99); pluggable Clang back-end later. |
| **Algorithm**        | Three passes: Collect calls → Resolve scopes/types → Render stubs. |
| **Outputs**          | Single `stubs.c` + `stubs.h`; future JSON export.            |
| **License**          | MIT                                                          |

## 3 · Non-Goals

* No behavioural mocks / expectation checking.  
* No C++ support (C99 only).  
* No inline assembly analysis.  
* No build-system file generation.

## 4 · Success Criteria

| Area          | Metric                                                       |
| ------------- | ------------------------------------------------------------ |
| **Technical** | Scan Linux kernel (~2 MLoC) < 30 s; 95 % real-world projects build first try. |
| **Process**   | One-liner GitHub Actions step; bug-fix round-trip ≤ 24 h.    |
| **Community** | 50+ GitHub ⭐ in 3 months; at least two external PRs.         |

## 5 · Consequences

| Positive                                 | Negative                                    |
| ---------------------------------------- | ------------------------------------------- |
| CI remains green without missing symbols | We maintain custom type inference.          |
| Enables long-chain grey-box tests        | Future C++ support will require extra work. |