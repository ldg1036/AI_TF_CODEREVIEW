"""
24_generate_35_real_wincc_samples.py

웹 검색 및 WinCC OA 레퍼런스 구문에 기반한 35개 실물 샘플 파일 세트 동적 구축 스크립트
"""

import os

def generate_35_real_samples():
    output_dir = os.path.join("intermediate_results", "real_samples")
    os.makedirs(output_dir, exist_ok=True)

    samples = [
        ("sample_01_dp_connect.ctl", """
main()
{
  dpConnect("add_callback", "Valve_A.:_online.._value", "Valve_B.:_online.._value");
}
void add_callback(string dp1, int a, string dp2, int b)
{
  int res = a + b;
  dpSet("Valve_C.:_original.._value", res);
  DebugN("Result:", res);
}
"""),
        ("sample_02_dp_query.ctl", """
void fetch_all_dps()
{
  string query = "SELECT '_online.._value' FROM 'Motor_*' WHERE _LEAF";
  dyn_dyn_anytype tab;
  int rc = dpQuery(query, tab);
  if (rc != 0)
  {
    DebugN("dpQuery failed:", getLastError());
  }
}
"""),
        ("sample_03_dp_get_period.ctl", """
void get_history_data(time t1, time t2)
{
  dyn_float values;
  dyn_time times;
  int err = dpGetPeriod(t1, t2, 0, "Pump_Flow.:_online.._value", values, times);
  if (err != 0)
  {
    DebugN("dpGetPeriod Error");
  }
}
"""),
        ("sample_04_file_io.ctl", """
void write_log_file(string msg)
{
  int file_id = fopen("C:\\logs\\scada_event.log", "a");
  if (file_id > 0)
  {
    fputs(msg + "\n", file_id);
    fclose(file_id);
  }
}
"""),
        ("sample_05_db_query_safe.ctl", """
void execute_safe_db()
{
  string sql = "SELECT user_id, role FROM users WHERE active = 1";
  dbExecuteQuery(sql);
}
"""),
        ("sample_06_db_query_unsafe.ctl", """
void execute_unsafe_db(string input_val)
{
  string sql = "SELECT * FROM logs WHERE user = '" + input_val + "'";
  dbExecuteQuery(sql);
}
"""),
        ("sample_07_loop_delay_valid.ctl", """
void run_worker_loop()
{
  while (true)
  {
    do_work();
    delay(1);
  }
}
"""),
        ("sample_08_loop_delay_missing.ctl", """
void run_infinite_loop()
{
  while (true)
  {
    do_work();
  }
}
"""),
        ("sample_09_dp_connect_pair_missing.ctl", """
void setup_listeners()
{
  dpConnect("on_change", "Sensor_Temp.:_online.._value");
}
void on_change(string dp, float val)
{
  DebugN("Temp changed:", val);
}
"""),
        ("sample_10_dp_connect_pair_valid.ctl", """
void setup_and_cleanup()
{
  dpConnect("on_change_v", "Sensor_Press.:_online.._value");
}
void cleanup()
{
  dpDisconnect("on_change_v", "Sensor_Press.:_online.._value");
}
"""),
        ("sample_11_hardcoding_ip.ctl", """
void connect_plc()
{
  string plc_ip = "192.168.1.100";
  DebugN("Connecting to PLC:", plc_ip);
}
"""),
        ("sample_12_hardcoding_version_skip.ctl", """
void print_version()
{
  string ver = "System version 1.0.0.0";
  DebugN(ver);
}
"""),
        ("sample_13_try_catch_valid.ctl", """
void safe_dp_get()
{
  try
  {
    anytype val;
    dpGet("Sensor_1.:_online.._value", val);
  }
  catch
  {
    DebugN("Caught exception during dpGet");
  }
}
"""),
        ("sample_14_try_catch_missing.ctl", """
void unsafe_dp_get()
{
  anytype val;
  dpGet("Sensor_1.:_online.._value", val);
}
"""),
        ("sample_15_pnl_init_context.pnl", """
// ScopeLib:: initialize
main()
{
  dpConnect("on_pnl_init", "Panel_Status.:_online.._value");
}
void on_pnl_init(string dp, int status)
{
  setValue("txt_status", "text", status);
}
"""),
        ("sample_16_pnl_add_symbol.pnl", """
main()
{
  addSymbol(myModuleName(), myPanelName(), "objects/valve_faceplate.pnl", "Valve_1", makeDynString("$dpName:Valve_1"), 10, 20, 0, 1.0, 1.0);
}
"""),
        ("sample_17_alarm_handling.ctl", """
void handle_alarm(string dp, time t, int state)
{
  if (state > 1)
  {
    dpSet("Alarm_Summary.:_original.._value", state);
  }
}
"""),
        ("sample_18_dyn_string_ops.ctl", """
void process_tags()
{
  dyn_string tags = makeDynString("Tag1", "Tag2", "Tag3");
  for (int i = 1; i <= dynlen(tags); i++)
  {
    DebugN("Processing tag:", tags[i]);
  }
}
"""),
        ("sample_19_scada_panel_child.pnl", """
main()
{
  ChildPanelOnCentral("dialogs/confirm.pnl", "Confirm Dialog", makeDynString("$msg:Save Changes?"));
}
"""),
        ("sample_20_xml_config_sample.xml", """<?xml version="1.0" encoding="UTF-8"?>
<config>
  <datapoint name="Motor_01" type="Pump">
    <address>10.0.0.5</address>
  </datapoint>
</config>
"""),
        ("sample_21_batch_dp_set.ctl", """
void batch_update()
{
  dyn_string dps = makeDynString("P1.:_original.._value", "P2.:_original.._value");
  dyn_anytype vals = makeDynAnytype(10, 20);
  dpSetWait(dps, vals);
}
"""),
        ("sample_22_single_dp_set_consecutive.ctl", """
void bad_consecutive_set()
{
  dpSet("P1.:_original.._value", 10);
  dpSet("P2.:_original.._value", 20);
  dpSet("P3.:_original.._value", 30);
  dpSet("P4.:_original.._value", 40);
}
"""),
        ("sample_23_uninitialized_var.ctl", """
void calc_uninit()
{
  int total;
  int count = 5;
  total = total + count;
  DebugN("Total:", total);
}
"""),
        ("sample_24_global_var_scope.ctl", """
global int g_counter = 0;
void increment_global()
{
  g_counter++;
}
"""),
        ("sample_25_dp_get_period_split.ctl", """
void fetch_split_data(time t1, time t2)
{
  dyn_float vals;
  dyn_time tms;
  dpGetPeriodSplit(t1, t2, 3600, "Tank_Level.:_online.._value", vals, tms);
}
"""),
        ("sample_26_redundancy_check.ctl", """
void check_redundancy()
{
  if (isRedundantActive())
  {
    DebugN("Active node running");
  }
}
"""),
        ("sample_27_driver_para.ctl", """
void configure_kafka_driver(string topic)
{
  dpSet("Kafka_Driver.Config.Topic:_original.._value", topic);
}
"""),
        ("sample_28_panel_on_close.pnl", """
main()
{
  dpDisconnect("on_change", "Panel_Temp.:_online.._value");
}
"""),
        ("sample_29_format_string.ctl", """
void format_display(float val)
{
  string txt = sprintf("%.2f %s", val, "bar");
  setValue("lbl_val", "text", txt);
}
"""),
        ("sample_30_bitwise_ops.ctl", """
void check_mask(int status_word)
{
  if ((status_word & 0x01) != 0)
  {
    DebugN("Bit 0 set: Fault condition");
  }
}
"""),
        ("sample_31_multi_dp_connect.ctl", """
void multi_listen()
{
  dpConnect("on_multi_change", "DP1.:_online.._value", "DP2.:_online.._value", "DP3.:_online.._value");
}
"""),
        ("sample_32_xml_panel_binding.xml", """<?xml version="1.0" encoding="UTF-8"?>
<panel name="MainDashboard">
  <shape type="RECTANGLE" name="rect_bg">
    <property name="BackColor" value="{255,255,255}"/>
  </shape>
</panel>
"""),
        ("sample_33_try_catch_dp_query.ctl", """
void safe_query()
{
  try
  {
    dyn_dyn_anytype result;
    dpQuery("SELECT '_online.._value' FROM 'Tank_*'", result);
  }
  catch
  {
    DebugN("dpQuery Exception caught");
  }
}
"""),
        ("sample_34_legacy_mapping_profile.ctl", """
void legacy_call()
{
  dpGet("LegacyDP.:_online.._value", g_counter);
}
"""),
        ("sample_35_comprehensive_scada_script.ctl", """
// Comprehensive SCADA Production Module
global bool g_system_ready = false;

main()
{
  int init_rc = init_scada_module();
  if (init_rc == 0)
  {
    dpConnect("on_scada_event", "SCADA_Master.Status.:_online.._value");
  }
}

int init_scada_module()
{
  g_system_ready = true;
  return 0;
}

void on_scada_event(string dp, int status)
{
  try
  {
    if (status == 1)
    {
      dpSet("SCADA_Master.Control.:_original.._value", 100);
    }
  }
  catch
  {
    DebugN("SCADA event callback error");
  }
}
""")
    ]

    for fname, content in samples:
        fpath = os.path.join(output_dir, fname)
        with open(fpath, "w", encoding="utf-8") as fp:
            fp.write(content.strip() + "\n")

    print(f"성공: 총 {len(samples)}개의 실물 WinCC OA 샘플 파일 구축 완료 (경로: {output_dir})")

if __name__ == "__main__":
    generate_35_real_samples()
