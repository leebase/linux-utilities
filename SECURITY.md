# Security Policy

## Supported version

Security fixes are accepted for the latest 0.1.x release until a newer supported
series is announced.

## Reporting a vulnerability

Use the repository's **Security → Report a vulnerability** form when private
vulnerability reporting is available. Include the affected command/input,
impact, reproduction steps, and any proposed remediation.

If private reporting is not yet enabled, open a minimal public issue asking the
maintainer to establish private contact. Do not include exploit details,
malicious fixtures, secrets, or sensitive system information in that issue.

The maintainer will acknowledge a usable report, investigate it, and coordinate
disclosure and a fix according to severity. No response-time guarantee is made
for this volunteer project.

## PATH Directory Ownership

`pathaudit --path` and `pathaudit --command` apply one shared ownership trust
policy to resolved executables and to every usable PATH directory they
consult. Trusted final-target owners are only root UID 0 and the invoking
real UID from `getuid()` (not `geteuid()`). Any other `st_uid` emits
`UNSAFE_OWNER` on the canonical offending `realpath`. For directories, the
scanner resolves the PATH entry, then walks that realpath and each ancestor
through `/`, because a foreign-owned parent can replace or plant children even
when a leaf executable looks self-owned. Shared ancestor realpaths stay
deduplicated to the lowest PATH index that observed them. Missing, empty
(aside from command-mode plant-risk ownership of `.` when applicable), and
non-directory components invent no ownership findings. Explicit-root mode
never searches executables and remains ownership-blind for directories and
ancestors. Findings are a read-only metadata snapshot ranked with
`GROUP_WRITABLE` / `WORLD_WRITABLE`; they are not a live lock, ACL audit,
capability check, or automatic remediation. Interpret `UNSAFE_OWNER` as a
prompt to verify who controls PATH search order and directory trees, and
expect `stat`/`realpath` TOCTOU under concurrent filesystem change.
