import requests
r = requests.post(
    'http://10.238.36.146:9999/execute',
    json={'command': 'su - zo3adm -c "HDB start"', 'timeout': 120, 'admin_override': True},
    headers={'X-API-Key': 'REMOTE_EXEC_KEY_REVOKED_PLACEHOLDER_0000000000000000'},
    timeout=130
)
d = r.json()
print(d.get('stdout', '') or d.get('output', ''))
print('STDERR:', d.get('stderr', ''))
