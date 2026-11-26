# Security

Report a vulnerability privately: this repository's **Security** tab, then **Report a vulnerability**. Please don't open a public issue for one.

A skill is a set of instructions an agent follows, so these count as vulnerabilities here:

- anything in `skills/sfx/SKILL.md` or its references that would lead an agent to run something unsafe, fetch from an untrusted place or leak a secret
- anything in `find` or `fetch` (the only commands that touch the network) that writes outside the output folder or trusts what a server sends back
- anything in CI that could run code from a pull request with more than read access
