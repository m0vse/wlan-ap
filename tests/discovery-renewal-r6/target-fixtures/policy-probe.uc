import { select_controller } from '/usr/share/ucentral/discovery_policy.uc';
assert(select_controller(null, 'fixture.invalid:15002', null)?.dhcp_port == 15002);
