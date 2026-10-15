#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <dlfcn.h>
#include <linux/netlink.h>
#include <linux/genetlink.h>
#include <netlink/msg.h>
#include <netlink/attr.h>
/* Use precisely the nl80211_copy.h used by the selected native codec. */
#ifndef BIT
#define BIT(n) (1UL << (n))
#endif
#include "nl80211_copy.h"
#define TEST_LINK_ATTR NL80211_ATTR_MLO_LINK_ID
__attribute__((constructor)) static void codec_active(void) { fputs("RRM_CODEC_INTERCEPT_ACTIVE\n",stderr); }
int nl_send_auto_complete(struct nl_sock *sock, struct nl_msg *msg) {
 struct nlmsghdr *h=nlmsg_hdr(msg);
 struct genlmsghdr *g=(void *)NLMSG_DATA(h);
 if(h->nlmsg_type!=GENL_ID_CTRL && g->cmd==NL80211_CMD_SET_WIPHY) {
  struct nlattr *a; int rem,found=0,id=-1,bytes=0;
  nla_for_each_attr(a,(void *)((char *)g+GENL_HDRLEN),h->nlmsg_len-NLMSG_HDRLEN-GENL_HDRLEN,rem) {
   if(nla_type(a)==TEST_LINK_ATTR) {found++;bytes=nla_len(a);id=bytes==1?*(uint8_t *)nla_data(a):-1;}
  }
  printf("{\"command\":%u,\"root_attr\":%d,\"count\":%d,\"bytes\":%d,\"value\":%d,\"ack\":%s,\"transmitted\":false}\n",g->cmd,TEST_LINK_ATTR,found,bytes,id,(h->nlmsg_flags & NLM_F_ACK)?"true":"false");fflush(stdout);_Exit(0);
 }
 static int(*real)(struct nl_sock*,struct nl_msg*);
 if(!real)real=dlsym(RTLD_NEXT,"nl_send_auto_complete");
 return real(sock,msg);
}
