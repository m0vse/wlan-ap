/* Explicit root-only, one-page bench reader. No NAND writes or core re-entry. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <mtd/mtd-user.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/prctl.h>
#include <unistd.h>

int main(int argc, char **argv)
{
 const char *attribute = "/sys/bus/platform/devices/79b0000.nand/miami_probe_test";
 struct mtd_info_user info;
 unsigned char data[2048];
 char arm[32], *end;
 unsigned long page, peb;
 unsigned int first_peb;
 int fd, control, length, saved_errno;
 ssize_t got;
 off_t offset;

 if (argc != 3 || (strcmp(argv[1], "/dev/mtd2") && strcmp(argv[1], "/dev/mtd3"))) {
  fprintf(stderr, "usage: %s /dev/mtd2|/dev/mtd3 physical-page\n", argv[0]);
  return 2;
 }
 errno = 0; page = strtoul(argv[2], &end, 0);
 if (errno || *end || page % 64 || page > 1541UL * 64) return 2;
 peb = page / 64; first_peb = !strcmp(argv[1], "/dev/mtd2") ? 6 : 774;
 if (peb < first_peb || peb >= first_peb + 768) return 2;
 fd = open(argv[1], O_RDONLY | O_CLOEXEC);
 if (fd < 0 || ioctl(fd, MEMGETINFO, &info) || info.size != 96U * 1024 * 1024 ||
     info.erasesize != 131072 || info.writesize != 2048 || info.oobsize != 128) {
  perror("read-only MTD geometry"); return 1;
 }
 if (prctl(PR_SET_NAME, "miami-ecc-test", 0, 0, 0)) return 1;
 control = open(attribute, O_WRONLY | O_CLOEXEC);
 if (control < 0) { perror("open opt-in bench arm"); return 1; }
 length = snprintf(arm, sizeof(arm), "%lu\n", page);
 if (write(control, arm, length) != length) { perror("arm rejected"); return 1; }
 close(control);
 offset = (off_t)(peb - first_peb) * info.erasesize;
 errno = 0; got = pread(fd, data, sizeof(data), offset); saved_errno = errno;
 /* mtdchar may return data for an ECC error; judge the labelled kernel record. */
 printf("MIAMI_PROBE_BENCH synthetic=1 physical_page=%lu bytes=%zd errno=%d\n",
        page, got, saved_errno);
 close(fd);
 return got < 0 && saved_errno != EBADMSG ? 1 : 0;
}
