"""
24_generate_35_real_wincc_samples.py

웹 검색 및 WinCC OA 레퍼런스 구문에 기반한 총 55개 실물 샘플 파일 세트 대량 구축 스크립트
"""

import os

def generate_55_real_samples():
    output_dir = os.path.join("intermediate_results", "real_samples")
    os.makedirs(output_dir, exist_ok=True)

    samples = [
        ("sample_01_dp_connect.ctl", "main() { dpConnect(\"add_cb\", \"A.:_online.._value\", \"B.:_online.._value\"); }\nvoid add_cb(string dp1, int a, string dp2, int b) { dpSet(\"C.:_original.._value\", a+b); }"),
        ("sample_02_dp_query.ctl", "void fetch() { string q = \"SELECT '_online.._value' FROM 'Motor_*'\"; dyn_dyn_anytype tab; int rc = dpQuery(q, tab); if(rc!=0) DebugN(getLastError()); }"),
        ("sample_03_dp_get_period.ctl", "void history(time t1, time t2) { dyn_float v; dyn_time t; dpGetPeriod(t1, t2, 0, \"Pump.:_online.._value\", v, t); }"),
        ("sample_04_file_io.ctl", "void write_log() { int f = fopen(\"C:\\\\log.txt\", \"a\"); if(f>0) { fputs(\"event\\n\", f); fclose(f); } }"),
        ("sample_05_db_query_safe.ctl", "void safe_db() { string s = \"SELECT id FROM users\"; dbExecuteQuery(s); }"),
        ("sample_06_db_query_unsafe.ctl", "void unsafe_db(string input_val) { string s = \"SELECT * FROM users WHERE name='\" + input_val + \"'\"; dbExecuteQuery(s); }"),
        ("sample_07_loop_delay_valid.ctl", "void loop_valid() { while(true) { do_work(); delay(1); } }"),
        ("sample_08_loop_delay_missing.ctl", "void loop_missing() { while(true) { do_work(); } }"),
        ("sample_09_dp_connect_pair_missing.ctl", "void setup() { dpConnect(\"on_change\", \"Sensor.:_online.._value\"); }"),
        ("sample_10_dp_connect_pair_valid.ctl", "void setup_clean() { dpConnect(\"on_change_v\", \"Press.:_online.._value\"); } void cleanup() { dpDisconnect(\"on_change_v\", \"Press.:_online.._value\"); }"),
        ("sample_11_hardcoding_ip.ctl", "void plc_conn() { string ip = \"192.168.1.100\"; DebugN(ip); }"),
        ("sample_12_hardcoding_version_skip.ctl", "void ver() { string v = \"version 1.0.0.0\"; DebugN(v); }"),
        ("sample_13_try_catch_valid.ctl", "void safe_get() { try { anytype val; dpGet(\"S1.:_online.._value\", val); } catch { DebugN(\"err\"); } }"),
        ("sample_14_try_catch_missing.ctl", "void unsafe_get() { anytype val; dpGet(\"S1.:_online.._value\", val); }"),
        ("sample_15_pnl_init_context.pnl", "// ScopeLib:: initialize\nmain() { dpConnect(\"on_init\", \"Status.:_online.._value\"); }"),
        ("sample_16_pnl_add_symbol.pnl", "main() { addSymbol(myModuleName(), myPanelName(), \"faceplate.pnl\", \"V1\", makeDynString(\"$dp:V1\"), 10, 20, 0, 1.0, 1.0); }"),
        ("sample_17_alarm_handling.ctl", "void alarm_cb(string dp, time t, int state) { if(state>1) dpSet(\"Alarm.:_original.._value\", state); }"),
        ("sample_18_dyn_string_ops.ctl", "void dyn_ops() { dyn_string tags = makeDynString(\"T1\", \"T2\"); for(int i=1; i<=dynlen(tags); i++) DebugN(tags[i]); }"),
        ("sample_19_scada_panel_child.pnl", "main() { ChildPanelOnCentral(\"confirm.pnl\", \"Dialog\", makeDynString(\"$msg:Save?\")); }"),
        ("sample_20_xml_config_sample.xml", "<?xml version=\"1.0\" encoding=\"UTF-8\"?><config><dp name=\"M1\"/></config>"),
        ("sample_21_batch_dp_set.ctl", "void batch() { dyn_string d = makeDynString(\"P1\", \"P2\"); dyn_anytype v = makeDynAnytype(1, 2); dpSetWait(d, v); }"),
        ("sample_22_single_dp_set_consecutive.ctl", "void bad_set() { dpSet(\"P1\", 1); dpSet(\"P2\", 2); dpSet(\"P3\", 3); dpSet(\"P4\", 4); }"),
        ("sample_23_uninitialized_var.ctl", "void uninit() { int total; int count = 5; total = total + count; }"),
        ("sample_24_global_var_scope.ctl", "global int g_counter = 0; void inc() { g_counter++; }"),
        ("sample_25_dp_get_period_split.ctl", "void split_fetch(time t1, time t2) { dyn_float v; dyn_time t; dpGetPeriodSplit(t1, t2, 3600, \"Level.:_online.._value\", v, t); }"),
        ("sample_26_redundancy_check.ctl", "void check_red() { if(isRedundantActive()) DebugN(\"Active\"); }"),
        ("sample_27_driver_para.ctl", "void conf_kafka(string topic) { dpSet(\"Kafka.Topic\", topic); }"),
        ("sample_28_panel_on_close.pnl", "main() { dpDisconnect(\"on_change\", \"Temp.:_online.._value\"); }"),
        ("sample_29_format_string.ctl", "void fmt(float v) { string txt = sprintf(\"%.2f bar\", v); }"),
        ("sample_30_bitwise_ops.ctl", "void bit_check(int w) { if((w & 0x01)!=0) DebugN(\"Bit0\"); }"),
        ("sample_31_multi_dp_connect.ctl", "void multi_cb() { dpConnect(\"on_m\", \"D1\", \"D2\", \"D3\"); }"),
        ("sample_32_xml_panel_binding.xml", "<?xml version=\"1.0\" encoding=\"UTF-8\"?><panel name=\"Dash\"><shape type=\"RECT\"/></panel>"),
        ("sample_33_try_catch_dp_query.ctl", "void safe_q() { try { dyn_dyn_anytype res; dpQuery(\"SELECT value\", res); } catch { DebugN(\"err\"); } }"),
        ("sample_34_legacy_mapping_profile.ctl", "void legacy() { dpGet(\"LegacyDP\", g_counter); }"),
        ("sample_35_comprehensive_scada_script.ctl", "global bool g_ready = false; main() { dpConnect(\"on_evt\", \"Master.Status\"); }"),
        ("sample_36_dyn_array_bounds.ctl", "main() { dyn_int arr = makeDynInt(1, 2); int x = arr[0]; }"),
        ("sample_37_bad_global_naming.ctl", "global string active_user_id = \"admin\";"),
        ("sample_38_unhandled_query.ctl", "void query_no_check() { dyn_dyn_anytype tab; dpQuery(\"SELECT value FROM DP*\", tab); }"),
        ("sample_39_sprintf_overflow.ctl", "void bad_sprintf(string s) { char buf[128]; sprintf(buf, \"User input: %s\", s); }"),
        ("sample_40_dp_set_wait_timeout.ctl", "void blocking_set() { dpSetWait(\"Tag1.:_original.._value\", 100); }"),
        ("sample_41_unmatched_lock.ctl", "void lock_demo() { lock(\"res_lock\"); do_critical_task(); }"),
        ("sample_42_bad_child_panel.ctl", "main() { ChildPanelOnCentral(\"popup.pnl\"); }"),
        ("sample_43_invalid_file_mode.ctl", "void bad_file_mode() { fopen(\"test.txt\", \"invalid_mode\"); }"),
        ("sample_44_missing_pnl_close.pnl", "main() { dpConnect(\"cb\", \"Live.:_online.._value\"); }"),
        ("sample_45_good_pnl_close.pnl", "main() { dpConnect(\"cb\", \"Live.:_online.._value\"); } void panelClose() { dpDisconnect(\"cb\", \"Live.:_online.._value\"); }"),
        ("sample_46_std_trend_script.ctl", "void load_trend(time t1, time t2) { dyn_float val; dyn_time tm; dpGetPeriod(t1, t2, 0, \"Trend.Tag.:_online.._value\", val, tm); }"),
        ("sample_47_alert_hdl_ack.ctl", "void ack_alert(string dpe, time t) { alertSet(t, 0, dpe, \":_alert_hdl.._ack\", 1); }"),
        ("sample_48_xml_event_script.xml", "<?xml version=\"1.0\" encoding=\"UTF-8\"?><script event=\"initialize\"><content>main(){}</content></script>"),
        ("sample_49_scoped_func.ctl", "synchronized void sync_process() { try { dpSet(\"SyncDP\", 1); } catch { DebugN(\"err\"); } }"),
        ("sample_50_socket_connect.ctl", "void conn_socket() { string host = \"10.0.0.1\"; int port = 8080; DebugN(host, port); }"),
        ("sample_51_dyn_string_concat.ctl", "void concat_tags() { dyn_string d1 = makeDynString(\"A\"); dyn_string d2 = makeDynString(\"B\"); dynAppend(d1, d2); }"),
        ("sample_52_dp_query_connect.ctl", "void q_conn() { dpQueryConnectSingle(\"on_q_change\", true, \"userData\", \"SELECT value FROM 'Pump*'\"); }"),
        ("sample_53_dp_get_types.ctl", "void check_types() { int val; dpGet(\"IntDP.:_online.._value\", val); }"),
        ("sample_54_xml_scada_layout.xml", "<?xml version=\"1.0\" encoding=\"UTF-8\"?><layout rows=\"2\" cols=\"2\"></layout>"),
        ("sample_55_full_scada_controller.ctl", "global int g_ctrl_state = 0; main() { dpConnect(\"on_ctrl\", \"Ctrl.State.:_online.._value\"); } void on_ctrl(string dp, int s) { try { g_ctrl_state = s; dpSet(\"Ctrl.Out.:_original.._value\", s); } catch { DebugN(\"Ctrl error\"); } }")
    ]

    for fname, content in samples:
        fpath = os.path.join(output_dir, fname)
        with open(fpath, "w", encoding="utf-8") as fp:
            fp.write(content.strip() + "\n")

    print(f"성공: 총 {len(samples)}개의 실물 WinCC OA 샘플 파일 구축 완료 (경로: {output_dir})")

if __name__ == "__main__":
    generate_55_real_samples()
