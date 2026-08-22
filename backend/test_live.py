import httpx
import json

client = httpx.Client(timeout=90.0)

# 1. Create or get CAA entity
r = client.post('http://127.0.0.1:8008/api/entities', json={'name': 'Citizenship Amendment Act', 'entity_type': 'government_scheme'})
entity = r.json()
print('Entity:', entity)

# 2. Trigger investigate
print('Triggering investigation...')
r_inv = client.post(f"http://127.0.0.1:8008/api/entities/{entity['id']}/investigate")
print('Investigate status:', r_inv.status_code)
if r_inv.status_code == 200:
    data = r_inv.json()
    print('Investigate success!')
    print('Documents analyzed:', data.get('documents_analyzed'))
    print('Comparisons count:', len(data.get('comparisons', [])))
    if data.get('comparisons'):
        print('First comparison:', json.dumps(data['comparisons'][0], indent=2))
else:
    print('Error detail:', r_inv.text)
