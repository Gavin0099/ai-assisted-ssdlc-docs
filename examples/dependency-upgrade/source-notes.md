# Source Notes: Dependency Upgrade

This example is synthetic. It demonstrates how a dependency upgrade is reviewed without copying registry credentials, private advisories, or raw scanner output into SSDLC documentation.

## Source Summary

- Source ref: CHANGE-DEPENDENCY-001
- Change: upgrade a shared HTTP client to a new major version
- Primary risks: package provenance, transitive dependency drift, behavior changes, rollback readiness
- Reviewer: security-owner

## Security Claims Requested

- The dependency change has a documented security decision.
- Supply-chain and availability risks are mapped to review evidence.
- Missing verification remains visible in the review queue.

## Source Boundary

Do not copy package-registry tokens, private advisory text, internal mirror URLs, proprietary SBOM contents, or raw scanner output into generated documentation.
