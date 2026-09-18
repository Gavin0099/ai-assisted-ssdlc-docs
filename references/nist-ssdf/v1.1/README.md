# NIST SSDF v1.1 Reference Slice

This directory is the authoritative-reference input for the S0 SSDF Direct Assessment experiment.

## Baseline

- Framework: NIST Secure Software Development Framework (SSDF)
- Publication: NIST SP 800-218
- Version: 1.1
- Status: Final
- Publication date: 2022-02-03
- Authoritative page: https://csrc.nist.gov/pubs/sp/800/218/final
- DOI: https://doi.org/10.6028/NIST.SP.800-218

As of 2026-09-17, NIST also lists SP 800-218 Rev. 1 / SSDF v1.2 as a draft. S0 deliberately uses v1.1 because it remains the final baseline. A future experiment may compare the draft separately, but findings from this dataset must not be labeled as v1.2 findings.

## S0 Scope

S0 does not copy the entire SSDF into this repository. `tasks.yaml` contains a representative task slice spanning PO, PS, PW, and RV so that the project can test whether an AI reviewer can produce useful, source-bounded findings before a larger reference ingestion effort is justified.

## Claim Boundary

The fields are intentionally separated:

- `normative_reference`: identifies the NIST task and provides a short paraphrase of the task's purpose. NIST remains the authority; this repository is not the normative source.
- `derived_guidance`: local review questions and expected evidence types used to help an AI reviewer inspect a company SSDLC document. These questions are non-normative and must never be presented as NIST requirements.
- `cannot_claim`: statements the assessment must not upgrade into compliance or implementation conclusions without supporting evidence.

A mapping result such as `COVERED` or `PARTIAL` is an assessment of document coverage against the selected reference task. It is not a claim that the organization conforms to NIST SSDF.

## S0 Non-Goals

- No OWASP SAMM, SLSA, IEC 62443, or device-specific overlay.
- No maturity score.
- No compliance score.
- No automated closure of findings.
- No assumption that a policy statement proves implementation.
- No attempt to normalize multiple frameworks into an internal practice catalog.
