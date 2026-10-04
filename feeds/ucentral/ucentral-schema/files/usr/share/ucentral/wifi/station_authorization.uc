// ucode nl80211 exposes STA_FLAGS as [mask, set]. The stable Linux UAPI
// NL80211_STA_FLAG_AUTHORIZED is enum value 1, hence bit 1 << 1.
export function station_authorized(flags) {
	if (type(flags) != 'array' || length(flags) != 2 ||
	    type(flags[0]) != 'int' || type(flags[1]) != 'int' ||
	    flags[0] < 0 || flags[1] < 0 || !(flags[0] & 2))
		return null;
	return !!(flags[1] & 2);
};
