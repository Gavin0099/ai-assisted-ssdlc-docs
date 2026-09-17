# S0 — SSDF Direct Assessment

This experiment tests one question:

> Can an AI-assisted reviewer use a small, authoritative NIST SSDF v1.1 task slice to produce useful company-SSDLC findings while preserving evidence and claim boundaries?

## Current Boundary

- Primary baseline: NIST SP 800-218 SSDF v1.1 Final.
- Reference slice: PO.1.2, PO.3.1, PS.2.1, PW.1.1, PW.4.4, PW.8.1, RV.1.3.
- Target fixture: `fixtures/sample-company-ssdlc.md`.
- No SAMM, SLSA, device profile, normalized practice catalog, maturity score, or compliance score.
- Existing Evidence Index and Review Queue vocabularies remain unchanged.

See `assessment-contract.md` for the source and claim boundaries.

## Implementation Slices

1. **S0-A — Source-bounded assessment contract (#6)**
   - Separate NIST normative basis, local derived guidance, and reviewer inference.
   - Separate document-coverage verdicts from Review Queue status and evidence strength.
   - Prohibit unsupported conformance and quantitative coverage claims.

2. **S0-B — Golden assessment fixture (#7)**
   - Produce one human-reviewed expected task result for each selected SSDF task.
   - Keep non-normative observations outside task findings.

3. **S0-C — Deterministic assessment linter (#8)**
   - Validate structure, vocabulary, task IDs, source references, and claim boundary.
   - Do not attempt semantic correctness scoring.

4. **S0-D — AI evaluation against golden boundary (#9)**
   - Run the semantic reviewer only after A/B/C establish the expected output surface.
   - Measure unsupported normative attribution, false positives, missed gaps, and overclaims.

## Exit Question

S0 is useful only if the generated findings are materially better than restating the NIST task and remain source-bounded.

If high-value findings consistently require device/native/firmware assumptions that SSDF does not supply, record that as evidence for a later domain-profile experiment. Do not silently expand S0.
