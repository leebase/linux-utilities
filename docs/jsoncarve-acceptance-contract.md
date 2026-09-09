# jsoncarve Acceptance Contract

## Overview

`jsoncarve` is a future small C17 filter for AI Agent Runtime and other
pre-ingest pipelines. It scans one untrusted byte stream, recognizes complete
top-level JSON objects and arrays, and copies those values to a deterministically
framed output stream. This document is the normative first-slice contract; it
specifies behavior for a later implementation but does not claim that a binary,
test suite, package, or release exists.

The utility is deliberately a carver rather than a general JSON processor. It
does enough strict JSON recognition to avoid emitting invalid values, while
preserving the accepted value's input bytes. It does not build a reusable JSON
tree, interpret application schemas, or expose selection and rewriting
operations.

## Problem

Agent output, logs, terminal captures, and model transcripts can contain prose
or arbitrary bytes around useful JSON. A downstream decoder should not need to
guess where a nested object ends, mistake a brace inside a string for structure,
or accept a prefix cut from a truncated response. At the same time, running a
large query language or silently repairing hostile input is inappropriate at a
security-sensitive ingestion boundary.

`jsoncarve` supplies a narrow mechanical boundary: scan noise, strictly
recognize complete container values, preserve each accepted byte span, and
frame multiple results unambiguously. Invalid candidates are observable but do
not prevent later independent candidates from being found. Fixed limits make
CPU, memory, nesting, diagnostic volume, and total-input behavior predictable.

## CLI Surface

The data path is exactly `jsoncarve`, with no operands: bytes are read from
standard input and records are written to standard output. The sole
informational forms are `jsoncarve --help` and `jsoncarve --version`; each is
valid only as the sole argument, writes its information to stdout, writes
nothing to stderr, reads no stdin, and returns 0. Any other option, operand, or
arity is `USAGE_ERROR`, writes no stdout, emits one diagnostic, and returns 2.

The data path reads stdin through EOF unless a fatal limit or I/O failure occurs.
It emits every accepted value in encounter order. There are no input paths,
output paths, environment-controlled modes, configuration files, network
operations, locale-dependent rules, interactive prompts, or hidden fallback
formats. Diagnostics go only to stderr and never become output records.

## Capability Boundary

A candidate begins at an ASCII `{` or `[` encountered while scanning outside a
candidate. A candidate is accepted only if its entire span is one strict JSON
value under RFC 8259, with an object or array at the top level. Objects, arrays,
strings, numbers, `true`, `false`, and `null` are recognized inside that
container. Object member names must be strings, separators and colons must be in
their grammatical positions, and trailing commas, comments, bare names, NaN,
Infinity, and extra tokens before the matching outer close are invalid.

Structural braces and brackets inside strings have no nesting effect. A quote
ends a string only when it is not escaped by an odd-length immediately preceding
run of backslashes. The JSON escapes `\"`, `\\`, `\/`, `\b`, `\f`, `\n`, `\r`,
`\t`, and `\u` followed by exactly four hexadecimal digits are accepted;
unknown, short, and dangling escapes are rejected. Raw control bytes
`0x00`--`0x1f` are forbidden in strings. Input within strings must otherwise be
well-formed UTF-8, and Unicode escapes must not contain an unpaired UTF-16
surrogate. Bytes at or above `0x80` outside strings cannot form JSON whitespace
or tokens and invalidate the current candidate.

An invalid candidate is discarded in full and produces no stdout record. To
recover without trusting a corrupt parse position, scanning restarts at the byte
immediately after that candidate's opening `{` or `[`. Consequently a valid
nested-looking value inside rejected bytes may later be recovered, but an
accepted outer value suppresses all of its nested values as separate results.
At EOF, an open candidate is truncated and discarded. Noise outside candidates,
including NUL and arbitrary binary bytes, is ignored except that every byte
counts toward the total-input limit.

The fixed first-slice limits are 64 MiB (67,108,864 bytes) read from stdin, 1
MiB (1,048,576 bytes) in any candidate span including its opening and closing
bytes, 256 simultaneously open object/array levels, and 32 detailed nonfatal
candidate diagnostics. Exceeding the input, candidate, or depth limit is fatal:
no further stdin is read and status 3 results. Memory usage must be bounded by
the candidate limit plus fixed bookkeeping rather than by total input or result
count. Recognition must make linear forward progress on every byte; recovery
must not cause quadratic rescanning of buffered hostile input.

Each accepted value is emitted as an RFC 7464 JSON text sequence record: one
ASCII Record Separator byte (`0x1e`), the candidate's exact original bytes, then
one LF byte (`0x0a`). Whitespace and escape spelling inside the accepted span are
preserved; no whitespace outside it is copied. This framing remains unambiguous
when a value contains legal formatting newlines. A checked stdout write or
flush failure is fatal, although records successfully written before a later
failure cannot be recalled.

## Hazard Taxonomy

The closed diagnostic codes are `MALFORMED_CANDIDATE`,
`TRUNCATED_CANDIDATE`, `CANDIDATE_BYTES_LIMIT`, `DEPTH_LIMIT`,
`INPUT_BYTES_LIMIT`, `INPUT_READ_ERROR`, `OUTPUT_WRITE_ERROR`, and
`USAGE_ERROR`; an implementation must not invent additional codes. Invalid
UTF-8, invalid escapes, unpaired surrogates, grammar errors, mismatched closing
delimiters, and forbidden string controls are reasons reported under
`MALFORMED_CANDIDATE`, not new taxonomy members.

Every diagnostic is one printable-ASCII line beginning `jsoncarve: CODE:` and
includes a one-based absolute input byte offset when an input byte is relevant.
Untrusted bytes are rendered as `\xHH`, never written raw. Malformed and
truncated candidates are nonfatal: at most 32 detailed lines are emitted, then
exactly one `jsoncarve: MALFORMED_CANDIDATE: further candidate diagnostics
suppressed` summary if more occur. Limit, usage, and I/O hazards are fatal and
are always diagnosed even after that suppression notice. Successful extraction
with nonfatal candidate diagnostics may still return 0.

## Exit Statuses

Exit meanings are stable and mutually exclusive. Status 0 means the data path
reached EOF and emitted at least one complete value, or an informational form
completed. Status 1 means the data path reached EOF without emitting a value;
this includes pure noise and streams containing only malformed or truncated
candidates. Status 2 means command-line usage was rejected before stdin was
read. Status 3 means `INPUT_BYTES_LIMIT`, `CANDIDATE_BYTES_LIMIT`, or
`DEPTH_LIMIT` stopped processing. Status 4 means an input read, stdout write, or
stdout flush failed.

Fatal precedence is 4 over 3 over the otherwise applicable 0 or 1 when more
than one condition has already become observable; usage status 2 is decided
before data-path work begins. Nonfatal malformed/truncated diagnostics do not
change status 0 after any record is emitted. Status 3 or 4 may accompany a
valid framed prefix already written to stdout, and callers must use the final
status before committing that prefix downstream.

## Non-Goals

The first slice does not extract top-level strings, numbers, booleans, or null;
only top-level objects and arrays start candidates. It does not pretty-print,
minify, canonicalize, repair, merge, sort, deduplicate, query, filter, redact,
schema-validate, or semantically interpret values. It does not decode JSON into
an exported object model or promise preservation of values that are invalid
under the strict recognition rules.

It does not accept files, directories, URLs, sockets, multiple input streams,
compression, JSON5, comments, JavaScript literals, concatenation modes, or a
user-selectable delimiter. It does not recursively emit nested values from an
accepted container, guess character encodings, normalize Unicode, follow logs,
run as a daemon, persist data, use the network, provide telemetry, or claim
race-free authorization. This documentation slice adds no implementation,
tests, build integration, packaging, installation, or release status.

## Acceptance Checks

The later implementation and its tests are acceptable only when every item
below is demonstrated. Examples must inspect raw bytes and exit status rather
than relying on terminal rendering, and hostile-input checks must complete
within explicit test timeouts.

AC-1. With no arguments, stdin is the only input and stdout is an RFC
   7464 sequence containing accepted values in encounter order; no surrounding
   noise is copied.
AC-2. Sole-argument `--help` and `--version` return 0 without reading
   stdin, while every other argument form returns 2 with empty stdout and a
   `USAGE_ERROR` diagnostic.
AC-3. Objects and arrays containing arbitrary mixed nesting are accepted,
   and an accepted outer value prevents its nested containers from being emitted
   separately.
AC-4. Braces, brackets, quotes, and even Record Separator bytes encoded
   as data within valid strings do not corrupt nesting or output framing.
AC-5. Every permitted escape is accepted, while unknown, incomplete, or
   dangling escapes and unescaped string controls produce no record for that
   candidate.
AC-6. Strict grammar rejects trailing commas, comments, bare keys,
   malformed numbers, invalid literals, mismatched closes, and tokens following
   the outer value before its close.
AC-7. String bytes must be valid UTF-8, `\u` escapes require four hex
   digits and correctly paired surrogates, and accepted bytes and spellings are
   preserved exactly.
AC-8. Arbitrary binary noise, including NUL and high bytes outside
   candidates, is ignored while the same forbidden bytes inside a candidate
   cause its rejection.
AC-9. After a malformed candidate, scanning restarts one byte after its
   opener and can recover a later or nested-looking valid top-level container in
   deterministic encounter order.
AC-10. An open candidate at EOF is discarded and diagnosed as
    `TRUNCATED_CANDIDATE`; status is 1 if no earlier value was emitted and 0 if
    at least one was emitted.
AC-11. Inputs at the 64 MiB, candidates at the 1 MiB, and nesting at the
    256-level boundaries are accepted when otherwise valid; the first byte or
    level beyond each bound returns 3 with its specified limit code.
AC-12. Peak memory is bounded independently of total result count, and
    long adversarial malformed streams make linear forward progress without
    hangs, stack exhaustion, integer overflow, or quadratic recovery work.
AC-13. Each output record is exactly `0x1e`, original candidate bytes,
    and `0x0a`, including when preserved JSON whitespace contains newlines.
AC-14. Diagnostics contain only the closed taxonomy, follow the
    printable-ASCII format, escape hostile bytes, use one-based offsets, cap
    nonfatal detail at 32, and emit the single required suppression summary.
AC-15. Exit statuses and fatal precedence match the Exit Statuses
    section, including status 0 despite earlier nonfatal rejection and the
    possibility of a framed prefix before status 3 or 4.
AC-16. Read, write, and final-flush failures return 4 with the matching
    I/O code, and no diagnostic bytes are mixed into stdout.
