from prometheus_client import Counter

NOTIFICATIONS = Counter(
    "notifications_sent_total",
    "Notifications processed by notification service",
    ["outcome"],  # success | failed | parse_error
)
