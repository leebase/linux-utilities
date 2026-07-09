CC ?= cc
CFLAGS ?= -std=c17 -Wall -Wextra -Wpedantic -Werror -O2
PYTHON ?= python3

STRICT_CFLAGS := -std=c17 -Wall -Wextra -Wpedantic -Werror -O2
SANITIZE_CFLAGS := -std=c17 -Wall -Wextra -Wpedantic -Werror -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer

.PHONY: all sysdiff test clean make-quality test-suite sanitizer-test valgrind-test

all: build/sysdiff

sysdiff: build/sysdiff

build/sysdiff: src/sysdiff.c
	mkdir -p build
	$(CC) $(CFLAGS) -o $@ $<

test: build/sysdiff
	./tests/test_sysdiff.sh

make-quality:
	$(MAKE) clean
	$(MAKE) CC=gcc CFLAGS="$(STRICT_CFLAGS)"
	$(MAKE) clean
	$(MAKE) CC=clang CFLAGS="$(STRICT_CFLAGS)"
	$(MAKE) test-suite
	$(MAKE) sanitizer-test
	$(MAKE) clean
	$(MAKE) CC=gcc CFLAGS="$(STRICT_CFLAGS)"
	$(MAKE) valgrind-test

test-suite: build/sysdiff
	$(MAKE) test
	$(PYTHON) -m pytest tests/ -q

sanitizer-test:
	@if command -v clang >/dev/null 2>&1; then \
		$(MAKE) clean; \
		$(MAKE) CC=clang CFLAGS="$(SANITIZE_CFLAGS)"; \
		ASAN_OPTIONS=detect_leaks=0:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1 $(MAKE) test; \
	else \
		printf 'warning: clang not found; skipping sanitizer-test\n' >&2; \
	fi

# Valgrind is warning-only when the valgrind executable is unavailable in the
# current environment; when present, any reported memory error is release-blocking.
valgrind-test: build/sysdiff
	@if command -v valgrind >/dev/null 2>&1; then \
		tmp=$$(mktemp -d); \
		trap 'rm -rf "$$tmp"' EXIT HUP INT TERM; \
		printf 'same.key=value\n' >"$$tmp/snapshot"; \
		valgrind --quiet --error-exitcode=1 --leak-check=full \
			--errors-for-leak-kinds=definite,possible \
			./build/sysdiff compare "$$tmp/snapshot" "$$tmp/snapshot" >/dev/null; \
	else \
		printf 'warning: valgrind not found; skipping valgrind-test\n' >&2; \
	fi

clean:
	rm -rf build
