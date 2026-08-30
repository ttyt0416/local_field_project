import { redirect, type Handle } from '@sveltejs/kit';

export const handle: Handle = async ({ event, resolve }) => {
	const forwardedProto = event.request.headers.get('x-forwarded-proto')?.split(',')[0].trim().toLowerCase();
	const cloudflareProto = event.request.headers.get('cf-visitor')?.match(/"scheme"\s*:\s*"([^"]+)"/)?.[1]?.toLowerCase();
	if ((forwardedProto ?? cloudflareProto) === 'http') {
		const url = new URL(event.request.url);
		const forwardedHost = event.request.headers.get('x-forwarded-host')?.split(',')[0].trim();
		const host = forwardedHost || event.request.headers.get('host');
		url.protocol = 'https:';
		if (host) url.host = host;
		throw redirect(308, url.toString());
	}
	return resolve(event);
};
