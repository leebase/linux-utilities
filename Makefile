CC ?= cc
CFLAGS ?= -std=c17 -Wall -Wextra -Wpedantic -Werror -O2
PYTHON ?= python3
SHELL := /bin/bash

SRC := src/sysdiff.c
BIN := build/sysdiff
MANPAGE := man/sysdiff.1
STRICT_WARNINGS := -std=c17 -Wall -Wextra -Wpedantic -Werror
STRICT_CFLAGS := $(STRICT_WARNINGS) -O2
ASAN_CFLAGS := $(STRICT_WARNINGS) -O1 -g -fsanitize=address -fno-omit-frame-pointer
UBSAN_CFLAGS := $(STRICT_WARNINGS) -O1 -g -fsanitize=undefined -fno-omit-frame-pointer
VALGRIND_CFLAGS := $(STRICT_WARNINGS) -O1 -g
CLANG_TIDY_CHECKS := clang-analyzer-*,bugprone-*,performance-*,portability-*,-bugprone-easily-swappable-parameters,-clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling
PYTEST_NO_CACHE := PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m pytest -p no:cacheprovider

DESTDIR ?=
prefix ?= /usr/local
bindir ?= $(prefix)/bin
mandir ?= $(prefix)/share/man
man1dir ?= $(mandir)/man1

DIST_DIR := dist
DIST_ARCHIVE := $(DIST_DIR)/sysdiff-source.tar.gz
DIST_CHECKSUM := $(DIST_DIR)/sysdiff-source.tar.gz.sha256
SOURCE_DATE_EPOCH ?= 0
DIST_PREFIX := sysdiff
DISTCHECK_EPOCH := 946684800
# Tracked release pathspecs only (source, tests, build metadata, docs, license).
DIST_PATHSPECS := \
	Makefile \
	LICENSE \
	README.md \
	CHANGELOG.md \
	SECURITY.md \
	CONTRIBUTING.md \
	.gitignore \
	src \
	man \
	tests \
	scripts \
	docs

.PHONY: all sysdiff test check clean quality make-quality test-suite test-shell \
	install uninstall dist distcheck \
	gcc-strict clang-strict clang-syntax format-check clang-tidy-check \
	cppcheck-check clang-analyzer-check \
	man-check sanitizer-test asan-test ubsan-test valgrind-test \
	test-sanitize test-asan test-ubsan test-valgrind \
	benchmark benchmark-check

all: $(BIN)

sysdiff: $(BIN)

$(BIN): $(SRC)
	mkdir -p build
	$(CC) $(CFLAGS) -o $@ $<

install: $(BIN)
	install -d "$(DESTDIR)$(bindir)"
	install -d "$(DESTDIR)$(man1dir)"
	install -m 755 "$(BIN)" "$(DESTDIR)$(bindir)/sysdiff"
	install -m 644 "$(MANPAGE)" "$(DESTDIR)$(man1dir)/sysdiff.1"

uninstall:
	rm -f "$(DESTDIR)$(bindir)/sysdiff"
	rm -f "$(DESTDIR)$(man1dir)/sysdiff.1"

test: test-suite

check: quality

quality:
	$(MAKE) clean
	$(MAKE) gcc-strict
	$(MAKE) clang-strict
	$(MAKE) format-check
	$(MAKE) clang-tidy-check
	$(MAKE) cppcheck-check
	$(MAKE) clang-analyzer-check
	$(MAKE) man-check
	$(MAKE) test-suite
	$(MAKE) benchmark-check
	$(MAKE) test-sanitize
	$(MAKE) test-valgrind

make-quality: quality

gcc-strict:
	@set -e; \
	if ! command -v gcc >/dev/null 2>&1; then \
		printf 'error: gcc is required for make gcc-strict\n' >&2; \
		exit 1; \
	fi; \
	workdir=$$(mktemp -d) || exit 1; \
	trap 'rm -rf "$$workdir"' EXIT HUP INT TERM; \
	tmpbin="$$workdir/sysdiff"; \
	gcc $(STRICT_CFLAGS) -o "$$tmpbin" $(SRC)

clang-strict:
	@set -e; \
	if ! command -v clang >/dev/null 2>&1; then \
		printf 'error: clang is required for make clang-strict\n' >&2; \
		exit 1; \
	fi; \
	workdir=$$(mktemp -d) || exit 1; \
	trap 'rm -rf "$$workdir"' EXIT HUP INT TERM; \
	tmpbin="$$workdir/sysdiff"; \
	clang $(STRICT_CFLAGS) -o "$$tmpbin" $(SRC)

clang-syntax:
	clang $(STRICT_WARNINGS) -fsyntax-only $(SRC)

format-check:
	clang-format --dry-run --Werror $(SRC)

clang-tidy-check:
	clang-tidy --checks='$(CLANG_TIDY_CHECKS)' --warnings-as-errors='*' $(SRC) -- $(STRICT_WARNINGS)

cppcheck-check:
	cppcheck --quiet --enable=all --suppress=missingIncludeSystem --error-exitcode=1 $(SRC)

# Clang static analyzer via clang --analyze (no scan-build / report dir required).
# analyzer-werror makes findings fail the gate; output stays under mktemp.
clang-analyzer-check:
	@set -euo pipefail; \
	if ! command -v clang >/dev/null 2>&1; then \
		printf 'error: clang is required for make clang-analyzer-check\n' >&2; \
		exit 1; \
	fi; \
	workdir=$$(mktemp -d) || exit 1; \
	trap 'rm -rf "$$workdir"' EXIT HUP INT TERM; \
	clang --analyze $(STRICT_WARNINGS) -Xclang -analyzer-werror \
		-Xclang -analyzer-output=text -o "$$workdir/sysdiff" $(SRC)

man-check:
	@warnfile=$$(mktemp) || exit 1; \
	status=0; \
	if ! groff -man -Tutf8 -ww -z $(MANPAGE) 2>"$$warnfile"; then \
		status=1; \
	elif [ -s "$$warnfile" ]; then \
		status=1; \
	fi; \
	if [ "$$status" -ne 0 ]; then \
		cat "$$warnfile" >&2; \
	fi; \
	rm -f "$$warnfile"; \
	exit "$$status"

test-shell: $(BIN)
	./tests/test_sysdiff.sh

test-suite: $(BIN)
	$(MAKE) test-shell
	SYSDIFF_BIN="$(CURDIR)/$(BIN)" $(PYTEST_NO_CACHE) tests/ -q

sanitizer-test: test-sanitize

asan-test: test-asan

ubsan-test: test-ubsan

valgrind-test: test-valgrind

test-sanitize: test-asan test-ubsan

test-asan:
	@$(PYTHON) scripts/check_tools.py --memory-gate sanitize
	@set -eu; \
	workdir=$$(mktemp -d) || exit 1; \
	trap 'rm -rf "$$workdir"' EXIT HUP INT TERM; \
	tmpbin="$$workdir/sysdiff-asan"; \
	if ! clang $(ASAN_CFLAGS) -o "$$tmpbin" $(SRC); then \
		printf 'error: AddressSanitizer build failed (clang or ASan runtime missing)\n' >&2; \
		exit 1; \
	fi; \
	status=0; \
	ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 SYSDIFF_BIN="$$tmpbin" \
		./tests/test_sysdiff.sh || status=$$?; \
	if [ "$$status" -eq 0 ]; then \
		ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 SYSDIFF_BIN="$$tmpbin" \
			$(PYTEST_NO_CACHE) tests/ -q || status=$$?; \
	fi; \
	exit "$$status"

test-ubsan:
	@$(PYTHON) scripts/check_tools.py --memory-gate sanitize
	@set -eu; \
	workdir=$$(mktemp -d) || exit 1; \
	trap 'rm -rf "$$workdir"' EXIT HUP INT TERM; \
	tmpbin="$$workdir/sysdiff-ubsan"; \
	if ! clang $(UBSAN_CFLAGS) -o "$$tmpbin" $(SRC); then \
		printf 'error: UndefinedBehaviorSanitizer build failed (clang or UBSan runtime missing)\n' >&2; \
		exit 1; \
	fi; \
	status=0; \
	UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 SYSDIFF_BIN="$$tmpbin" \
		./tests/test_sysdiff.sh || status=$$?; \
	if [ "$$status" -eq 0 ]; then \
		UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 SYSDIFF_BIN="$$tmpbin" \
			$(PYTEST_NO_CACHE) tests/ -q || status=$$?; \
	fi; \
	exit "$$status"

test-valgrind:
	@$(PYTHON) scripts/check_tools.py --memory-gate valgrind
	@set -eu; \
	workdir=$$(mktemp -d) || exit 1; \
	trap 'rm -rf "$$workdir"' EXIT HUP INT TERM; \
	tmpbin="$$workdir/sysdiff-valgrind"; \
	if ! gcc $(VALGRIND_CFLAGS) -o "$$tmpbin" $(SRC); then \
		printf 'error: Valgrind debug build failed\n' >&2; \
		exit 1; \
	fi; \
	status=0; \
	SYSDIFF_BIN="$$tmpbin" SYSDIFF_UNDER_VALGRIND=1 \
		./tests/test_sysdiff.sh || status=$$?; \
	if [ "$$status" -eq 0 ]; then \
		SYSDIFF_BIN="$$tmpbin" SYSDIFF_UNDER_VALGRIND=1 \
			$(PYTEST_NO_CACHE) tests/ -q || status=$$?; \
	fi; \
	exit "$$status"

clean:
	rm -rf build

# Deterministic Linux performance/resource benchmark (temp-dir build only).
benchmark:
	@mkdir -p artifacts/performance
	$(PYTHON) scripts/benchmark_sysdiff.py --output artifacts/performance/sysdiff-benchmark.json

# Quality-gate benchmark: same harness, JSON report under mktemp (no workspace write).
benchmark-check:
	@set -euo pipefail; \
	if [ ! -f scripts/benchmark_sysdiff.py ]; then \
		printf 'error: scripts/benchmark_sysdiff.py is required for make benchmark-check\n' >&2; \
		exit 1; \
	fi; \
	outdir=$$(mktemp -d) || exit 1; \
	trap 'rm -rf "$$outdir"' EXIT HUP INT TERM; \
	$(PYTHON) scripts/benchmark_sysdiff.py --output "$$outdir/sysdiff-benchmark.json"

# Reproducible source archive from tracked release pathspecs only.
# Override SOURCE_DATE_EPOCH (non-negative integer) for bit-identical rebuilds.
dist:
	@set -euo pipefail; \
	epoch="$(SOURCE_DATE_EPOCH)"; \
	case "$$epoch" in \
		''|*[!0-9]*) \
			printf 'error: SOURCE_DATE_EPOCH must be a non-negative integer (got: %s)\n' \
				"$${epoch:-<empty>}" >&2; \
			exit 1; \
			;; \
	esac; \
	if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then \
		printf 'error: make dist requires a git work tree to select tracked files\n' >&2; \
		exit 1; \
	fi; \
	mapfile -t members < <(git ls-files -z -- $(DIST_PATHSPECS) | tr '\0' '\n' | LC_ALL=C sort); \
	if [ "$${#members[@]}" -eq 0 ]; then \
		printf 'error: make dist found no tracked release files\n' >&2; \
		exit 1; \
	fi; \
	mkdir -p "$(DIST_DIR)"; \
	stage=$$(mktemp -d /tmp/sysdiff-dist-stage.XXXXXXXXXX) || exit 1; \
	trap 'rm -rf "$$stage"' EXIT HUP INT TERM; \
	prefix_dir="$$stage/$(DIST_PREFIX)"; \
	mkdir -p "$$prefix_dir"; \
	for member in "$${members[@]}"; do \
		[ -n "$$member" ] || continue; \
		if [ ! -e "$$member" ]; then \
			printf 'error: tracked dist member missing: %s\n' "$$member" >&2; \
			exit 1; \
		fi; \
		dest="$$prefix_dir/$$member"; \
		mkdir -p "$$(dirname "$$dest")"; \
		cp -f "$$member" "$$dest"; \
	done; \
	find "$$prefix_dir" -type d -exec chmod 0755 {} +; \
	find "$$prefix_dir" -type f -exec chmod 0644 {} +; \
	find "$$prefix_dir" -type f -name '*.sh' -exec chmod 0755 {} +; \
	tar \
		--format=ustar \
		--sort=name \
		--mtime="@$$epoch" \
		--owner=0 \
		--group=0 \
		--numeric-owner \
		--mode='u=rwX,go=rX' \
		-C "$$stage" \
		-cf - "$(DIST_PREFIX)" \
		| gzip -n -9 >"$(DIST_ARCHIVE).tmp"; \
	mv -f "$(DIST_ARCHIVE).tmp" "$(DIST_ARCHIVE)"; \
	( cd "$(DIST_DIR)" && sha256sum "$$(basename "$(DIST_ARCHIVE)")" >"$$(basename "$(DIST_CHECKSUM)").tmp" ); \
	mv -f "$(DIST_CHECKSUM).tmp" "$(DIST_CHECKSUM)"; \
	printf 'wrote %s\n' "$(DIST_ARCHIVE)"; \
	printf 'wrote %s\n' "$(DIST_CHECKSUM)"

# Rebuild at a fixed epoch, compare digests, then build+test a clean extract
# outside the workspace. Extraction state is under /tmp and removed on exit.
distcheck:
	@set -euo pipefail; \
	epoch="$(DISTCHECK_EPOCH)"; \
	verify_root=$$(mktemp -d /tmp/sysdiff-distcheck.XXXXXXXXXX) || exit 1; \
	trap 'rm -rf "$$verify_root"' EXIT HUP INT TERM; \
	$(MAKE) dist SOURCE_DATE_EPOCH="$$epoch"; \
	cp -f "$(DIST_ARCHIVE)" "$$verify_root/first.tar.gz"; \
	cp -f "$(DIST_CHECKSUM)" "$$verify_root/first.sha256"; \
	digest1=$$(awk '{print $$1}' "$$verify_root/first.sha256"); \
	$(MAKE) dist SOURCE_DATE_EPOCH="$$epoch"; \
	cp -f "$(DIST_ARCHIVE)" "$$verify_root/second.tar.gz"; \
	cp -f "$(DIST_CHECKSUM)" "$$verify_root/second.sha256"; \
	digest2=$$(awk '{print $$1}' "$$verify_root/second.sha256"); \
	if [ "$$digest1" != "$$digest2" ]; then \
		printf 'error: source archive digests differ across same-epoch rebuilds\n' >&2; \
		exit 1; \
	fi; \
	if ! cmp -s "$$verify_root/first.tar.gz" "$$verify_root/second.tar.gz"; then \
		printf 'error: source archives differ across same-epoch rebuilds\n' >&2; \
		exit 1; \
	fi; \
	if ! cmp -s "$$verify_root/first.sha256" "$$verify_root/second.sha256"; then \
		printf 'error: source checksum files differ across same-epoch rebuilds\n' >&2; \
		exit 1; \
	fi; \
	if ! ( cd "$(DIST_DIR)" && sha256sum -c "$$(basename "$(DIST_CHECKSUM)")" >/dev/null ); then \
		printf 'error: %s does not match %s\n' "$(DIST_CHECKSUM)" "$(DIST_ARCHIVE)" >&2; \
		exit 1; \
	fi; \
	members=$$(tar -tzf "$(DIST_ARCHIVE)"); \
	while IFS= read -r member; do \
		[ -n "$$member" ] || continue; \
		case "$$member" in \
			/*|*/../*|*/..|../*|..) \
				printf 'error: unsafe archive member path: %s\n' "$$member" >&2; \
				exit 1; \
				;; \
			$(DIST_PREFIX)|$(DIST_PREFIX)/|$(DIST_PREFIX)/*) ;; \
			*) \
				printf 'error: archive member missing %s/ prefix: %s\n' \
					"$(DIST_PREFIX)" "$$member" >&2; \
				exit 1; \
				;; \
		esac; \
		case "$$member" in \
			*/.git|*/.git/*|.git|.git/*|*code-reviews*|*playbooks*|*plans*|\
			*/dist/*|*/dist|.pytest_cache*|*__pycache__*|*agent-orch*) \
				printf 'error: archive includes excluded path: %s\n' "$$member" >&2; \
				exit 1; \
				;; \
		esac; \
	done <<< "$$members"; \
	for required in \
		"$(DIST_PREFIX)/Makefile" \
		"$(DIST_PREFIX)/LICENSE" \
		"$(DIST_PREFIX)/README.md" \
		"$(DIST_PREFIX)/CHANGELOG.md" \
		"$(DIST_PREFIX)/src/sysdiff.c" \
		"$(DIST_PREFIX)/man/sysdiff.1" \
		"$(DIST_PREFIX)/tests/test_sysdiff.sh" \
		"$(DIST_PREFIX)/tests/test_sysdiff.py"; do \
		if ! printf '%s\n' "$$members" | grep -Fxq "$$required"; then \
			printf 'error: archive missing required member: %s\n' "$$required" >&2; \
			exit 1; \
		fi; \
	done; \
	extract_dir="$$verify_root/extract"; \
	mkdir -p "$$extract_dir"; \
	tar -xzf "$(DIST_ARCHIVE)" -C "$$extract_dir"; \
	sourcedir="$$extract_dir/$(DIST_PREFIX)"; \
	case "$$sourcedir" in \
		"$(CURDIR)"|"$(CURDIR)"/*) \
			printf 'error: distcheck extract resolved inside workspace\n' >&2; \
			exit 1; \
			;; \
	esac; \
	$(MAKE) -C "$$sourcedir"; \
	$(MAKE) -C "$$sourcedir" test; \
	printf 'distcheck: ok\n'
