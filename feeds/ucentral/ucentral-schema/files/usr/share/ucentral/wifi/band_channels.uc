// Pure operating-band views. Capability arrays belong to the physical PHY;
// never mutate them while rendering a switchable PHY for multiple bands.
export function base_band(band) {
	return band in ['5G-lower', '5G-upper'] ? '5G' : band;
};

export function frequency_channel(freq, band) {
	if (band == '2G') {
		if (freq == 2484) return 14;
		if (freq >= 2412 && freq <= 2472 && (freq - 2407) % 5 == 0)
			return (freq - 2407) / 5;
	}
	if (base_band(band) == '5G') {
		if (band == '5G-lower' && !(freq >= 5160 && freq <= 5340)) return null;
		if (band == '5G-upper' && !(freq >= 5480 && freq <= 5885)) return null;
		if (freq >= 5160 && freq <= 5885 && freq % 5 == 0) return (freq - 5000) / 5;
		if (freq >= 4910 && freq <= 4980 && freq % 5 == 0) return (freq - 4000) / 5;
	}
	if (band == '6G' && freq >= 5955 && freq <= 7115 &&
	    (freq - 5955) % 20 == 0) return (freq - 5950) / 5;
	return null;
};

export function select_band(phy, band) {
	let base = base_band(band);
	if (!(base in (phy.band || []))) return null;
	if (!(base in ['2G','5G','6G'])) return { ...phy };
	let frequencies = [], channels = [];
	if (length(phy.frequencies)) {
		for (let freq in phy.frequencies) {
			let ch = frequency_channel(freq, band);
			if (ch == null || !(ch in (phy.channels || []))) continue;
			push(frequencies, freq);
			push(channels, ch);
		}
	} else {
		// Channel numbers overlap across bands. Without paired frequencies,
		// a multi-band capability list cannot establish a safe band view.
		if (length(phy.band) != 1) return null;
		channels = filter(phy.channels || [], ch => base != '6G' ||
			(ch >= 1 && ch <= 233 && (ch - 1) % 4 == 0));
		if (band == '5G-lower') channels = filter(channels, ch => ch >= 32 && ch <= 68);
		if (band == '5G-upper') channels = filter(channels, ch => ch >= 96 && ch <= 177);
	}
	channels = uniq(sort(channels, (a,b) => a-b));
	if (!length(channels)) return null;
	return { ...phy, hardware_band: [...phy.band], band: [base],
		frequencies: uniq(sort(frequencies, (a,b) => a-b)), channels,
		dfs_channels: base == '6G' ? [] :
			filter(phy.dfs_channels || [], ch => ch in channels) };
};

export function reserve_switchable(phys, band, radios) {
	// One physical radio cannot operate in 5 and 6 GHz simultaneously.
	// An explicitly enabled 6G request owns a switchable PHY; dedicated
	// 5G PHYs remain usable. Disabled 6G does not reserve hardware.
	let enabled6 = length(filter(radios || [], r => r.band == '6G' && r.enable != false));
	let enabled5 = length(filter(radios || [], r => base_band(r.band) == '5G' && r.enable != false));
	if (base_band(band) == '5G' && enabled6)
		return filter(phys, phy => !('6G' in (phy.hardware_band || phy.band || [])));
	// Do not let a later disabled6G section disable a PHY already allocated
	// to enabled5G. A lone disabled6G section still explicitly disables it.
	if (band == '6G' && !enabled6 && enabled5)
		return filter(phys, phy => !('5G' in (phy.hardware_band || phy.band || [])));
	return phys;
};

export function primary_6g_allowed(channel, width, channels) {
	if (!(width in [20,40,80,160,320]) || channel < 1 || channel > 233 ||
	    (channel - 1) % 4 != 0 || !(channel in channels)) return false;
	let count = width / 20, starts = [];
	if (width == 320) {
		// 320MHz operating classes have overlapping 160MHz-offset blocks.
		for (let start = 1; start + 4 * (count - 1) <= 233; start += 32)
			if (channel >= start && channel <= start + 4 * (count - 1)) push(starts,start);
	} else {
		push(starts, 1 + int((channel - 1) / (4 * count)) * 4 * count);
	}
	for (let start in starts) {
		let allowed = true;
		for (let n = 0; n < count; n++)
			if (!(start + 4 * n in channels) || start + 4 * n > 233) allowed = false;
		if (allowed) return true;
	}
	// Primary eligibility is necessary, not a width authorization. The
	// normal hostapd/kernel regulatory and hardware checks still apply.
	return false;
};
