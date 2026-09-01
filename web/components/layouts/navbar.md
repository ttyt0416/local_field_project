# Navbar

The authenticated desktop navbar polls Local Field `GET /hardware/metrics` immediately after authentication and every 5 seconds. It shows compact CPU, GPU, RAM, and DISK whole percentages. Browser code never calls the independent hardware-monitor directly, so the monitor remains outside public browser/CORS access; Local Field server authenticates the user and proxies the internal request. On the first consecutive poll failure, the navbar hides stale values and shows one safe negative Toast; it suppresses repeated Toasts until a successful poll resets the failure state.
