/* SPDX-License-Identifier: BSD-3-Clause */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>
#include <linux/netlink.h>
#include <linux/genetlink.h>
#include <netlink/msg.h>
#include <netlink/attr.h>
#include <netlink/handlers.h>
#include <netlink/genl/genl.h>
#ifdef SCAN_USE_QCA_HEADER
#ifndef BIT
#define BIT(n) (1UL << (n))
#endif
#include "nl80211_copy.h"
#else
#include <linux/nl80211.h>
#endif

struct callbacks {
	struct nl_cb *cb;
	nl_recvmsg_msg_cb_t valid, finish;
	void *valid_arg, *finish_arg;
};
static struct callbacks callbacks[16];
static int pending, family;

__attribute__((constructor)) static void decode_active(void)
{
	fputs("SCAN_SSID_DECODE_INTERCEPT_ACTIVE\n", stderr);
}

int nl_cb_set(struct nl_cb *cb, enum nl_cb_type type, enum nl_cb_kind kind,
	      nl_recvmsg_msg_cb_t fn, void *arg)
{
	static int (*real_set)(struct nl_cb *, enum nl_cb_type,
			     enum nl_cb_kind, nl_recvmsg_msg_cb_t, void *);
	int i;
	for (i = 0; i < 16; i++) {
		if (callbacks[i].cb && callbacks[i].cb != cb)
			continue;
		callbacks[i].cb = cb;
		if (type == NL_CB_VALID) {
			callbacks[i].valid = fn;
			callbacks[i].valid_arg = arg;
		}
		if (type == NL_CB_FINISH) {
			callbacks[i].finish = fn;
			callbacks[i].finish_arg = arg;
		}
		break;
	}
	if (!real_set)
		real_set = dlsym(RTLD_NEXT, "nl_cb_set");
	return real_set(cb, type, kind, fn, arg);
}

int nl_send_auto_complete(struct nl_sock *sock, struct nl_msg *msg)
{
	static int (*real_send)(struct nl_sock *, struct nl_msg *);
	struct nlmsghdr *h = nlmsg_hdr(msg);
	struct genlmsghdr *g = (void *)NLMSG_DATA(h);
	if (h->nlmsg_type != GENL_ID_CTRL && g->cmd == NL80211_CMD_GET_INTERFACE) {
		pending = 1;
		family = h->nlmsg_type;
		fputs("GET_INTERFACE_BLOCKED_SYNTHETIC_REPLY\n", stderr);
		return h->nlmsg_len;
	}
	if (!real_send)
		real_send = dlsym(RTLD_NEXT, "nl_send_auto_complete");
	return real_send(sock, msg);
}

int nl_recvmsgs(struct nl_sock *sock, struct nl_cb *cb)
{
	static int (*real_recv)(struct nl_sock *, struct nl_cb *);
	const char binary[] = { 'a', 0, 'b' };
	const char *mode = getenv("SCAN_DECODE_CASE");
	struct nl_msg *msg;
	struct nlattr *nest;
	int i;
	if (!pending) {
		if (!real_recv)
			real_recv = dlsym(RTLD_NEXT, "nl_recvmsgs");
		return real_recv(sock, cb);
	}
	for (i = 0; i < 16 && callbacks[i].cb != cb; i++) {}
	if (i == 16 || !callbacks[i].valid || !callbacks[i].finish)
		_Exit(93);
	pending = 0;
	msg = nlmsg_alloc();
	if (!msg)
		_Exit(94);
	genlmsg_put(msg, 0, 0, family, 0, NLM_F_MULTI,
		    NL80211_CMD_NEW_INTERFACE, 0);
	nest = nla_nest_start(msg, NL80211_ATTR_SCAN_SSIDS);
	nla_put(msg, 0, 0, "");
	nla_put(msg, 1, 3, "abc");
	nla_put(msg, 2, sizeof(binary), binary);
	nla_nest_end(msg, nest);
	if (mode && !strcmp(mode, "empty")) {
		nla_put(msg, NL80211_ATTR_SSID, 0, "");
		nla_put(msg, NL80211_ATTR_FRAME_MATCH, 0, "");
		nla_put(msg, NL80211_ATTR_IFNAME, 0, "");
	} else {
		nla_put(msg, NL80211_ATTR_SSID, sizeof(binary), binary);
		nla_put(msg, NL80211_ATTR_FRAME_MATCH, sizeof(binary), binary);
		nla_put_string(msg, NL80211_ATTR_IFNAME, "wlan-test");
	}
	callbacks[i].valid(msg, callbacks[i].valid_arg);
	callbacks[i].finish(msg, callbacks[i].finish_arg);
	nlmsg_free(msg);
	return 0;
}
