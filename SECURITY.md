# Security policy

## Not a medical device
Fidetype is **research software**. It is **not a medical device**. It is not certified, cleared or approved by any regulator for clinical, diagnostic or assistive use. Do not use it as the only means of communication for a person who depends on it.

## Supported versions
Fidetype is pre-release. Only the latest code gets security fixes.

| Version | Supported |
|---|---|
| `main` branch | Yes |
| 0.0.x (latest release) | Yes |
| Older versions | No |

## Report a vulnerability
**Do not report a vulnerability in a public issue.**

Use GitHub private vulnerability reporting:
1. Go to the [Security tab](https://github.com/zhangzibo/fidetype/security) of the repository.
2. Click **Report a vulnerability**. Or open [a new advisory](https://github.com/zhangzibo/fidetype/security/advisories/new) directly.
3. Describe the problem, the affected version, and the steps to reproduce it.

What to expect:
- We acknowledge the report within **7 days**.
- We tell you our assessment and a plan within **30 days**.
- We credit you in the advisory, unless you ask us not to.

## In scope
- Code execution through crafted input files (for example, NPZ or JSON Lines streams).
- Leakage of personal data or ground-truth text through the library.
- Supply-chain problems in our dependencies or CI.

## Data and privacy
Fidetype handles neural data. If you find personal data in this repository or in a release, report it in the same private way. We remove it as soon as possible.
