/* SPDX-License-Identifier: BSD-3-Clause */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <dlfcn.h>
#include <linux/netlink.h>
#include <linux/genetlink.h>
#include <netlink/msg.h>
#include <netlink/attr.h>
#ifndef BIT
#define BIT(n) (1UL << (n))
#endif
#ifdef SCAN_USE_QCA_HEADER
#include "nl80211_copy.h"
#else
#include <linux/nl80211.h>
#endif

__attribute__((constructor)) static void codec_active(void)
{
	fputs("SCAN_SSID_INTERCEPT_ACTIVE\n", stderr);
}

int nl_send_auto_complete(struct nl_sock *sock, struct nl_msg *msg)
{
	struct nlmsghdr *h = nlmsg_hdr(msg);
	struct genlmsghdr *g = (void *)NLMSG_DATA(h);
	struct nlattr *a, *ssid;
	int rem, nested_rem, roots = 0, count = 0, i;

	if (h->nlmsg_type != GENL_ID_CTRL &&
	    g->cmd == NL80211_CMD_TRIGGER_SCAN) {
		fputs("{\"transmitted\":false,\"ssids\":[", stdout);
		nla_for_each_attr(a, (struct nlattr *)((char *)g + GENL_HDRLEN),
				h->nlmsg_len - NLMSG_HDRLEN - GENL_HDRLEN, rem) {
			if (nla_type(a) != NL80211_ATTR_SCAN_SSIDS)
				continue;
			roots++;
			nla_for_each_nested(ssid, a, nested_rem) {
				unsigned char *bytes = nla_data(ssid);
				printf("%s{\"bytes\":%d,\"hex\":\"",
				       count++ ? "," : "", nla_len(ssid));
				for (i = 0; i < nla_len(ssid); i++)
					printf("%02x", bytes[i]);
				fputs("\"}", stdout);
			}
		}
		printf("],\"root_count\":%d}\n", roots);
		fflush(stdout);
		_Exit(0);
	}

	static int (*real_send)(struct nl_sock *, struct nl_msg *);
	if (!real_send)
		real_send = dlsym(RTLD_NEXT, "nl_send_auto_complete");
	return real_send(sock, msg);
}
