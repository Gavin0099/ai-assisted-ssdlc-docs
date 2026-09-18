# Sample Company SSDLC Policy

> Synthetic fixture for S0 SSDF Direct Assessment. This document intentionally mixes reasonable policy intent with vague, incomplete, and weakly evidenced controls. It is not a model policy.

## 1. Scope

This policy applies to company-developed desktop applications, device utilities, firmware update tools, and supporting software components.

Engineering managers are responsible for ensuring that software is developed securely. Product teams may adapt the process when project schedules or customer requirements require flexibility.

## 2. Security Requirements

All software shall be secure and protect confidential customer information.

Projects with known security requirements shall record them in the project specification. Requirements should be reviewed when major product changes occur.

Exceptions may be approved by the engineering manager when implementation is impractical.

## 3. Secure Design

Software with complex security-sensitive features should receive a security design review before implementation.

The reviewer should consider authentication, authorization, data protection, and externally supplied input. Threat modeling may be used when the reviewer considers it necessary.

The design review result should be recorded in the project notes.

## 4. Third-Party Components

Development teams should use stable and commonly adopted third-party libraries and packages.

Where possible, dependencies should be updated to a recent stable version before a major release. Known critical vulnerabilities should be fixed before shipment unless the engineering manager approves an exception.

Open-source components that are already widely used in the industry may be accepted without additional security review.

## 5. Development Toolchain

Projects should use company-approved source control and build systems.

Static analysis, dependency scanning, and other security tools may be enabled when appropriate for the project. Individual teams may select tools that fit their development environment.

Security-tool failures should be reviewed before release.

## 6. Build and Release

Release candidates require approval from the project manager and engineering manager.

Production binaries shall be code-signed when applicable. Release packages may include a checksum when requested by the customer.

The release owner shall retain the final package and release notes.

## 7. Security Verification

Security verification shall be performed before release for products that handle sensitive information or have externally reachable interfaces.

Verification may include code review, static analysis, penetration testing, or other appropriate methods. The project team determines the required scope based on schedule, risk, and available resources.

Security issues found before release should be tracked and resolved when practical.

## 8. Vulnerability Response

Customers and internal teams may report suspected security issues through normal support channels.

Reported vulnerabilities will be evaluated by the responsible engineering team and fixed as soon as reasonably practical.

Critical issues should be escalated to engineering management. External disclosure will be handled case by case.

## 9. Records

Projects should retain security-related review records together with normal development documentation when practical.

Evidence may include design notes, test reports, issue records, release approvals, or email confirmations.
