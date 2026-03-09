import requests
# Try hdbsql with userstore key SYSTEM
r = requests.post(
    'http://10.238.36.146:9999/execute',
    json={
        'command': 'su - zo3adm -c "hdbsql -U SYSTEM -d ZO3 \\"SELECT DATABASE_NAME, ACTIVE_STATUS FROM M_DATABASES\\""',
        'timeout': 15,
        'admin_override': True
    },
    headers={'X-API-Key': 'REMOTE_EXEC_KEY_REVOKED_PLACEHOLDER_0000000000000000'},
    timeout=20
)
d = r.json()
print('STDOUT:', d.get('stdout', '') or d.get('output', ''))
print('STDERR:', d.get('stderr', ''))
print('RC:', d.get('return_code', d.get('exit_code', '?')))
