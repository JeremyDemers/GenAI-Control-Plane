# Dependency Audit

CI gates high-severity npm advisories with `npm audit --audit-level=high`.

As of the current lockfile, `npm audit --audit-level=moderate` reports the Next-bundled PostCSS
advisory `GHSA-qx2v-qp2m-jg93`. The suggested `npm audit fix --force` path downgrades Next to an
obsolete major version, so the project keeps the high-severity gate in CI and tracks the moderate
advisory until a non-breaking Next release resolves the bundled dependency.

