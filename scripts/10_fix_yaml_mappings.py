import os

import yaml

client_path = os.path.join('config', 'legacy_mapping', 'client.yaml')
server_path = os.path.join('config', 'legacy_mapping', 'server.yaml')

# Read client yaml
with open(client_path, 'r', encoding='utf-8') as f:
    client_data = yaml.safe_load(f)

# Update client.yaml entries with auto_full
for entry in client_data.get('entries', []):
    key = entry.get('source_key', '')
    if 'Event, Ctrl Manager 이벤트 교환 횟수 최소화' in key:
        entry['automation_mode'] = 'auto_full'
        entry['rule_ids'] = ['CTL_PRF_002']
        entry['checker_type'] = 'builtin'
        entry['checker_key'] = 'ctl.batch_dp_ops'
    elif 'DP 함수 예외 처리' in key:
        entry['automation_mode'] = 'auto_full'
        entry['rule_ids'] = ['CTL_ERR_001']
        entry['checker_type'] = 'builtin'
        entry['checker_key'] = 'ctl.dp_error_handling'
    elif 'Try, Catch 예외처리' in key:
        entry['automation_mode'] = 'auto_full'
        entry['rule_ids'] = ['CTL_ERR_002']
        entry['checker_type'] = 'builtin'
        entry['checker_key'] = 'ctl.try_catch'
    elif '하드코딩 지양' in key:
        entry['automation_mode'] = 'auto_full'
        entry['rule_ids'] = ['CTL_STYLE_001']
        entry['checker_type'] = 'builtin'
        entry['checker_key'] = 'ctl.hardcoding'
    elif '메모리 누수 체크' in key:
        entry['automation_mode'] = 'auto_full'
        entry['rule_ids'] = ['CTL_RES_001']
        entry['checker_type'] = 'builtin'
        entry['checker_key'] = 'ctl.dp_connect_pair'

with open(client_path, 'w', encoding='utf-8') as f:
    yaml.dump(client_data, f, allow_unicode=True, sort_keys=False)

# Read server yaml
with open(server_path, 'r', encoding='utf-8') as f:
    server_data = yaml.safe_load(f)

# Update server.yaml entries
for entry in server_data.get('entries', []):
    key = entry.get('source_key', '')
    if 'Loop문 내에 처리 조건' in key:
        entry['automation_mode'] = 'auto_full'
        entry['rule_ids'] = ['CTL_PRF_001']
        entry['checker_type'] = 'builtin'
        entry['checker_key'] = 'ctl.loop_delay'
    elif 'Event, Ctrl Manager 이벤트 교환 횟수 최소화' in key:
        entry['automation_mode'] = 'auto_full'
        entry['rule_ids'] = ['CTL_PRF_002']
        entry['checker_type'] = 'builtin'
        entry['checker_key'] = 'ctl.batch_dp_ops'
    elif 'DB Query 작성 기준|바인딩 쿼리 처리' in key:
        entry['automation_mode'] = 'auto_full'
        entry['rule_ids'] = ['CTL_DB_001']
        entry['checker_type'] = 'builtin'
        entry['checker_key'] = 'ctl.db_query_binding'
    elif 'DP 함수 예외 처리' in key:
        entry['automation_mode'] = 'auto_full'
        entry['rule_ids'] = ['CTL_ERR_001']
        entry['checker_type'] = 'builtin'
        entry['checker_key'] = 'ctl.dp_error_handling'
    elif 'Try, Catch 예외처리' in key:
        entry['automation_mode'] = 'auto_full'
        entry['rule_ids'] = ['CTL_ERR_002']
        entry['checker_type'] = 'builtin'
        entry['checker_key'] = 'ctl.try_catch'
    elif '하드코딩 지양' in key:
        entry['automation_mode'] = 'auto_full'
        entry['rule_ids'] = ['CTL_STYLE_001']
        entry['checker_type'] = 'builtin'
        entry['checker_key'] = 'ctl.hardcoding'

with open(server_path, 'w', encoding='utf-8') as f:
    yaml.dump(server_data, f, allow_unicode=True, sort_keys=False)

print("Updated legacy mapping YAML with auto_full mode successfully.")
