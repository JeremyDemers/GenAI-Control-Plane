# Interview Demo

1. Start the stack with `make dev`.
2. Open `http://localhost:3000`.
3. Select `employee@example.local`.
4. Submit the seeded Amazon Bedrock and GitHub Copilot request.
5. Show the employee notification and policy evaluation with manager and CTO approvals.
6. Select `approver@example.local`, show the approval notification, and approve the manager step.
7. Select `cto@example.local`, show the approval notification, and approve final access.
8. Show the request becoming `ACTIVE`.
9. Select `admin@example.local`.
10. Show the active policy version, then use Developer Controls to trigger 70%, 90%, and 100% budget thresholds.
11. Show usage and budget evidence updating with spend, remaining budget, and data freshness.
12. Show automatic suspension, incident creation, incident resolution, and admin budget notifications.
13. Restore the assignment.
14. Switch to `cto@example.local` and show the executive spend report.
15. Switch to `employee@example.local`, request a one-week extension, then approve it as the CTO.
16. Switch back to `admin@example.local`, force expiration, and show archive evidence.
17. Switch to `auditor@example.local`, review the audit trail, and export CSV evidence.

The scenario is also automated:

```bash
make e2e
```
