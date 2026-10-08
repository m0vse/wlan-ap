let shared = require('deferred_settings');
let create = shared.create, status = shared.status, country = shared.country, DEFERRED_EXIT = shared.DEFERRED_EXIT;
let passed = [];
function copy(v) { return json(sprintf('%J', v)); }
function fixture() {
	let context = {board:'cambiumnetworks,xv3-8',serial:'001122334455',bank:1,
		spki:'same-key',job:null,installer_pending:true,boot_id:'boot-one',identity_accepted:true,
		country_codes:['US','GB','DE'],active_country:'US'};
	let state = {context, record:null, effects:[],baseline:'before', fail:null,
		readback:false, topology:false};
	let io = {
		context: () => copy(state.context),
		probe: () => state.topology ? [{setting:'topology',active:'dual-4x4',desired:'single-8x8'}] : [],
		validate_country: function(wanted) { assert(state.fail != 'regional', 'Regional file missing'); },
		load: () => copy(state.record),
		save: function(record) { assert(state.fail != 'save', 'Write failure'); state.record=copy(record); },
		baseline: () => ({defaults:state.baseline}),
		check_baseline: function(old) { assert(old.defaults==state.baseline,'Concurrent edit'); },
		commit: function(record) {
			push(state.effects,'boot-only');
			assert(state.fail != 'commit','Partial commit');
		},
		readback: () => state.readback
	};
	return {state, service:create(io), restart: () => create(io)};
}
function request(extra) { return {country:'GB',uuid:1234,id:9,...(extra || {})}; }
function check(name, callback) { callback();push(passed,name); }
function refuses(callback) { let failed=false;try {callback();} catch(e) {failed=true;} assert(failed,'Expected refusal'); }

check('exact-correlated-status-and-no-live-effects',function() {
	let f=fixture(),r=f.service.prepare(request());
	let s=status(r);assert(r.uuid==1234&&r.id==9&&s.error==0&&s.text=='Reboot required'&&s.reboot_required===true&&s.applied===false);
	assert(!length(f.state.effects)&&f.state.record.phase=='accepted'&&DEFERRED_EXIT==75);
});
check('same-country-no-false-reboot',function(){let f=fixture();assert(f.service.prepare(request({country:'US'}))==null&&!f.state.record);});
check('invalid-country-no-write',function(){let f=fixture();refuses(()=>f.service.prepare(request({country:'gB'})));assert(!f.state.record);});
check('unauthorized-country-no-write',function(){let f=fixture();refuses(()=>f.service.prepare(request({country:'FR'})));assert(!f.state.record);});
check('non-ISO-code-not-admitted-by-bad-hardware-list',function(){let f=fixture();push(f.state.context.country_codes,'ZZ');refuses(()=>f.service.prepare(request({country:'ZZ'})));assert(!f.state.record);});
check('deployment-country-restriction',function(){let f=fixture();f.state.context.restricted_countries=['US'];refuses(()=>f.service.prepare(request()));});
check('missing-regional-file-no-write',function(){let f=fixture();f.state.fail='regional';refuses(()=>f.service.prepare(request()));assert(!f.state.record);});
check('conflicting-radio-country',function(){refuses(()=>country({radios:[{country:'GB'},{country:'US'}]}));});
check('country00-does-not-select-policy',function(){assert(country({radios:[{country:'00'},{country:'GB'}]})=='GB');});
check('partial-journal-failure-no-live-effects',function(){let f=fixture();f.state.fail='save';refuses(()=>f.service.prepare(request()));assert(!f.state.record&&!length(f.state.effects));});
check('retry-correlates-current-id-preserves-journal-boot-and-deadline',function(){let f=fixture();let r=f.service.prepare(request());let again=f.service.prepare(request({id:10}));assert(again.id==10&&f.state.record.id==r.id&&again.accepted_boot=='boot-one'&&!length(f.state.effects));});
check('different-pending-uuid-refused',function(){let f=fixture();f.service.prepare(request());refuses(()=>f.service.prepare(request({uuid:2222})));assert(f.state.record.uuid==1234);});
check('same-boot-cannot-commit',function(){let f=fixture();f.service.prepare(request());refuses(()=>f.service.boot());assert(!length(f.state.effects));});
check('identity-bank-mismatch-refused',function(){let f=fixture();f.service.prepare(request());f.state.context.boot_id='boot-two';f.state.context.bank=0;refuses(()=>f.service.boot());assert(!length(f.state.effects));});
check('qualified-managed-bank-transition-preserves-pending',function(){let f=fixture();f.service.prepare(request());f.state.context.boot_id='boot-two';f.state.context.bank=0;f.state.context.layout='banks';f.state.context.ab_state='trial-started';f.state.context.confirmed=1;f.state.context.target=0;let r=f.service.boot();assert(r.phase=='boot-staged'&&r.bank_transition.source==1&&r.binding.bank==0);});
check('first-enrollment-pending-never-rebound-by-bank-transition',function(){let f=fixture();f.state.context.identity_accepted=false;f.state.context.job='same-job';f.service.prepare(request());f.state.context.boot_id='boot-two';f.state.context.bank=0;f.state.context.layout='banks';f.state.context.ab_state='trial-started';f.state.context.confirmed=1;f.state.context.target=0;refuses(()=>f.service.boot());assert(!length(f.state.effects));});
check('country-baseline-edit-preserved',function(){let f=fixture();f.service.prepare(request());f.state.context.boot_id='boot-two';f.state.baseline='operator-edit';refuses(()=>f.service.boot());assert(!length(f.state.effects));});
check('country-restriction-rechecked-before-boot-commit',function(){let f=fixture();f.service.prepare(request());f.state.context.boot_id='boot-two';f.state.context.restricted_countries=['US'];refuses(()=>f.service.boot());assert(!length(f.state.effects));});
check('restart-replays-partial-commit',function(){let f=fixture();f.service.prepare(request());f.state.context.boot_id='boot-two';f.state.fail='commit';refuses(()=>f.service.boot());assert(f.state.record.phase=='committing');f.state.fail=null;assert(f.restart().boot().phase=='boot-staged');});
check('hardware-readback-required',function(){let f=fixture();f.service.prepare(request());f.state.context.boot_id='boot-two';f.service.boot();refuses(()=>f.service.confirm());assert(f.state.record.phase=='boot-staged');f.state.readback=true;assert(f.service.confirm().phase=='active'&&f.service.state().reboot_required===false);});
check('accepted-is-not-applied-on-same-boot',function(){let f=fixture();f.service.prepare(request());f.state.readback=true;refuses(()=>f.service.confirm());assert(f.state.record.phase=='accepted');});
check('first-enrollment-pending-outside-store',function(){let f=fixture();f.state.context.identity_accepted=false;f.state.context.job='same-job';f.service.prepare(request());f.state.context.boot_id='boot-two';assert(f.service.boot().phase=='accepted'&&!length(f.state.effects)&&f.service.state().blocked_enrollment);});
check('empty-unenrolled-store-no-job-refused',function(){let f=fixture();f.state.context.identity_accepted=false;f.state.context.spki=null;refuses(()=>f.service.prepare(request()));assert(!f.state.record);});
check('same-native-job-completes-original-key-binding',function(){let f=fixture();f.state.context.identity_accepted=false;f.state.context.job='same-job';f.state.context.spki=null;f.service.prepare(request());f.state.context.boot_id='boot-two';f.state.context.identity_accepted=true;f.state.context.spki='original-native-key';assert(f.service.boot().binding.spki=='original-native-key');});
check('same-job-original-key-arrival-can-cancel-without-acceptance',function(){let f=fixture();f.state.context.identity_accepted=false;f.state.context.job='same-job';f.state.context.spki=null;f.service.prepare(request());f.state.context.spki='original-native-key';assert(f.service.prepare(request({country:'US',uuid:2222}))==null&&f.state.record.phase=='cancelled'&&!length(f.state.effects));});
check('renewed-leaf-does-not-change-key-binding',function(){let f=fixture();f.service.prepare(request());f.state.context.boot_id='boot-two';f.state.context.leaf='renewed-leaf';assert(f.service.boot().phase=='boot-staged');});
check('validated-current-settings-cancel-uncommitted-pending',function(){let f=fixture();f.service.prepare(request());assert(f.service.prepare(request({country:'US',uuid:2222}))==null&&f.state.record.phase=='cancelled'&&!f.service.state().reboot_required);});
check('committing-pending-cannot-be-superseded',function(){let f=fixture();f.service.prepare(request());f.state.context.boot_id='boot-two';f.state.fail='commit';refuses(()=>f.service.boot());refuses(()=>f.service.prepare(request({country:'US',uuid:2222})));});
check('thor-topology-uses-same-deferred-lifecycle',function(){let f=fixture();f.state.topology=true;let r=f.service.prepare({uuid:1234,id:9,document:{uuid:1234,radios:[]},source:'/etc/ucentral/ucentral.cfg.0000001234'});assert(r.changes[0].setting=='topology'&&status(r).reboot_required&&!length(f.state.effects));f.state.context.boot_id='boot-two';assert(f.service.boot().phase=='boot-staged');});

print(sprintf('%J\n',{passed:true,count:length(passed),cases:passed}));
