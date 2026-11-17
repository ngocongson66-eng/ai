import server, json

# 1. Check if server HTML has any undefined variables or missing functions
html = server.HTML_PAGE

# 2. Test batch process with empty, 1 item, and sample items
cases = [
    [],
    [{"id": "REQ-1001", "customer_name": "Test", "raw_request_text": "Cần mua 10 laptop"}],
    server.INITIAL_SAMPLE_DATA
]

for idx, c in enumerate(cases):
    dossiers, summary = server.agent.process_batch(c)
    print(f"Case {idx}: {len(dossiers)} dossiers, summary: {summary.get('total_value_formatted')}")
