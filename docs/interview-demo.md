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
10. Use Developer Controls to trigger 70%, 90%, and 100% budget thresholds.
11. Show automatic suspension at enforcement and the admin budget notifications.
12. Restore the assignment.
13. Switch to `cto@example.local` and show the executive spend report.
14. Switch back to `admin@example.local`, force expiration, and show archive evidence.
15. Switch to `auditor@example.local`, review the audit trail, and export CSV evidence.

The scenario is also automated:

```bash
make e2e
```
