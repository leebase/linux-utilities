CC ?= cc
CFLAGS ?= -std=c17 -Wall -Wextra -Wpedantic -Werror -O2
PYTHON ?= python3

SRC := src/sysdiff.c
MANPAGE := man/sysdiff.1
STRICT_WARNINGS := -std=c17 -Wall -Wextra -Wpedantic -Werror
STRICT_CFLAGS := $(STRICT_WARNINGS) -O2
ASAN_CFLAGS := $(STRICT_WARNINGS) -O1 -g -fsanitize=address -fno-omit-frame-pointer
UBSAN_CFLAGS := $(STRICT_WARNINGS) -O1 -g -fsanitize=undefined -fno-omit-frame-pointer
CLANG_TIDY_CHECKS := clang-analyzer-*,bugprone-*,performance-*,portability-*,-bugprone-easily-swappable-parameters,-clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling

.PHONY: all sysdiff test check clean quality make-quality test-suite test-shell \
	gcc-strict clang-syntax format-check clang-tidy-check cppcheck-check \
	man-check sanitizer-test asan-test ubsan-test valgrind-test

all: build/sysdiff

sysdiff: build/sysdiff

build/sysdiff: src/sysdiff.c
	mkdir -p build
	$(CC) $(CFLAGS) -o $@ $<

test: test-suite

check: quality

quality:
	$(MAKE) clean
	$(MAKE) gcc-strict
	$(MAKE) clang-syntax
	$(MAKE) format-check
	$(MAKE) clang-tidy-check
	$(MAKE) cppcheck-check
	$(MAKE) man-check
	$(MAKE) test-suite
	$(MAKE) sanitizer-test
	$(MAKE) valgrind-test

make-quality: quality

gcc-strict:
	$(MAKE) CC=gcc CFLAGS="$(STRICT_CFLAGS)" build/sysdiff

clang-syntax:
	clang $(STRICT_WARNINGS) -fsyntax-only $(SRC)

format-check:
	clang-format --dry-run --Werror $(SRC)

clang-tidy-check:
	clang-tidy --checks='$(CLANG_TIDY_CHECKS)' --warnings-as-errors='*' $(SRC) -- $(STRICT_WARNINGS)

cppcheck-check:
	cppcheck --quiet --enable=all --suppress=missingIncludeSystem --error-exitcode=1 $(SRC)

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

test-shell: build/sysdiff
	./tests/test_sysdiff.sh

test-suite: build/sysdiff
	$(MAKE) test-shell
	$(PYTHON) -m pytest tests/ -q

sanitizer-test: asan-test ubsan-test

asan-test:
	$(MAKE) clean
	$(MAKE) CC=clang CFLAGS="$(ASAN_CFLAGS)" build/sysdiff
	ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 $(MAKE) test-suite

ubsan-test:
	$(MAKE) clean
	$(MAKE) CC=clang CFLAGS="$(UBSAN_CFLAGS)" build/sysdiff
	UBSAN_OPTIONS=halt_on_error=1 $(MAKE) test-suite

valgrind-test:
	$(MAKE) clean
	$(MAKE) CC=gcc CFLAGS="$(STRICT_CFLAGS)" build/sysdiff
	SYSDIFF_UNDER_VALGRIND=1 ./tests/test_sysdiff.sh

clean:
	rm -rf build
