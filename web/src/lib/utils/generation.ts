const kstDateFormatter = new Intl.DateTimeFormat('en-CA', {
	timeZone: 'Asia/Seoul',
	year: 'numeric',
	month: '2-digit',
	day: '2-digit',
	hour: '2-digit',
	minute: '2-digit',
	second: '2-digit',
	hour12: false
});

export function formatElapsedSeconds(totalSeconds: number) {
	const seconds = Math.max(0, Math.floor(Number.isFinite(totalSeconds) ? totalSeconds : 0));
	return `${Math.floor(seconds / 60)}분 ${String(seconds % 60).padStart(2, '0')}초`;
}

export function formatFileSize(bytes: number | null | undefined) {
	if (!Number.isFinite(bytes) || !bytes || bytes < 0) return '정보 없음';
	const units = ['B', 'KB', 'MB', 'GB'];
	const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
	return `${(bytes / 1024 ** exponent).toFixed(exponent === 0 ? 0 : 1)} ${units[exponent]}`;
}

export function formatKstDateTime(value: string | number) {
	const parts = Object.fromEntries(kstDateFormatter.formatToParts(new Date(value)).map(({ type, value: part }) => [type, part]));
	return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second} KST`;
}
