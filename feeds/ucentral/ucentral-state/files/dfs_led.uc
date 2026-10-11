// Output only the current detector result; no radio/configuration changes.
REQUIRE_SEARCH_PATH = [ '/usr/share/ucentral/*.uc', ...REQUIRE_SEARCH_PATH ];
let cursor = require('uci').cursor();
cursor.load('wireless');
let bus = require('ubus').connect();
let pending = require('dfs_cac').collect(cursor.get_all('wireless') || {}, bus.call('network.wireless', 'status'));
print(sprintf('%J\n', { sampled: time(), pending: length(keys(pending?.radios || {})) > 0 }));
