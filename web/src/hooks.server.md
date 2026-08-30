# HTTPS redirect hook

`handle` checks the proxy protocol headers provided by Cloudflare Tunnel. Public requests received as HTTP are redirected with status `308` to the same HTTPS host, path, and query string. Direct local requests without those proxy headers keep their existing behavior so Docker health checks can continue using localhost HTTP.
