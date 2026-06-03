DEFAULT_INVESTIGATIONS = 10
DEFAULT_QUESTIONS = 10
DEFAULT_QUERIES = 10
DEFAULT_QUERIES_ABLATION = 50 # anymore and agent hits the recursion limit
DEFAULT_INVESTIGATION_MIN = 7 # at least 7 investigations
DEFAULT_MAX_TOKENS = 2048

# Error loop guards — caps malformed <tool_call> XML retries before giving up
DEFAULT_MAX_ERRORS = 10          # investigator agent: max bad-format responses
DEFAULT_CHIEF_MAX_ERRORS = 8     # chief inspector: max bad-format responses

# IP POI budget boost — IP-based investigations need more depth to trace
# multi-hop chains (IP → process → domain). Targets the observed recall gap.
IP_MAX_INVESTIGATIONS = 15
IP_MAX_QUESTIONS = 12
IP_MAX_QUERIES = 12

# Safety-net timeout per individual scenario (seconds).
# 12 hours — only fires if a genuine infinite loop survives the error_count guards.
# This is a dead-man switch, NOT a performance target.
DEFAULT_SCENARIO_TIMEOUT = 43200  # 12 hours