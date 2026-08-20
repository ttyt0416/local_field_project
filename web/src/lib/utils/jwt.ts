export type JwtPayload = {
	exp?: number;
	[key: string]: unknown;
};

function decodeBase64Url(value: string) {
	if (typeof atob !== 'function') return null;
	const base64 = value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (value.length % 4)) % 4);
	const bytes = Uint8Array.from(atob(base64), (character) => character.charCodeAt(0));
	return new TextDecoder().decode(bytes);
}

export function decodeJwtPayload(token: string): JwtPayload | null {
	const payloadPart = token.split('.')[1];
	if (!payloadPart) return null;
	try {
		const payload = JSON.parse(decodeBase64Url(payloadPart) ?? 'null');
		return typeof payload === 'object' && payload !== null && !Array.isArray(payload) ? (payload as JwtPayload) : null;
	} catch {
		return null;
	}
}

export function isJwtExpired(token: string, nowSeconds = Math.floor(Date.now() / 1000)) {
	const payload = decodeJwtPayload(token);
	return typeof payload?.exp !== 'number' || payload.exp <= nowSeconds;
}

export function isJwtUsable(token: string | null) {
	return Boolean(token && !isJwtExpired(token));
}
