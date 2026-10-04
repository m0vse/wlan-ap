/* Durable owner-only store operations. This does not authorize activation. */
#define _GNU_SOURCE
#include <sys/stat.h>
#include <sys/types.h>
#include <fcntl.h>
#include <unistd.h>
#include <ctype.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void refused(void) {
    fputs("Private identity store operation refused\n", stderr);
    exit(2);
}

static void component(const char *name) {
    if (!name[0] || strlen(name) > 128 || !strcmp(name, ".") || !strcmp(name, ".."))
        refused();
    for (const unsigned char *c = (const unsigned char *)name; *c; c++)
        if (!isalnum(*c) && *c != '-' && *c != '_' && *c != '.')
            refused();
}

static int directory(const char *path) {
    int fd = open(path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    struct stat st;
    if (fd < 0 || fstat(fd, &st) || !S_ISDIR(st.st_mode) ||
        st.st_uid != geteuid() || (st.st_mode & 0777) != 0700)
        refused();
    return fd;
}

static int file(int dir, const char *name) {
    component(name);
    int fd = openat(dir, name, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    struct stat st;
    if (fd < 0 || fstat(fd, &st) || !S_ISREG(st.st_mode) ||
        st.st_uid != geteuid() || (st.st_mode & 0777) != 0600 ||
        st.st_nlink != 1 || st.st_size < 1 || st.st_size > 65536)
        refused();
    return fd;
}

static void fault(const char *phase) {
#ifdef PRIVATE_PKI_TEST_FAULTS
    const char *requested = getenv("PRIVATE_PKI_TEST_FAULT");
    if (requested && !strcmp(requested, phase))
        _exit(88);
#else
    (void)phase;
#endif
}

int main(int argc, char **argv) {
    if (argc < 4)
        refused();
    int dir = directory(argv[2]);
    if (!strcmp(argv[1], "seal")) {
        for (int i = 3; i < argc; i++) {
            int fd = file(dir, argv[i]);
            if (fsync(fd) || close(fd))
                refused();
        }
        if (fsync(dir))
            refused();
    } else if (!strcmp(argv[1], "commit") && argc == 5) {
        component(argv[4]);
        if (!strcmp(argv[3], argv[4]))
            refused();
        int fd = file(dir, argv[3]);
        struct stat old;
        if (!fstatat(dir, argv[4], &old, AT_SYMLINK_NOFOLLOW)) {
            int previous = file(dir, argv[4]);
            if (close(previous))
                refused();
        } else if (errno != ENOENT) {
            refused();
        }
        if (fsync(fd) || close(fd) || fsync(dir))
            refused();
        fault("before-rename");
        if (renameat(dir, argv[3], dir, argv[4]))
            refused();
        fault("after-rename");
        if (fsync(dir))
            refused();
    } else {
        refused();
    }
    if (close(dir))
        refused();
    return 0;
}
