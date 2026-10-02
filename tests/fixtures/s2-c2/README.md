# S2-C2 Synthetic Golden Projection

These manually specified templates define the chosen JSON/Markdown display
contract for a single synthetic FILE_EXISTS edge. They are not captured renderer
output. Substitution uses the reviewed B2 fixture JSON oracle, native Git commit,
standard SHA-256 of literal fixture bytes, and frozen S2-A §7 claims.

The product fixtures are constructed in temporary repositories; no company or
real product inputs are required. Full-byte comparison supplements the executable
Scenario 1–12 matrix, independent node/digest assertions and I/O failure probes.
The first test receipt contains one erroneous expected rule ID (RULE-LOCK instead
of the fixture's RULE-1); that is a test-oracle error, not a production defect.

Concrete node arrays preserve `[]` (no structured nodes) versus `[""]` (the
RFC 6901 root). The root regression rejects the first renderer in all four
JSON/YAML existence/equality cases and the no-node control. The Markdown golden
was amended by hand to display `[]`; it was not regenerated from renderer output.
