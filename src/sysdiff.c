#include <stdio.h>
#include <string.h>

static void print_usage(void) {
    puts("usage: sysdiff --help|--version");
}

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--help") == 0) {
        print_usage();
        return 0;
    }
    if (argc == 2 && strcmp(argv[1], "--version") == 0) {
        puts("sysdiff 0.1.0");
        return 0;
    }
    print_usage();
    return argc == 1 ? 0 : 2;
}
