CC ?= cc
CFLAGS ?= -std=c17 -Wall -Wextra -Wpedantic -Werror -O2

.PHONY: all test clean

all: build/sysdiff

build/sysdiff: src/sysdiff.c
	mkdir -p build
	$(CC) $(CFLAGS) -o $@ $<

test: build/sysdiff
	./tests/test_sysdiff.sh

clean:
	rm -rf build
