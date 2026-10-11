// Current critical faults only. All state is private and volatile; no remediation.
import * as fs from 'fs';

function evaluate(facts, previous, now) {
 if (facts == null) return { ...previous, updated: now, active: previous?.active || [],
  monitoring: { storage: 'unavailable', reason: 'probe_failed' } };
 let next = { updated: now, active: [], counters: {}, ecc: {}, monitoring: {
  radio: facts?.radio_monitoring || 'unavailable', radio_reason: facts?.radio_reason || null,
  adapter: facts?.adapter || { status: 'unavailable' },
  storage: facts != null ? 'available' : 'unavailable', feature_registers: 'not_available_in_this_kernel', canary: facts?.canary || []
 } };

 function candidate(code, resource, detail, immediate) {
  let key = code + ':' + resource;
  let old = previous?.counters?.[key];
  let count = min((old?.count || 0) + 1, 3);
  next.counters[key] = { count, detail };
  if (immediate || count >= 2) push(next.active, { code, resource, severity: 'critical', ...detail });
 }
 for (let m in facts?.mtd || []) {
  let id = '' + m.index, old = previous?.ecc?.[id];
  let since = old?.since || 0;
  if ((old == null && m.ecc_failures > 0) || (old != null && m.ecc_failures > old.value)) since = now;
  next.ecc[id] = { value: m.ecc_failures, since };
  if (since && now - since < 600)
   candidate('storage_uncorrectable_ecc', 'mtd' + id, { last_seen: since }, true);
 }
 for (let mount in facts?.mounts || []) {
  if (mount.readonly) candidate('storage_readonly', mount.path, {}, false);
  if (mount.total_inodes > 0 && mount.available_inodes != null && mount.available_inodes < 16)
   candidate('storage_inode_exhausted', mount.path, { available_inodes: mount.available_inodes }, false);
  if (mount.total_bytes > 0 && mount.available_bytes < min(1048576, mount.total_bytes / 100))
   candidate('storage_exhausted', mount.path, { available_bytes: mount.available_bytes }, false);
 }
 for (let bank in facts?.canary || []) {
  if (bank.status != 'checked') continue;
  for (let sample in bank.samples || []) {
   if (sample.bad || sample.ok) continue;
   candidate('storage_canary', 'mtd' + bank.mtd + '/PEB' + sample.peb,
    { reason: sample.error ? 'read_error' : 'invalid_ec_header', errno: sample.error || 0 }, false);
  }
 }
 if (facts.memory?.total_kb > 0 && facts.memory.available_kb < min(8192, facts.memory.total_kb / 20))
  candidate('memory_pressure', 'memory', { available_kb: facts.memory.available_kb }, false);
 for (let radio in facts?.radios || [])
  candidate('radio_failure', radio.radio, { reason: radio.reason, driver_crash_observed: facts.driver_crash || false, phy: radio.phy, band: radio.band }, false);
 if (facts.radio_monitoring != 'available') {
  for (let fault in previous?.active || []) {
   if (fault.code == 'radio_failure' && !length(filter(next.active, f => f.code == fault.code && f.resource == fault.resource))) push(next.active, { ...fault, stale: true });
  }
 }
 for (let io in facts?.io || [])
  candidate('storage_io', io.resource, { reason: io.reason }, true);
 return next;
}

function snapshot() {
 let data;
 try { data = json(fs.readfile('/tmp/ucentral-faults/status.json')); } catch(e) {}
 if (type(data) != 'object')
  return { active: [], monitoring: { storage: 'unavailable', reason: 'collector_missing' } };
 if (time() - data.updated > 180 || data.updated > time() + 60)
  return { active: data.active || [], stale: true, monitoring: { storage: 'unavailable', reason: 'collector_stale' } };
 return { updated: data.updated, active: data.active || [], monitoring: data.monitoring || {} };
}

function radio_facts(config, status, cac, kernel_interfaces) {
 let result = [];
 for (let name, radio in config || {}) {
  if (radio?.['.type'] != 'wifi-device' || radio.disabled == '1') continue;
  let expected = [];
  for (let section, iface in config || {}) {
   if (iface?.['.type'] == 'wifi-iface' && iface.device == name && iface.disabled != '1' &&
       (!iface.mode || iface.mode == 'ap') && length(iface.ssid || '')) push(expected, section);
  }
  if (!length(expected)) continue;
  let live = status?.[name];
  if (live?.pending || live?.disabled || cac?.radios?.[name]) continue;
  let reason, phy = radio.phy || null;
  if (!live) reason = 'configured_radio_absent';
  else if (!live.up) reason = 'configured_radio_down';
  else {
   let present = {};
   for (let iface in live.interfaces || []) present[iface.section] = true;
   for (let section in expected) {
    if (cac?.sections?.[section]) continue;
    if (present[section] && kernel_interfaces != null) {
     let iface = filter(live.interfaces || [], i => i.section == section)[0];
     let observed = kernel_interfaces?.[iface?.ifname];
     if (!observed || observed.mode != 'ap' || observed.ssid != config[section].ssid) {
      reason = 'configured_bss_unavailable'; break;
     }
     if (observed.phy != null) phy = observed.phy;
     if (!observed.has_channel) { reason = 'configured_bss_no_channel'; break; }
    }
    if (!present[section] && !cac?.sections?.[section]) { reason = 'configured_bss_unavailable'; break; }
   }
  }
  if (reason) push(result, { radio: name, phy, band: radio.band || null, reason });
 }
 return result;
}

function select_banks(profiles, board, records) {
 let profile = profiles?.[board];
 if (!profile) return { status: 'unsupported', banks: [] };
 let banks = [];
 for (let spec in profile) {
  let found = filter(records || [], row => row.name == spec.name && row.type == 'nand' &&
   row.size == spec.size && row.erase == spec.erase && row.write == spec.write &&
   (row.offset == null || row.offset == spec.offset));
  if (length(found) != 1) return { status: 'unavailable', reason: 'bank_geometry', banks: [] };
  if (spec.name == 'fs' && !found[0].paired_ubi)
   return { status: 'unavailable', reason: 'paired_ubi_unproven', banks: [] };
  if (!match(spec.samples || '', /^[0-9]+(,[0-9]+){0,7}$/))
   return { status: 'unavailable', reason: 'sample_profile', banks: [] };
  push(banks, { index: found[0].index, ...spec });
 }
 return { status: 'qualified', banks };
}

return { evaluate, snapshot, radio_facts, select_banks };
