# Test Report

## Anomaly: Remote Authentication and Push Authorization Failure

### Observed Failure / Stack Trace
```text
$ git push origin --dry-run
remote: Permission to tienvinh1210/F12_04.git denied to hazeleyes91.
fatal: unable to access 'https://github.com/tienvinh1210/F12_04.git/': The requested URL returned error: 403
```

### Suspected Root Cause
Windows Credential Manager stores credentials for two distinct targets:
1. `github.com` authenticated as `hazeleyes91`
2. `github.sydney.edu.au` authenticated as `vivu0988`

The cloned repository remote `origin` is pointed at `https://github.com/tienvinh1210/F12_04.git` on public `github.com`. When Git performs HTTPS push, Git Credential Manager selects the `github.com` token associated with `hazeleyes91`, which initially lacked write permissions to `tienvinh1210/F12_04.git`.

### Status: RESOLVED
Push permission verified via dry-run:
```text
$ git push origin HEAD:refs/heads/test-probe --dry-run
To https://github.com/tienvinh1210/F12_04.git
 * [new branch]      HEAD -> test-probe
```
Collaborator permissions are confirmed active on `origin`.
