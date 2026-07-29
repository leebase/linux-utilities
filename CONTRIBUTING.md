# Contributing

Thanks for considering a contribution to Linux Utilities.

Keep changes small, portable, and within the documented scope of the utility
being changed. Do not add runtime dependencies, network behavior, hidden
background work, or automatic remediation without a documented design
decision.

Before opening a pull request, run:

```sh
make quality
```

Add or update deterministic tests for every behavior change. Preserve each
utility's command, output, and exit-status contracts, or document an
intentional compatible versioned change in the guide, manual, and release
notes.

Follow [SECURITY.md](SECURITY.md) for security-sensitive reports. Do not open a
public issue containing exploit details.
