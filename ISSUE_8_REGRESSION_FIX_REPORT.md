# Issue #8 regression-fix report

Date: 14 September 2026

## Verdict

The two regressions identified in the consultant's Gate 0 / Gate 1 review are
fixed on branch `arena/01a0a1a3-forlawe`.

The fix is committed as `c149d3d` (`Fix issue 8 security and contrast
regressions`) and is proposed in pull request [#9](https://github.com/forlawe/forlawe/pull/9).

Issue #8 remains open until the pull request is merged into `main`.

## F-062: login timing side-channel

`hositalsuite/app/views/auth.py` now defines a fixed, unusable
`_DUMMY_PASSWORD_HASH` using the same scrypt parameters as normal user
passwords. When the username does not resolve to a user, `login_post()` calls
`check_password_hash(_DUMMY_PASSWORD_HASH, password)` before returning the
invalid-login response. A real user continues through `user.check_password()`.

This preserves the expensive password-verification work without creating a
credential that can authenticate. The dummy hash is fixed rather than created
per request, so the mitigation itself does not introduce a new timing signal.
The ambiguous-username branch also pays the dummy verification cost before it
returns its routing guidance.

## F-080: WCAG contrast tokens

The foreground tokens in `app/static/css/app.css` were restored to the
previously verified AA-safe values:

| Token | Value | Contrast on white |
|---|---:|---:|
| `--amber` | `#8f641c` | 5.24:1 |
| `--orange` | `#ac5b01` | 4.94:1 |
| `--faint` | `#687887` | 4.54:1 |

The copied legacy values were also removed from the admin hospital warning,
the onboarding footer, and the triage consulting guide so those surfaces do
not quietly reintroduce the failing palette.

## Regression coverage

New file: `hositalsuite/tests/test_issue8_regressions.py`

It verifies that:

1. an unknown username actually invokes the fixed dummy hash through the
   rendered login endpoint; and
2. the three CSS foreground tokens are present, are not the regressed values,
   and compute to at least the WCAG AA 4.5:1 ratio on white.

## Verification

- Issue 8 regression tests: **2 passed**
- Login and hardening tests: **15 passed**
- Gate 1 and foundation tests: **40 passed**
- Full suite: **1113 passed, 8 skipped, 2 warnings**

The warnings are the existing SQLAlchemy `Query.get()` deprecation warnings
in `tests/test_audit_round_roster_ussd_roles.py`; there were no failures.

## GitHub delivery

- Branch pushed: `arena/01a0a1a3-forlawe`
- Pull request: [#9](https://github.com/forlawe/forlawe/pull/9)
- The PR body includes `Closes #8 after merge`.
- The GitHub integration allowed the PR to be created but rejected a direct
  comment on Issue #8 with `Resource not accessible by integration`. Therefore
  the issue is intentionally not claimed as closed here; merging PR #9 should
  close it through the PR's closing reference.
