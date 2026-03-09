import requests
# Try connecting to HANA from the remote server itself (localhost)
r = requests.post(
    'http://10.238.36.146:9999/execute',
    json={
        'command': 'su - zo3adm -c "hdbsql -i 02 -u SYSTEM -p HANA_PASSWORD_REVOKED_PLACEHOLDER_00000000000000000000 -d ZO3 \\"SELECT DATABASE_NAME, ACTIVE_STATUS FROM M_DATABASES\\""',
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
