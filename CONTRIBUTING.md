# Contributing

Thanks for considering a contribution to `sysdiff`.

Keep changes small, portable, and within the explicit-snapshot comparison
scope. Do not add runtime dependencies, network behavior, live system capture,
or hidden background work without a documented design decision.

Before opening a pull request, run:

```sh
make quality
```

Add or update deterministic tests for every behavior change. Preserve the
snapshot-format and output contracts, or document an intentional compatible
versioned change in the specification and release notes.

Follow [SECURITY.md](SECURITY.md) for security-sensitive reports. Do not open a
public issue containing exploit details.
