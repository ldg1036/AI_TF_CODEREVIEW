// v1.0 (2022.03.02)
// 1. PitPumpEWSAlarm first version
//-----------------------------------------------------------
// v1.01 (2022.09.26)
// 1. passive server memory 상승에 따른 오류 개선
//-----------------------------------------------------------
// v1.02 (2022.10.26)
// 1. Under Count Alarm 발생 계산결과(Alarm Set 값) 내림으로 소수점 버리고 비교하도록 변경
// 2. 불필요한 주석 삭제
//-----------------------------------------------------------

#uses "CtrlADO"
#uses "library_standard.ctl"
#uses "hosts.ctl"
#uses "dpGroups.ctl"
#uses "udag.ctl"

//---------------------------------------------
// configuration path & filename
//---------------------------------------------
string script_path;      //getPath(SCRIPTS_REL_PATH);
const string config_filename = "config/config.PitPumpEWSAlarm";
const string g_script_release_version = "v1.02";
const string g_script_release_date = "2022.10.26";
const string g_script_name = "PitPumpEWSAlarm";
string manager_dpname ="";  //ex: WCCOActrl_2  (A_SIT_ADMIN_MANAGER)
string ScriptActive_Condition  = "ACTIVE";  //|BOTH|HOST1|HOST2";
int query_blocking_time = 1000;

// config
string cfg_pvlast = ".PVLAST";
string cfg_pmmode = ".PMMODE";
string cfg_internal_svrtime = "A.TIME";

dyn_string cfg_tag_list, cfg_control_dyn_dp, cfg_status_dyn_dp;

// over parameter
string param_DAY_COUNT = ".DAY_COUNT";
string param_RUN_COUNT = ".RUN_COUNT";
string param_MONTH_MAX_COUNT = ".MONTH_MAX_COUNT";
string param_OVERCOUNT_RANGE = ".OVERCOUNT_RANGE";
string param_UNDERCOUNT_RANGE = ".UNDERCOUNT_RANGE";
string param_OVERCNTALM = ".alert.OVERCNTALM";
string param_DAY_MAX_COUNT = ".DAY_MAX_COUNT";
string param_DEVIATION_MODE = ".DEVIATION_MODE";
string param_DEVIATION_MAN = ".DEVIATION_MAN";
string param_MODE = ".MODE";
string param_OVER_AUTO_MAX = ".OVER_AUTO_MAX";
string param_OVER_AUTO_RANGE = ".OVER_AUTO_RANGE";
string param_AUTO_ALARM_SET = ".AUTO_ALARM_SET";
string param_OVER_MANUAL = ".OVER_MANUAL";
string param_YESTERDAY_COUNT = ".YESTERDAY_COUNT";
string param_AUTO_INITIAL = ".AUTO_INITIAL";
string param_AUTO_MAN = ".AUTO_MAN";
string param_AUTO_RANGE = ".AUTO_RANGE";
string param_OVER_ALARM_RESET = ".OVER_ALARM_RESET";

// under parameter
string param_BEFORE_SHIFT_COUNT = ".BEFORE_SHIFT_COUNT";
string param_CURRENT_SHIFT_COUNT = ".CURRENT_SHIFT_COUNT";
string param_UNDERCNTALM = ".alert.UNDERCNTALM";
string param_UNDER_ALARM_RESET = ".UNDER_ALARM_RESET";

// repeat alarm parameter
string param_SP_OVERCNT_REPTM = ".SP_OVERCNT_REPTM";
string param_OVERCNT_REPTM = ".OVERCNT_REPTM";
string param_OVERCNT_REPALM_INVALIDITY = ".OVERCNT_REPALM_INVALIDITY";
string param_SP_UNDERCNT_REPTM = ".SP_UNDERCNT_REPTM";
string param_UNDERCNT_REPTM = ".UNDERCNT_REPTM";
string param_UNDERCNT_REPALM_INVALIDITY = ".UNDERCNT_REPALM_INVALIDITY";
string param_OVERCNT_REPALM = ".alert.OVERCNT_REPALM";
string param_UNDERCNT_REPALM = ".alert.UNDERCNT_REPALM";

// run time parameter
string param_RUN_TMALM = ".alert.RUN_TMALM";
string param_RUN_REPALM = ".alert.RUN_REPALM";
string param_RUN_TM = ".RUN_TM";
string param_RUN_TMSET = ".RUN_TMSET";
string param_RUN_REPALM_INVALIDITY = ".RUN_REPALM_INVALIDITY";
string param_RUN_REPTM = ".RUN_REPTM";
string param_RUN_REPTMSET = ".RUN_REPTMSET";
string param_RUNTIME_ALARM_RESET = ".RUNTIME_ALARM_RESET";


mapping mapp_alarm_dp, mapp_status_value;
mapping mapp_repeat_alarm_dp, mapp_repeat_alarm_conf;
mapping mapp_runtm_dp, mapp_runtm_conf, mapp_runtm_check;
mapping mapp_auto_alarm_set_dp, mapp_auto_alarm_set_conf;

// Constant
const int RTN_VALUE_ERROR = -1;			// API 실행 실패 리턴값
const int RTN_VALUE_OK = 0;				// API 실행 성공 리턴값

const int ALM = 1;
const int INVALIDITY = 2;
const int MAXCNT = 3;
const int CURRCNT = 4;
const int REPALM = 5;

const int MAXRT = 2;
const int CURRT = 3;
const int PM = 4;
const int STATUS = 5;

const int MODE = 2;
const int MANU = 3;
const int AUTOMAX = 4;
const int AUTORANGE = 5;
const int MONTHMAN = 6;
const int MONTHRANGE = 7;
const int DAYRANGE = 8;


// initialize flag
bool is_initialize_complete = false;
bool is_shift_end = false;

//*******************************************************************************
// name         : main()
// argument     :
// return value :
// date         : 2020-06-09
// developed by : Tech/Ino Group (Ryan, Kim)
// brief        : Script main function
//*******************************************************************************
void main()
{
	int thread_id;
	int return_value;
	string dp_group, dp_group_alarm;
	dyn_string control_dyn_dp_count, control_dyn_dp_mode, control_dyn_dp_manual;
	string query;

	try
	{
		//-----------------------------------------------------------
		// 0. Common library initialize
		//-----------------------------------------------------------
		writeLog(g_script_name, "===== Script initialize start =====", LV_INFO);

		// Debug-Flag Initialize
		init_lib_Commmon();

		// Script infomation Log write
		writeLog(g_script_name, "0. Script info. Release version = " + g_script_release_version + ", Date = " + g_script_release_date, LV_INFO);
		writeLog(g_script_name, "                lib_standard Version = " + g_lib_standard_version + ", Date = " + g_lib_standard_release_date, LV_INFO);

		// Create Script Monitoring DP
		manager_dpname = init_program_info(g_script_name, g_script_release_version, g_script_release_date);

		//-----------------------------------------------------------
		// 1. Load Configuration
		//-----------------------------------------------------------
		if (load_config() == true)
		{
			writeLog(g_script_name, "1. Load configuration - OK", LV_INFO);
		}
		else
		{
			writeLog(g_script_name, "1. Load configuration - NG", LV_ERR);
			exit();
		}

		//---------------------------------------------
		// 2. Apply script active conditions
		//---------------------------------------------
		writeLog(g_script_name, "2. Apply script active condition", LV_INFO);
		if (dpExists(manager_dpname + ".Action.ActiveCondition") == true)
		{
			dpConnect("CB_ChangeActiveCondition", manager_dpname + ".Action.ActiveCondition");
		}
		else
		{
			init_script_active();
		}

		init_user_alarm(manager_dpname);	// Reset user User-defined alarm to OFF

		delay(1);

		//---------------------------------------------
		// 3. Dp alarm, status setting
		//---------------------------------------------
		writeLog(g_script_name, "3-1. Status, Alarm DP connection setting", LV_INFO);

    // Run time Alarm DP value connection setting
    create_runtime_dp(cfg_control_dyn_dp, param_RUN_TMALM, param_RUN_TMSET, param_RUN_TM);

    // run time over alarm dpconnect
    dpConnect_runtime();

    for(int i=1;i<=dynlen(cfg_status_dyn_dp);i++)
    {
      control_dyn_dp_count[i] = cfg_control_dyn_dp[i] + param_RUN_COUNT;

      mapp_alarm_dp[dpSubStr(cfg_status_dyn_dp[i],DPSUB_DP)] = dpSubStr(cfg_control_dyn_dp[i],DPSUB_DP);

      if(dpConnect("CB_StatusCount", cfg_status_dyn_dp[i]) == 0)
      {
        writeLog(g_script_name, "dpConnect for staus OK..."+i+"/"+dynlen(cfg_status_dyn_dp), LV_DBG1);
      }
      else
      {
        writeLog(g_script_name, "dpConnect for status NG..."+i+"/"+dynlen(cfg_status_dyn_dp), LV_ERR);
      }

      if(dpConnect("CB_CountOverAlarm", cfg_control_dyn_dp[i] + param_RUN_COUNT) == 0)
      {
        writeLog(g_script_name, "dpConnect for over alarm OK..."+i+"/"+dynlen(cfg_status_dyn_dp), LV_DBG1);
      }
      else
      {
        writeLog(g_script_name, "dpConnect for over alarm NG..."+i+"/"+dynlen(cfg_status_dyn_dp), LV_ERR);
      }
      delay(0,100);
    }

		writeLog(g_script_name, "3-2. Status, Alarm DP connection setting OK", LV_INFO);

		//---------------------------------------------
		// 4. Over Alarm auto connection setting
		//---------------------------------------------
		writeLog(g_script_name, "4-1. Over Alarm auto initialize and connection setting", LV_INFO);

		create_alarm_set_dp(cfg_control_dyn_dp, param_AUTO_ALARM_SET, param_MODE, param_OVER_MANUAL, param_OVER_AUTO_MAX, param_OVER_AUTO_RANGE,
							param_AUTO_MAN, param_AUTO_RANGE, param_OVERCOUNT_RANGE);

		dpConnect_alarm_set();

		startThread("CheckAutoAlarmSet");

		writeLog(g_script_name, "4-2. Over Alarm auto initialize and connection setting OK", LV_INFO);

		//---------------------------------------------
		// 5. Time Flow DP value connection setting
		//---------------------------------------------
		writeLog(g_script_name, "5-1. Time Flow DP value initialize and connection setting", LV_INFO);

		startThread("CheckTimeFlow", cfg_control_dyn_dp);

		writeLog(g_script_name, "5-2. Time Flow DP value initialize and connection OK", LV_INFO);

		//---------------------------------------------
		// 6. Run Time Over Alarm DP value connection setting
		//---------------------------------------------
		writeLog(g_script_name, "6-1. Runtime connection setting", LV_INFO);

		startThread("CheckRunTimeOver");

		writeLog(g_script_name, "6-2. Runtime connection OK", LV_INFO);

		//---------------------------------------------
		// 7. Repeat Alarm
		//---------------------------------------------
		// Count Under Alarm : shift(8시간 기준)마다 가동 횟수의 합산이 기준 이하 시 Alarm 발생.
		writeLog(g_script_name, "7-1. Over,Under,RunTime Repeat Alarm initialize and connection setting", LV_INFO);

		// create repeat alarm conf
		create_alm_dp(cfg_control_dyn_dp, param_OVERCNTALM, param_OVERCNT_REPALM_INVALIDITY, param_SP_OVERCNT_REPTM, param_OVERCNT_REPTM, param_OVERCNT_REPALM);
		create_alm_dp(cfg_control_dyn_dp, param_UNDERCNTALM, param_UNDERCNT_REPALM_INVALIDITY, param_SP_UNDERCNT_REPTM, param_UNDERCNT_REPTM, param_UNDERCNT_REPALM);
		create_alm_dp(cfg_control_dyn_dp, param_RUN_TMALM, param_RUN_REPALM_INVALIDITY, param_RUN_REPTMSET, param_RUN_REPTM, param_RUN_REPALM);

		writeLog(g_script_name, "7-3. Over,Under,RunTime Repeat Alarm initialize OK", LV_INFO);
		// alarm check
		dpConnect_alarm_repeat();

		startThread("CheckCountRepeatAlarm");

		writeLog(g_script_name, "7-4. Over,Under,RunTime Repeat Alarm connection OK", LV_INFO);

		//---------------------------------------------
		// 8. Alarm Reset check box
		//---------------------------------------------
		writeLog(g_script_name, "8-1. Alarm Reset connection setting", LV_INFO);

		dpConnect_alarm_reset(cfg_control_dyn_dp);

		writeLog(g_script_name, "8-4. Alarm Reset connection setting OK", LV_INFO);


		writeLog(g_script_name,"===== Script initialize Complete =====", LV_INFO);
	}
	catch
	{
		update_user_alarm(g_script_name, "Exception of main() : " + getLastException());
	}
}

//*******************************************************************************
// name         : loadConfig()
// argument     :
// return value : bool
// date         : 2020-06-09
// developed by : Tech/Ino Group (Ryan, Kim)
// brief        : Script config initialize
//*******************************************************************************
bool load_config()
{
	bool is_result = true;
	string config_path;

	int tmp_query_blocking_time;
	string tmp_script_active_condition;
	string tmp_cfg_internal_svrtime = "A.TIME";
	string tmp_cfg_pvlast = ".PVLAST";
	string tmp_cfg_pmmode = ".PMMODE";

	string tmp_param_MODE = ".MODE";
	string tmp_param_OVER_MANUAL = ".OVER_MANUAL";
	string tmp_param_OVER_AUTO_MAX = ".OVER_AUTO_MAX";
	string tmp_param_OVER_AUTO_RANGE = ".OVER_AUTO_RANGE";
	string tmp_param_AUTO_ALARM_SET = ".AUTO_ALARM_SET";
	string tmp_param_AUTO_INITIAL = ".AUTO_INITIAL";
	string tmp_param_AUTO_MAN = ".AUTO_MAN";
	string tmp_param_AUTO_RANGE = ".AUTO_RANGE";
	string tmp_param_OVERCOUNT_RANGE = ".OVERCOUNT_RANGE";
	string tmp_param_UNDERCOUNT_RANGE = ".UNDERCOUNT_RANGE";
	string tmp_param_DEVIATION_MODE = ".DEVIATION_MODE";
	string tmp_param_DEVIATION_MAN = ".DEVIATION_MAN";
	string tmp_param_SP_OVERCNT_REPTM = ".SP_OVERCNT_REPTM";
	string tmp_param_OVERCNT_REPTM = ".OVERCNT_REPTM";
	string tmp_param_OVERCNT_REPALM_INVALIDITY = ".OVERCNT_REPALM_INVALIDITY";
	string tmp_param_DAY_COUNT = ".DAY_COUNT";
	string tmp_param_RUN_COUNT = ".RUN_COUNT";
	string tmp_param_YESTERDAY_COUNT = ".YESTERDAY_COUNT";
	string tmp_param_DAY_MAX_COUNT = ".DAY_MAX_COUNT";
	string tmp_param_MONTH_MAX_COUNT = ".MONTH_MAX_COUNT";
	string tmp_param_SP_UNDERCNT_REPTM = ".SP_UNDERCNT_REPTM";
	string tmp_param_UNDERCNT_REPTM = ".UNDERCNT_REPTM";
	string tmp_param_UNDERCNT_REPALM_INVALIDITY = ".UNDERCNT_REPALM_INVALIDITY";
	string tmp_param_CURRENT_SHIFT_COUNT = ".CURRENT_SHIFT_COUNT";
	string tmp_param_BEFORE_SHIFT_COUNT = ".BEFORE_SHIFT_COUNT";
	string tmp_param_OVERCNTALM = ".alert.OVERCNTALM";
	string tmp_param_OVERCNT_REPALM = ".alert.OVERCNT_REPALM";
	string tmp_param_UNDERCNTALM = ".alert.UNDERCNTALM";
	string tmp_param_UNDERCNT_REPALM = ".alert.UNDERCNT_REPALM";
	string tmp_param_RUN_TMALM = ".alert.RUN_TMALM";
	string tmp_param_RUN_REPALM = ".alert.RUN_REPALM";
	string tmp_param_RUN_TM = ".RUN_TM";
	string tmp_param_RUN_REPTM = ".RUN_REPTM";
	string tmp_param_RUN_TMSET = ".RUN_TMSET";
	string tmp_param_RUN_REPALM_INVALIDITY = ".RUN_REPALM_INVALIDITY";
	string tmp_param_RUN_REPTMSET = ".RUN_REPTMSET";
	string tmp_param_OVER_ALARM_RESET = ".OVER_ALARM_RESET";
	string tmp_param_UNDER_ALARM_RESET = ".UNDER_ALARM_RESET";
	string tmp_param_RUNTIME_ALARM_RESET = ".RUNTIME_ALARM_RESET";

  dyn_string tmp_cfg_tag_list;

	try
	{

		// 1. Load config File Name from Manager DP
// 		if(globalExists("global_config_name") == TRUE)
// 			config_filename = global_config_name;
		//-----------------------------------------------------------
		// 2. load script Path
		//-----------------------------------------------------------
		config_path = getPath(SCRIPTS_REL_PATH) + config_filename;
		writeLog(g_script_name, "loadConfig() - config file path = " + config_path, LV_INFO);
// 		writeLog(g_script_name, "loadConfig() - config file path = " + config_path, LV_DBG2);

		//-----------------------------------------------------------
		// 3. read by section
		//-----------------------------------------------------------
		// [general] section read
		// 스크립트 동작 방식
		if(paCfgReadValue(config_path, "general", "ACTIVE_CONDITION", tmp_script_active_condition) != RTN_VALUE_OK)
		{
			writeLog(g_script_name, "Failed to load : [general] ACTIVE_CONDITION. Set to default value to " + ScriptActive_Condition, LV_WARN);
		}
		else
		{
			ScriptActive_Condition = tmp_script_active_condition;
		}

		// dpQueryConnectSingle() blocking 시간
		if(paCfgReadValue(config_path,"general","QUERY_BLOCKING_TIME", tmp_query_blocking_time) != RTN_VALUE_OK)
		{
		  writeLog(g_script_name,"Failed to load : [general] QUERY_BLOCKING_TIME. Set to default value to " + query_blocking_time, LV_WARN);
		}
		else
		{
		  query_blocking_time = tmp_query_blocking_time;
		}

		// server time
		if(paCfgReadValue(config_path, "general", "INTERNAL_SVRTIME", tmp_cfg_internal_svrtime) != RTN_VALUE_OK)
		{
			writeLog(g_script_name, "Failed to load : [general] INTERNAL_SVRTIME.", LV_ERR);
			is_result = false;
		}
		else
		{
		  cfg_internal_svrtime = tmp_cfg_internal_svrtime;
		}

		// pvlast
		if(paCfgReadValue(config_path, "main", "STATUS_PVLAST", tmp_cfg_pvlast) != RTN_VALUE_OK)
		{
			writeLog(g_script_name, "Failed to load : [main] STATUS_PVLAST.", LV_ERR);
			is_result = false;
		}
    else
    {
      cfg_pvlast = tmp_cfg_pvlast;
    }

		// pmmode
		if(paCfgReadValue(config_path, "main", "STATUS_PMMODE", tmp_cfg_pmmode) != RTN_VALUE_OK)
		{
			writeLog(g_script_name, "Failed to load : [main] STATUS_PMMODE.", LV_ERR);
			is_result = false;
		}
    else
    {
      cfg_pmmode = tmp_cfg_pmmode;
    }

    // param
  if(paCfgReadValue(config_path, "param", "param_MODE", tmp_param_MODE) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_MODE.", LV_ERR);is_result = false;}  else param_MODE = tmp_param_MODE;
  if(paCfgReadValue(config_path, "param", "param_OVER_MANUAL", tmp_param_OVER_MANUAL) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_OVER_MANUAL.", LV_ERR);is_result = false;}  else param_OVER_MANUAL = tmp_param_OVER_MANUAL;
  if(paCfgReadValue(config_path, "param", "param_OVER_AUTO_MAX", tmp_param_OVER_AUTO_MAX) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_OVER_AUTO_MAX.", LV_ERR);is_result = false;}  else param_OVER_AUTO_MAX = tmp_param_OVER_AUTO_MAX;
  if(paCfgReadValue(config_path, "param", "param_OVER_AUTO_RANGE", tmp_param_OVER_AUTO_RANGE) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_OVER_AUTO_RANGE.", LV_ERR);is_result = false;}  else param_OVER_AUTO_RANGE = tmp_param_OVER_AUTO_RANGE;
  if(paCfgReadValue(config_path, "param", "param_AUTO_ALARM_SET", tmp_param_AUTO_ALARM_SET) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_AUTO_ALARM_SET.", LV_ERR);is_result = false;}  else param_AUTO_ALARM_SET = tmp_param_AUTO_ALARM_SET;
  if(paCfgReadValue(config_path, "param", "param_AUTO_INITIAL", tmp_param_AUTO_INITIAL) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_AUTO_INITIAL.", LV_ERR);is_result = false;}  else param_AUTO_INITIAL = tmp_param_AUTO_INITIAL;
  if(paCfgReadValue(config_path, "param", "param_AUTO_MAN", tmp_param_AUTO_MAN) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_AUTO_MAN.", LV_ERR);is_result = false;}  else param_AUTO_MAN = tmp_param_AUTO_MAN;
  if(paCfgReadValue(config_path, "param", "param_AUTO_RANGE", tmp_param_AUTO_RANGE) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_AUTO_RANGE.", LV_ERR);is_result = false;}  else param_AUTO_RANGE = tmp_param_AUTO_RANGE;
  if(paCfgReadValue(config_path, "param", "param_OVERCOUNT_RANGE", tmp_param_OVERCOUNT_RANGE) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_OVERCOUNT_RANGE.", LV_ERR);is_result = false;}  else param_OVERCOUNT_RANGE = tmp_param_OVERCOUNT_RANGE;
  if(paCfgReadValue(config_path, "param", "param_UNDERCOUNT_RANGE", tmp_param_UNDERCOUNT_RANGE) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_UNDERCOUNT_RANGE.", LV_ERR);is_result = false;}  else param_UNDERCOUNT_RANGE = tmp_param_UNDERCOUNT_RANGE;
  if(paCfgReadValue(config_path, "param", "param_DEVIATION_MODE", tmp_param_DEVIATION_MODE) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_DEVIATION_MODE.", LV_ERR);is_result = false;}  else param_DEVIATION_MODE = tmp_param_DEVIATION_MODE;
  if(paCfgReadValue(config_path, "param", "param_DEVIATION_MAN", tmp_param_DEVIATION_MAN) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_DEVIATION_MAN.", LV_ERR);is_result = false;}  else param_DEVIATION_MAN = tmp_param_DEVIATION_MAN;
  if(paCfgReadValue(config_path, "param", "param_SP_OVERCNT_REPTM", tmp_param_SP_OVERCNT_REPTM) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_SP_OVERCNT_REPTM.", LV_ERR);is_result = false;}  else param_SP_OVERCNT_REPTM = tmp_param_SP_OVERCNT_REPTM;
  if(paCfgReadValue(config_path, "param", "param_OVERCNT_REPTM", tmp_param_OVERCNT_REPTM) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_OVERCNT_REPTM.", LV_ERR);is_result = false;}  else param_OVERCNT_REPTM = tmp_param_OVERCNT_REPTM;
  if(paCfgReadValue(config_path, "param", "param_OVERCNT_REPALM_INVALIDITY", tmp_param_OVERCNT_REPALM_INVALIDITY) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_OVERCNT_REPALM_INVALIDITY.", LV_ERR);is_result = false;}  else param_OVERCNT_REPALM_INVALIDITY = tmp_param_OVERCNT_REPALM_INVALIDITY;
  if(paCfgReadValue(config_path, "param", "param_DAY_COUNT", tmp_param_DAY_COUNT) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_DAY_COUNT.", LV_ERR);is_result = false;}  else param_DAY_COUNT = tmp_param_DAY_COUNT;
  if(paCfgReadValue(config_path, "param", "param_RUN_COUNT", tmp_param_RUN_COUNT) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_RUN_COUNT.", LV_ERR);is_result = false;}  else param_RUN_COUNT = tmp_param_RUN_COUNT;
  if(paCfgReadValue(config_path, "param", "param_YESTERDAY_COUNT", tmp_param_YESTERDAY_COUNT) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_YESTERDAY_COUNT.", LV_ERR);is_result = false;}  else param_YESTERDAY_COUNT = tmp_param_YESTERDAY_COUNT;
  if(paCfgReadValue(config_path, "param", "param_DAY_MAX_COUNT", tmp_param_DAY_MAX_COUNT) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_DAY_MAX_COUNT.", LV_ERR);is_result = false;}  else param_DAY_MAX_COUNT = tmp_param_DAY_MAX_COUNT;
  if(paCfgReadValue(config_path, "param", "param_MONTH_MAX_COUNT", tmp_param_MONTH_MAX_COUNT) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_MONTH_MAX_COUNT.", LV_ERR);is_result = false;}  else param_MONTH_MAX_COUNT = tmp_param_MONTH_MAX_COUNT;
  if(paCfgReadValue(config_path, "param", "param_SP_UNDERCNT_REPTM", tmp_param_SP_UNDERCNT_REPTM) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_SP_UNDERCNT_REPTM.", LV_ERR);is_result = false;}  else param_SP_UNDERCNT_REPTM = tmp_param_SP_UNDERCNT_REPTM;
  if(paCfgReadValue(config_path, "param", "param_UNDERCNT_REPTM", tmp_param_UNDERCNT_REPTM) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_UNDERCNT_REPTM.", LV_ERR);is_result = false;}  else param_UNDERCNT_REPTM = tmp_param_UNDERCNT_REPTM;
  if(paCfgReadValue(config_path, "param", "param_UNDERCNT_REPALM_INVALIDITY", tmp_param_UNDERCNT_REPALM_INVALIDITY) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_UNDERCNT_REPALM_INVALIDITY.", LV_ERR);is_result = false;}  else param_UNDERCNT_REPALM_INVALIDITY = tmp_param_UNDERCNT_REPALM_INVALIDITY;
  if(paCfgReadValue(config_path, "param", "param_CURRENT_SHIFT_COUNT", tmp_param_CURRENT_SHIFT_COUNT) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_CURRENT_SHIFT_COUNT.", LV_ERR);is_result = false;}  else param_CURRENT_SHIFT_COUNT = tmp_param_CURRENT_SHIFT_COUNT;
  if(paCfgReadValue(config_path, "param", "param_BEFORE_SHIFT_COUNT", tmp_param_BEFORE_SHIFT_COUNT) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_BEFORE_SHIFT_COUNT.", LV_ERR);is_result = false;}  else param_BEFORE_SHIFT_COUNT = tmp_param_BEFORE_SHIFT_COUNT;
  if(paCfgReadValue(config_path, "param", "param_OVERCNTALM", tmp_param_OVERCNTALM) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_OVERCNTALM.", LV_ERR);is_result = false;}  else param_OVERCNTALM = tmp_param_OVERCNTALM;
  if(paCfgReadValue(config_path, "param", "param_OVERCNT_REPALM", tmp_param_OVERCNT_REPALM) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_OVERCNT_REPALM.", LV_ERR);is_result = false;}  else param_OVERCNT_REPALM = tmp_param_OVERCNT_REPALM;
  if(paCfgReadValue(config_path, "param", "param_UNDERCNTALM", tmp_param_UNDERCNTALM) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_UNDERCNTALM.", LV_ERR);is_result = false;}  else param_UNDERCNTALM = tmp_param_UNDERCNTALM;
  if(paCfgReadValue(config_path, "param", "param_UNDERCNT_REPALM", tmp_param_UNDERCNT_REPALM) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_UNDERCNT_REPALM.", LV_ERR);is_result = false;}  else param_UNDERCNT_REPALM = tmp_param_UNDERCNT_REPALM;
  if(paCfgReadValue(config_path, "param", "param_RUN_TMALM", tmp_param_RUN_TMALM) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_RUN_TMALM.", LV_ERR);is_result = false;}  else param_RUN_TMALM = tmp_param_RUN_TMALM;
  if(paCfgReadValue(config_path, "param", "param_RUN_REPALM", tmp_param_RUN_REPALM) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_RUN_REPALM.", LV_ERR);is_result = false;}  else param_RUN_REPALM = tmp_param_RUN_REPALM;
  if(paCfgReadValue(config_path, "param", "param_RUN_TM", tmp_param_RUN_TM) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_RUN_TM.", LV_ERR);is_result = false;}  else param_RUN_TM = tmp_param_RUN_TM;
  if(paCfgReadValue(config_path, "param", "param_RUN_REPTM", tmp_param_RUN_REPTM) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_RUN_REPTM.", LV_ERR);is_result = false;}  else param_RUN_REPTM = tmp_param_RUN_REPTM;
  if(paCfgReadValue(config_path, "param", "param_RUN_TMSET", tmp_param_RUN_TMSET) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_RUN_TMSET.", LV_ERR);is_result = false;}  else param_RUN_TMSET = tmp_param_RUN_TMSET;
  if(paCfgReadValue(config_path, "param", "param_RUN_REPALM_INVALIDITY", tmp_param_RUN_REPALM_INVALIDITY) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_RUN_REPALM_INVALIDITY.", LV_ERR);is_result = false;}  else param_RUN_REPALM_INVALIDITY = tmp_param_RUN_REPALM_INVALIDITY;
  if(paCfgReadValue(config_path, "param", "param_RUN_REPTMSET", tmp_param_RUN_REPTMSET) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_RUN_REPTMSET.", LV_ERR);is_result = false;}  else param_RUN_REPTMSET = tmp_param_RUN_REPTMSET;
  if(paCfgReadValue(config_path, "param", "param_OVER_ALARM_RESET", tmp_param_OVER_ALARM_RESET) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_OVER_ALARM_RESET.", LV_ERR);is_result = false;}  else param_OVER_ALARM_RESET = tmp_param_OVER_ALARM_RESET;
  if(paCfgReadValue(config_path, "param", "param_UNDER_ALARM_RESET", tmp_param_UNDER_ALARM_RESET) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_UNDER_ALARM_RESET.", LV_ERR);is_result = false;}  else param_UNDER_ALARM_RESET = tmp_param_UNDER_ALARM_RESET;
  if(paCfgReadValue(config_path, "param", "param_RUNTIME_ALARM_RESET", tmp_param_RUNTIME_ALARM_RESET) != RTN_VALUE_OK){writeLog(g_script_name, "Failed to load : [param] param_RUNTIME_ALARM_RESET.", LV_ERR);is_result = false;}  else param_RUNTIME_ALARM_RESET = tmp_param_RUNTIME_ALARM_RESET;

  if(paCfgReadValueList(config_path, "list", "TAG_LIST", tmp_cfg_tag_list) != RTN_VALUE_OK)
  {
    writeLog(g_script_name, "Failed to load : [list] TAG_LIST.", LV_ERR);
    is_result = false;
  }
  else
  {
//     cfg_tag_list = strsplit(tmp_cfg_tag_list,"|");
    cfg_tag_list = tmp_cfg_tag_list;
    dyn_string dyn_tmp;
    writeLog(g_script_name, "tag list count = " + dynlen(cfg_tag_list), LV_INFO);
    for(int i=1;i<=dynlen(cfg_tag_list);i++)
    {
      strreplace(cfg_tag_list[i], " ", "");
      dyn_tmp = strsplit(cfg_tag_list[i], ",");
      if(dynlen(dyn_tmp) == 2)
      {
        dynAppend(cfg_status_dyn_dp, dyn_tmp[1] + cfg_pvlast);
        dynAppend(cfg_control_dyn_dp, dyn_tmp[2]);
      }
      else
      {
        writeLog(g_script_name, "Failed to load : [main] TAG_LIST. - Error in list!!("+cfg_tag_list[i]+")", LV_ERR);
        is_result = false;
      }
    }
  }

		string msg = "Configuration Information"
			+ "\n [general]"
			+ "\n ACTIVE_CONDITION = " 			+ ScriptActive_Condition
			+ "\n QUERY_BLOCKING_TIME = " 	+ query_blocking_time
      + "\n INTERNAL_SVRTIME = "      + cfg_internal_svrtime
			+ "\n [main]"
			+ "\n PVLAST = "                + cfg_pvlast
			+ "\n PMMODE = "                + cfg_pmmode
			+ "\n [param]"
      + "\n MODE = "                       + param_MODE
      + "\n OVER_MANUAL = "                + param_OVER_MANUAL
      + "\n OVER_AUTO_MAX = "              + param_OVER_AUTO_MAX
      + "\n OVER_AUTO_RANGE = "            + param_OVER_AUTO_RANGE
      + "\n AUTO_ALARM_SET = "             + param_AUTO_ALARM_SET
      + "\n AUTO_INITIAL = "               + param_AUTO_INITIAL
      + "\n AUTO_MAN = "                   + param_AUTO_MAN
      + "\n AUTO_RANGE = "                 + param_AUTO_RANGE
      + "\n OVERCOUNT_RANGE = "            + param_OVERCOUNT_RANGE
      + "\n UNDERCOUNT_RANGE = "           + param_UNDERCOUNT_RANGE
      + "\n DEVIATION_MODE = "             + param_DEVIATION_MODE
      + "\n DEVIATION_MAN = "              + param_DEVIATION_MAN
      + "\n SP_OVERCNT_REPTM = "           + param_SP_OVERCNT_REPTM
      + "\n OVERCNT_REPTM = "              + param_OVERCNT_REPTM
      + "\n OVERCNT_REPALM_INVALIDITY = "  + param_OVERCNT_REPALM_INVALIDITY
      + "\n DAY_COUNT = "                  + param_DAY_COUNT
      + "\n RUN_COUNT = "                  + param_RUN_COUNT
      + "\n YESTERDAY_COUNT = "            + param_YESTERDAY_COUNT
      + "\n DAY_MAX_COUNT = "              + param_DAY_MAX_COUNT
      + "\n MONTH_MAX_COUNT = "            + param_MONTH_MAX_COUNT
      + "\n SP_UNDERCNT_REPTM = "          + param_SP_UNDERCNT_REPTM
      + "\n UNDERCNT_REPTM = "             + param_UNDERCNT_REPTM
      + "\n UNDERCNT_REPALM_INVALIDITY = " + param_UNDERCNT_REPALM_INVALIDITY
      + "\n CURRENT_SHIFT_COUNT = "        + param_CURRENT_SHIFT_COUNT
      + "\n BEFORE_SHIFT_COUNT = "         + param_BEFORE_SHIFT_COUNT
      + "\n OVERCNTALM = "                 + param_OVERCNTALM
      + "\n OVERCNT_REPALM = "             + param_OVERCNT_REPALM
      + "\n UNDERCNTALM = "                + param_UNDERCNTALM
      + "\n UNDERCNT_REPALM = "            + param_UNDERCNT_REPALM
      + "\n RUN_TMALM = "                  + param_RUN_TMALM
      + "\n RUN_REPALM = "                 + param_RUN_REPALM
      + "\n RUN_TM = "                     + param_RUN_TM
      + "\n RUN_REPTM = "                  + param_RUN_REPTM
      + "\n RUN_TMSET = "                  + param_RUN_TMSET
      + "\n RUN_REPALM_INVALIDITY = "      + param_RUN_REPALM_INVALIDITY
      + "\n RUN_REPTMSET = "               + param_RUN_REPTMSET
      + "\n OVER_ALARM_RESET = "           + param_OVER_ALARM_RESET
      + "\n UNDER_ALARM_RESET = "          + param_UNDER_ALARM_RESET
      + "\n RUNTIME_ALARM_RESET = "        + param_RUNTIME_ALARM_RESET
			+ "\n [list]"
      + "\n TAG_LIST = "              + cfg_tag_list
      ;

		writeLog(g_script_name, msg, LV_INFO);
	}
	catch
	{
		update_user_alarm(g_script_name, "Exception of main() : " + getLastException());
	}
	finally
	{
		return is_result;
	}
}


//*******************************************************************************
// name         : CB_StatusCount()
// argument     :
// return value :
// date         : 2022-03-08
// developed by : htj
// brief        : status dp value = false->true, day_count+1
//*******************************************************************************
void CB_StatusCount(string dp, bool value)
{
  bool ispmmode;
  string status_dp, alarm_dp, runtm_alarm_dp;
  int tmp_day_count, day_count, current_shift_count, run_count;
  dyn_anytype oldValues, newValues;

	// API 실행 후 결과값
	int return_value = RTN_VALUE_ERROR;

  status_dp = dpSubStr(dp, DPSUB_DP);
  // 값 초기 셋팅 및 재구동 시 가동 횟수 +1 방지
  if(!mappingHasKey(mapp_status_value, status_dp))
  {
    // dp를 key로 값 저장
    mapp_status_value[status_dp] = value;
  }

  try
  {
    writeLog(g_script_name, "CB_StatusCount() - callback value of status DP. = " + dp, LV_DBG1);

    status_dp = dpSubStr(dp, DPSUB_DP);
    alarm_dp = mapp_alarm_dp[status_dp];
    runtm_alarm_dp = alarm_dp + param_RUN_TMALM;
    if(mappingHasKey(mapp_runtm_conf, runtm_alarm_dp))
      oldValues = mapp_runtm_conf[runtm_alarm_dp];
    else
      oldValues = makeDynAnytype(false, 0, 0, false, false);

    if(mappingHasKey(mapp_status_value, status_dp))
    {
      if(isScriptActive && mapp_status_value[status_dp] == false && value == true)
      {
        // get day_count and day, shift count
        return_value = dpGet(alarm_dp + param_DAY_COUNT, tmp_day_count,
                             alarm_dp + param_RUN_COUNT, run_count,
                             alarm_dp + param_CURRENT_SHIFT_COUNT, current_shift_count);
        if(return_value == RTN_VALUE_ERROR)
        {
          writeLog(g_script_name, "CB_StatusCount() - dpGet error.", LV_ERR);
        }
    		else
    		{
    			writeLog(g_script_name, "CB_StatusCount() - count up OK.", LV_DBG1);

          if(oldValues[PM] == false)
          {
            day_count = tmp_day_count+1;
            run_count++;
            return_value = dpSet(alarm_dp + param_DAY_COUNT, day_count,
                                 alarm_dp + param_RUN_COUNT, run_count,
                                 alarm_dp + param_CURRENT_SHIFT_COUNT, current_shift_count+1);
            if(return_value == RTN_VALUE_ERROR)
            {
              writeLog(g_script_name, "CB_StatusCount() - count up error. DPE = " + alarm_dp + param_DAY_COUNT + ":" + " Value = "+ day_count, LV_ERR);
              writeLog(g_script_name, "CB_StatusCount() - count up error. DPE = " + alarm_dp + param_RUN_COUNT + ":" + " Value = "+ run_count, LV_ERR);
              writeLog(g_script_name, "CB_StatusCount() - count up error. DPE = " + alarm_dp + param_CURRENT_SHIFT_COUNT + ":" + " Value = "+ current_shift_count+1, LV_ERR);
            }
        		else
        		{
        			writeLog(g_script_name, "CB_StatusCount() - count up OK. DPE = " + alarm_dp + param_DAY_COUNT + ":" + " Value = "+ day_count, LV_DBG1);
        		}
          }
        }
      }
    }
    mapp_status_value[status_dp] = value;
  }
  catch
  {
    writeLog(g_script_name, "CB_StatusCount() - ERROR", LV_ERR);
		update_user_alarm(manager_dpname , "Exception of CB_StatusCount(). Error = " + getLastException());
  }
}

//*******************************************************************************
// name         : CB_CountOverAlarm()
// argument     :
// return value :
// date         : 2022-03-08
// developed by : htj
// brief        : run_count+1 -> over_auto > run_count -> alarm on
//*******************************************************************************
void CB_CountOverAlarm(string dp, float run_count)
{
	//1. PitPumpEWSAlarm Active? ====================================================
	if (!isScriptActive)
	{
		return;
	}

	// API 실행 후 결과값
	int return_value = RTN_VALUE_ERROR;

  try
  {
    writeLog(g_script_name, "CB_CountOverAlarm() - callback value of status DP." + dp, LV_DBG1);

    string alarm_dp = dpSubStr(dp, DPSUB_DP);
    float old_run_count, mode, manual_count, auto_alarm_set;
    bool isOvercntalmOn;

    return_value = dpGet(alarm_dp + param_AUTO_ALARM_SET, auto_alarm_set,
                         alarm_dp + param_OVERCNTALM, isOvercntalmOn,
                         alarm_dp + param_MODE, mode);
    if(return_value == RTN_VALUE_ERROR)
    {
      writeLog(g_script_name, "CB_CountOverAlarm() initial dpGet error.", LV_ERR);
    }
		else
		{
      writeLog(g_script_name, "CB_CountOverAlarm() initial dpGet OK.", LV_DBG1);
		}

    if(mode == 0)
    {
      // manual
      return_value = dpGet(alarm_dp + param_OVER_MANUAL, manual_count);
      if(return_value == RTN_VALUE_ERROR)
      {
        writeLog(g_script_name, "CB_CountOverAlarm() manual initial dpGet error.", LV_ERR);
      }
  		else
  		{
        writeLog(g_script_name, "CB_CountOverAlarm() manual initial dpGet OK.", LV_DBG1);
  		}

      if(manual_count != 0 && run_count >= manual_count && !isOvercntalmOn)
      {
        return_value = dpSet(alarm_dp + param_OVERCNTALM, true);
        if(return_value == RTN_VALUE_ERROR)
        {
          writeLog(g_script_name, "CB_CountOverAlarm() MANUAL - dpSet error. DPE = " + alarm_dp + param_OVERCNTALM + ":" + " Value = true", LV_ERR);
        }
    		else
    		{
    			writeLog(g_script_name, "CB_CountOverAlarm() MANUAL - run_count("+run_count+") >= MANUAL_COUNT("+manual_count+")" , LV_DBG1);
    		}
      }
    }
    else
    {
      if(run_count >= auto_alarm_set && !isOvercntalmOn)
      {
        return_value = dpSet(alarm_dp + param_OVERCNTALM, true);
        if(return_value == RTN_VALUE_ERROR)
        {
          writeLog(g_script_name, "CB_CountOverAlarm() AUTO(MAX) - dpSet error. DPE = " + alarm_dp + param_OVERCNTALM + ":" + " Value = true", LV_ERR);
        }
    		else
    		{
    			writeLog(g_script_name, "CB_CountOverAlarm() AUTO(MAX)" , LV_DBG1);
    		}
      }
    }
  }
  catch
  {
		update_user_alarm(manager_dpname , "Exception of CB_CountOverAlarm(). Error = " + getLastException());
  }
}

//*******************************************************************************
// name         : CheckTimeFlow()
// argument     :
// return value :
// date         : 2022-03-08
// developed by : htj
// brief        : shift time over & [before_shift_count >= current_shift_count - (current_shift_count * %] -> alarm on
//*******************************************************************************
void CheckTimeFlow(dyn_string control_dyn_dp)
{
  time server_time;
  bool isOverAlarmOn, isUnderAlarmOn, isMonthFlag, isDeviationMode;
  float day_count, day_max_count, deviation_man, over_auto_range, overcount_range, yesterday_count;
  float before_shift_count, current_shift_count, undercount_range;

	// API 실행 후 결과값
	int return_value = RTN_VALUE_ERROR;
	dyn_anytype dpSet_dps, dpSet_values;

  while(true)
  {
    try
    {
    	//1. PitPumpEWSAlarm Active? ====================================================
    	if (!isScriptActive)
    	{
			delay_cycle(1);
    		continue;
    	}
      // for local
      server_time = getCurrentTime();
      // for test
      //dpGet("A.TIME", server_time);
      // every day initial
      if(hour(server_time) == 0 && minute(server_time) == 0 && second(server_time) == 0)
      {
        for(int i=1;i<=dynlen(control_dyn_dp);i++)
        {
          return_value = dpGet(control_dyn_dp[i] + param_DAY_COUNT,       day_count,
                               control_dyn_dp[i] + param_DAY_MAX_COUNT,   day_max_count,
                               control_dyn_dp[i] + param_YESTERDAY_COUNT, yesterday_count,
                               control_dyn_dp[i] + param_DEVIATION_MODE,  isDeviationMode,
                               control_dyn_dp[i] + param_DEVIATION_MAN,   deviation_man,
                               control_dyn_dp[i] + param_OVERCOUNT_RANGE, overcount_range);

          if(return_value == RTN_VALUE_ERROR)
          {
      			writeLog(g_script_name, "CheckTimeFlow() - dpget error.", LV_ERR);
          }
      		else
      		{
      			writeLog(g_script_name, "CheckTimeFlow() - dpget OK.", LV_DBG1);
      		}

          over_auto_range = day_count + (day_count * overcount_range / 100);
          // return_value = dpSet(control_dyn_dp[i] + param_OVER_AUTO_RANGE, over_auto_range);
          dynAppend(dpSet_dps, control_dyn_dp[i] + param_OVER_AUTO_RANGE);
		  dynAppend(dpSet_values, over_auto_range);
            // dynAppend(dpSet_values, newValues[AUTOMAX]);

          // if(return_value == RTN_VALUE_ERROR)
          // {
      			// writeLog(g_script_name, "CheckTimeFlow() - 증가율 dpset error.", LV_ERR);
          // }
      		// else
      		// {
      			// writeLog(g_script_name, "CheckTimeFlow() - 증가율 OK.", LV_DBG1);
      		// }

          // 편차 설정 시 편차 초과해서 차이나는 경우 일 MAX COUNT로 치지 않음.(비정상 상황 무시)
          if(isDeviationMode && (deviation_man > day_count - yesterday_count) && (day_count > day_max_count))
          {
            return_value = dpSet(control_dyn_dp[i] + param_DAY_MAX_COUNT,   day_count);
            if(return_value == RTN_VALUE_ERROR)
            {
        			writeLog(g_script_name, "CheckTimeFlow() - 편차설정 dpset error. 편차("+deviation_man+") > DAY_COUNT("+day_count+") - DAY_MAX_COUNT("+day_max_count+")", LV_ERR);
            }
        		else
        		{
        			writeLog(g_script_name, "CheckTimeFlow() - 편차설정 OK. 편차("+deviation_man+") > DAY_COUNT("+day_count+") - DAY_MAX_COUNT("+day_max_count+")", LV_DBG1);
        		}
          }
          else if(!isDeviationMode && (day_count > day_max_count))
          {
            return_value = dpSet(control_dyn_dp[i] + param_DAY_MAX_COUNT,   day_count);
            if(return_value == RTN_VALUE_ERROR)
            {
        			writeLog(g_script_name, "CheckTimeFlow() - 편차미설정 dpset error. DAY_COUNT("+day_count+") > DAY_MAX_COUNT("+day_max_count+")", LV_ERR);
            }
        		else
        		{
        			writeLog(g_script_name, "CheckTimeFlow() - 편차미설정 OK. DAY_COUNT("+day_count+") > DAY_MAX_COUNT("+day_max_count+")", LV_DBG1);
        		}
          }

          if(day(server_time) == 1)
          {
            MonthMaxCountReset(control_dyn_dp[i]);
          }

          // return_value = dpSet(control_dyn_dp[i] + param_DAY_COUNT,  0,
                               // control_dyn_dp[i] + param_RUN_COUNT,  0,
                               // control_dyn_dp[i] + param_YESTERDAY_COUNT, day_count);

		  dynAppend(dpSet_dps, control_dyn_dp[i] + param_DAY_COUNT);
		  dynAppend(dpSet_values, 0);

		  dynAppend(dpSet_dps, control_dyn_dp[i] + param_RUN_COUNT);
		  dynAppend(dpSet_values, 0);

		  dynAppend(dpSet_dps, control_dyn_dp[i] + param_YESTERDAY_COUNT);
		  dynAppend(dpSet_values, day_count);
          // if(return_value == RTN_VALUE_ERROR)
          // {
            // writeLog(g_script_name, "CheckTimeFlow() - day count reset error. DPE = " + control_dyn_dp[i] + param_YESTERDAY_COUNT + ":" + " Value = " + current_shift_count, LV_ERR);
            // writeLog(g_script_name, "CheckTimeFlow() - day count reset error. DPE = " + control_dyn_dp[i] + param_DAY_COUNT + ":" + " Value = 0", LV_ERR);
          // }
      		// else
      		// {
      			// writeLog(g_script_name, "CheckTimeFlow() - day count reset OK. DPE = " + control_dyn_dp[i] + param_YESTERDAY_COUNT + ":" + " Value = " + current_shift_count, LV_DBG1);
      			// writeLog(g_script_name, "CheckTimeFlow() - day count reset OK. DPE = " + control_dyn_dp[i] + param_DAY_COUNT + ":" + " Value = 0", LV_DBG1);
      		// }

          // Over Count Alarm Reset
          return_value = dpGet(control_dyn_dp[i] + param_OVERCNTALM,  isOverAlarmOn);
          if(return_value == RTN_VALUE_ERROR)
          {
            writeLog(g_script_name, "CheckTimeFlow() - Over Count Alarm Reset dpGet error.", LV_ERR);
          }
      		else
      		{
      			writeLog(g_script_name, "CheckTimeFlow() - Over Count Alarm Reset dpGet OK.", LV_DBG1);
            if(isOverAlarmOn)
            {
              // return_value = dpSet(control_dyn_dp[i] + param_OVERCNTALM, false);
			  dynAppend(dpSet_dps, control_dyn_dp[i] + param_OVERCNTALM);
			  dynAppend(dpSet_values, false);
              if(return_value == RTN_VALUE_ERROR)
              {
                writeLog(g_script_name, "CheckTimeFlow() - count over alarm reset error. DPE = " + control_dyn_dp[i] + param_OVERCNTALM + ":" + " Value = FALSE", LV_ERR);
              }
          		else
          		{
          			writeLog(g_script_name, "CheckTimeFlow() - count over alarm reset OK. DPE = " + control_dyn_dp[i] + param_OVERCNTALM + ":" + " Value = FALSE", LV_DBG1);
          		}
            }
          }
          delay(0,10);
        }
      }

      if((hour(server_time) == 6 || hour(server_time) == 14 || hour(server_time) == 22) && minute(server_time) == 0 && second(server_time) == 0)
      {
        for(int i=1;i<=dynlen(control_dyn_dp);i++)
        {
          return_value = dpGet(control_dyn_dp[i] + param_BEFORE_SHIFT_COUNT,  before_shift_count,
                               control_dyn_dp[i] + param_CURRENT_SHIFT_COUNT, current_shift_count,
                               control_dyn_dp[i] + param_UNDERCOUNT_RANGE,    undercount_range,
                               control_dyn_dp[i] + param_UNDERCNTALM,         isUnderAlarmOn);
          if(return_value == RTN_VALUE_ERROR)
          {
            writeLog(g_script_name, "CheckTimeFlow() - under count alarm initial dpGet error.", LV_ERR);
          }
      		else
      		{
      			writeLog(g_script_name, "CheckTimeFlow() - under count alarm initial dpGet OK.", LV_DBG1);
      		}

          // -- 20221026 : ALARM SET 값 계산 결과 내림으로 소수점 삭제.
          int tmp_alarm_set_value = floor(before_shift_count - (before_shift_count * undercount_range / 100));
          if((current_shift_count < tmp_alarm_set_value) && before_shift_count != 0)
          {
            // return_value = dpSet(control_dyn_dp[i] + param_UNDERCNTALM, true);
			  dynAppend(dpSet_dps, control_dyn_dp[i] + param_UNDERCNTALM);
			  dynAppend(dpSet_values, true);
            // if(return_value == RTN_VALUE_ERROR)
            // {
              // writeLog(g_script_name, "CheckTimeFlow() - under count alarm on error. DPE = " + control_dyn_dp[i] + param_UNDERCNTALM + ":" + " Value = true", LV_ERR);
            // }
        		// else
        		// {
        			// writeLog(g_script_name, "CheckTimeFlow() - under count alarm on OK. DPE = " + control_dyn_dp[i] + param_UNDERCNTALM + ":" + " Value = true", LV_DBG1);
        		// }
          }
          else
          {
            // return_value = dpSet(control_dyn_dp[i] + param_UNDERCNTALM, false);
			  dynAppend(dpSet_dps, control_dyn_dp[i] + param_UNDERCNTALM);
			  dynAppend(dpSet_values, false);
            // if(return_value == RTN_VALUE_ERROR)
            // {
              // writeLog(g_script_name, "CheckTimeFlow() - under count alarm reset error. DPE = " + control_dyn_dp[i] + param_UNDERCNTALM + ":" + " Value = false", LV_ERR);
            // }
        		// else
        		// {
        			// writeLog(g_script_name, "CheckTimeFlow() - under count alarm reset OK. DPE = " + control_dyn_dp[i] + param_UNDERCNTALM + ":" + " Value = false", LV_DBG1);
        		// }
          }

          // return_value = dpSet(control_dyn_dp[i] + param_BEFORE_SHIFT_COUNT,  current_shift_count,
                               // control_dyn_dp[i] + param_CURRENT_SHIFT_COUNT, 0);

		  dynAppend(dpSet_dps, control_dyn_dp[i] + param_BEFORE_SHIFT_COUNT);
		  dynAppend(dpSet_values, current_shift_count);

		  dynAppend(dpSet_dps, control_dyn_dp[i] + param_CURRENT_SHIFT_COUNT);
		  dynAppend(dpSet_values, 0);
          // if(return_value == RTN_VALUE_ERROR)
          // {
            // writeLog(g_script_name, "CheckTimeFlow() - shift count reset error. DPE = " + control_dyn_dp[i] + param_BEFORE_SHIFT_COUNT + ":" + " Value = " + current_shift_count, LV_ERR);
            // writeLog(g_script_name, "CheckTimeFlow() - shift count reset error. DPE = " + control_dyn_dp[i] + param_CURRENT_SHIFT_COUNT + ":" + " Value = 0", LV_ERR);
          // }
      		// else
      		// {
      			// writeLog(g_script_name, "CheckTimeFlow() - shift count reset OK. DPE = " + control_dyn_dp[i] + param_BEFORE_SHIFT_COUNT + ":" + " Value = " + current_shift_count, LV_DBG1);
      			// writeLog(g_script_name, "CheckTimeFlow() - shift count reset OK. DPE = " + control_dyn_dp[i] + param_CURRENT_SHIFT_COUNT + ":" + " Value = 0", LV_DBG1);
      		// }
          delay(0,10);
        }
      }

		if(isScriptActive == true && dynlen(dpSet_dps) > 0)
        {
			setDpValue_block(dpSet_dps, dpSet_values);
        }
	}
    catch
    {
      update_user_alarm(manager_dpname , "Exception of CheckTimeFlow(). Error = " + getLastException());
    }
    delay_cycle(1);
			dynClear(dpSet_dps);
			dynClear(dpSet_values);
  }
}

//*******************************************************************************
// name         : MonthMaxCountReset()
// argument     :
// return value : int
// date         : 2022-03-08
// developed by : htj
// brief        : server_time = every 1d. -> MONTH_MAX_COUNT = DAY_MAX_COUNT
int MonthMaxCountReset(string dp)
{
  int day_max_count, auto_initial, auto_man, auto_range, month_max_count, over_auto_max;

	// API 실행 후 결과값
	int return_value = RTN_VALUE_ERROR;

  return_value = dpGet(dp + param_DAY_MAX_COUNT, day_max_count,
                       dp + param_AUTO_INITIAL,  auto_initial,
                       dp + param_AUTO_MAN,      auto_man,
                       dp + param_AUTO_RANGE,    auto_range);
  if(return_value == RTN_VALUE_ERROR)
  {
    writeLog(g_script_name, "CheckTimeFlow() - initial dpGet error.", LV_ERR);
  }
  else
  {
    if(day_max_count == 0)
    {
      over_auto_max = auto_initial;
    }
    else if(day_max_count < 10)
    {
      over_auto_max = day_max_count + auto_man;
    }
    else
    {
      over_auto_max = day_max_count + (day_max_count * auto_range / 100);
    }

    return_value = dpSet(dp + param_MONTH_MAX_COUNT, day_max_count,
                         dp + param_OVER_AUTO_MAX,   over_auto_max,
                         dp + param_DAY_MAX_COUNT,   0);

    if(return_value == RTN_VALUE_ERROR)
    {
      writeLog(g_script_name, "CheckTimeFlow() - dpSet error. DPE = " + dp + param_MONTH_MAX_COUNT + ":" + " Value = " + day_max_count, LV_ERR);
      writeLog(g_script_name, "CheckTimeFlow() - dpSet error. DPE = " + dp + param_DAY_MAX_COUNT + ":" + " Value = 0", LV_ERR);
      return return_value;
    }
    else
    {
      writeLog(g_script_name, "CheckTimeFlow() - dpSet OK. DPE = " + dp + param_MONTH_MAX_COUNT + ":" + " Value = " + day_max_count, LV_DBG1);
  		writeLog(g_script_name, "CheckTimeFlow() - dpSet OK. DPE = " + dp + param_DAY_MAX_COUNT + ":" + " Value = 0", LV_DBG1);
      return return_value;
    }
  }
}

//*******************************************************************************
// name         : CheckCountRepeatAlarm()
// argument     :
// return value :
// date         : 2022-03-14
// developed by : htj
// brief        : repeat alarm for over and under
// over or under alarm connect.
void CheckCountRepeatAlarm()
{
	// API 실행 후 결과값
	int return_value = RTN_VALUE_ERROR;

  string dp_alarm;
  dyn_anytype oldValues, newValues, dpSet_dps, dpSet_values;
  mapping mapp_repeat_alarm_conf_old;

  mapp_repeat_alarm_conf_old = mapp_repeat_alarm_conf;

  writeLog(g_script_name, "8-3. CheckCountRepeatAlarm() - thread start.", LV_INFO);

  while(true)
  {
    try
    {
      for(int i=1;i<=mappinglen(mapp_repeat_alarm_conf);i++)
      {
        dp_alarm = mappingGetKey(mapp_repeat_alarm_conf, i);
        // mapp_repeat_alarm_conf = makeDynAnytype(alarm status, repeat invalidity, max count, current count, repeat alarm)
        if(mappingHasKey(mapp_repeat_alarm_conf_old,dp_alarm))
          oldValues = mapp_repeat_alarm_conf_old[dp_alarm];
        else
          oldValues =  mapp_repeat_alarm_conf[dp_alarm];
        newValues = mapp_repeat_alarm_conf[dp_alarm];
        // invalidity = false(repeat alarm 미사용)
        if(newValues[INVALIDITY] == false)
        {
          if(newValues[ALM] == true)
          {
            if(newValues[MAXCNT] != 0)
            {
              newValues[CURRCNT]++;
              if(newValues[CURRCNT] >= newValues[MAXCNT] * 2)
              {
                newValues[REPALM] = false;
                newValues[CURRCNT] = 0;
              }
              else if(newValues[CURRCNT] > newValues[MAXCNT])
              {
                newValues[REPALM] = true;
              }
              else
              {
                newValues[REPALM] = false;
              }
            }
            else
            {
              newValues[REPALM] = false;
              newValues[CURRCNT] = 0;
            }
          }
          else
          {
            newValues[REPALM] = false;
            newValues[CURRCNT] = 0;
          }
        }
        else
        {
          // reset
          if(newValues[CURRCNT] != 0)
          {
            newValues[CURRCNT] = 0;
            if(dynAppend(dpSet_dps, mapp_repeat_alarm_dp[dp_alarm][CURRCNT]) > 0)
              dynAppend(dpSet_values, newValues[CURRCNT]);
          }
          if(newValues[REPALM] != false)
          {
            newValues[REPALM] = false;
            if(dynAppend(dpSet_dps, mapp_repeat_alarm_dp[dp_alarm][REPALM]) > 0)
              dynAppend(dpSet_values, newValues[REPALM]);
          }
        }

        // alarm data set
        if(oldValues[REPALM] != newValues[REPALM])
        {
          if(dynAppend(dpSet_dps, mapp_repeat_alarm_dp[dp_alarm][REPALM]) > 0)
            dynAppend(dpSet_values, newValues[REPALM]);
        }
        // current count data set
        if(oldValues[CURRCNT] != newValues[CURRCNT])
        {
          if(dynAppend(dpSet_dps, mapp_repeat_alarm_dp[dp_alarm][CURRCNT]) > 0)
            dynAppend(dpSet_values, newValues[CURRCNT]);
        }

        mapp_repeat_alarm_conf_old[dp_alarm] = newValues;

        // Script 상태에 대한 감시 추가
  			// if (!isScriptActive)
  			// {
  				// delay_cycle(1);
  				// continue;
  			// }

        // if(dynlen(dpSet_dps) > 0)
        // {
          // setDpValue_block(dpSet_dps, dpSet_values);
  				// dynClear(dpSet_dps);
  				// dynClear(dpSet_values);
        // }
        // delay(0,10);
      }//for

		if(isScriptActive == true && dynlen(dpSet_dps) > 0)
        {
			setDpValue_block(dpSet_dps, dpSet_values);
        }
    }
    catch
    {
      update_user_alarm(manager_dpname, "Exception of CheckCountRepeatAlarm() \n" + getLastException());
      delay_cycle(1);
    }
    delay_cycle(1);
			dynClear(dpSet_dps);
			dynClear(dpSet_values);
  }
}

// alarm = param_OVERCNTALM or param_UNDERCNTALM....
// invalidity = param_OVERCNT_REPALM_INVALIDITY
// maxerrcnt = param_SP_OVERCNT_REPTM
// repalm = param_OVERCNT_REPALM
void create_alm_dp(dyn_string control_dyn_dp, string param_alarm, string param_invalidity, string param_maxerrcnt, string param_curerrcnt, string param_repalm)
{
  try
  {
    for(int i=1;i<=dynlen(control_dyn_dp);i++)
    {
      if(dpExists(control_dyn_dp[i] + param_alarm) && dpExists(control_dyn_dp[i] + param_invalidity) &&
         dpExists(control_dyn_dp[i] + param_maxerrcnt) && dpExists(control_dyn_dp[i] + param_curerrcnt) && dpExists(control_dyn_dp[i] + param_repalm))
        mapp_repeat_alarm_dp[control_dyn_dp[i] + param_alarm] = makeDynString(control_dyn_dp[i] + param_alarm, control_dyn_dp[i] + param_invalidity,
                                                                control_dyn_dp[i] + param_maxerrcnt, control_dyn_dp[i] + param_curerrcnt, control_dyn_dp[i] + param_repalm);
      delay(0,10);
    }
  }
  catch
  {
    writeLog(g_script_name, "Create mapping value for repeat Alarm error", LV_ERR);
  }
}

void create_runtime_dp(dyn_string control_dyn_dp, string param_alarm, string param_maxerrcnt, string param_curerrcnt)
{
  string pmmode_dp, status_dp;
  try
  {
    for(int i=1;i<=dynlen(control_dyn_dp);i++)
    {
      string tmp_cfg_pmmode_dp_name = cfg_status_dyn_dp[i];
      strreplace(tmp_cfg_pmmode_dp_name, cfg_pvlast, cfg_pmmode);
      pmmode_dp = tmp_cfg_pmmode_dp_name;
      status_dp = cfg_status_dyn_dp[i];
      if(dpExists(control_dyn_dp[i] + param_alarm) && dpExists(control_dyn_dp[i] + param_maxerrcnt) && dpExists(control_dyn_dp[i] + param_curerrcnt) && dpExists(pmmode_dp) && dpExists(status_dp))
        mapp_runtm_dp[control_dyn_dp[i] + param_alarm] = makeDynString(control_dyn_dp[i] + param_alarm, control_dyn_dp[i] + param_maxerrcnt, control_dyn_dp[i] + param_curerrcnt, pmmode_dp, status_dp);
      else
        writeLog(g_script_name, "Create mapping value for rumtime Alarm error --- "+control_dyn_dp[i] + param_alarm, LV_ERR);
      delay(0,10);
    }
  }
  catch
  {
    writeLog(g_script_name, "Create mapping value for rumtime Alarm error", LV_ERR);
  }
}

// (control_dyn_dp, param_AUTO_ALARM_SET, param_MODE, param_OVER_MANUAL, param_OVER_AUTO_MAX, param_OVER_AUTO_RANGE);
void create_alarm_set_dp(dyn_string control_dyn_dp, string param_alarm_set, string param_mode, string param_manual,
                    string param_auto_max, string param_over_auto_range, string param_auto_man, string param_auto_range,
                    string param_overcount_range)
{
  try
  {
    for(int i=1;i<=dynlen(control_dyn_dp);i++)
    {
      if(dpExists(control_dyn_dp[i] + param_alarm_set) && dpExists(control_dyn_dp[i] + param_mode) && dpExists(control_dyn_dp[i] + param_manual) && dpExists(control_dyn_dp[i] + param_auto_max) && dpExists(control_dyn_dp[i] + param_over_auto_range))
        mapp_auto_alarm_set_dp[control_dyn_dp[i] + param_alarm_set] = makeDynString(control_dyn_dp[i] + param_alarm_set, control_dyn_dp[i] + param_mode, control_dyn_dp[i] + param_manual, control_dyn_dp[i] + param_auto_max,
                                                                                    control_dyn_dp[i] + param_over_auto_range, control_dyn_dp[i] + param_auto_man, control_dyn_dp[i] + param_auto_range, control_dyn_dp[i] + param_overcount_range);
      delay(0,10);
    }
  }
  catch
  {
    writeLog(g_script_name, "Create mapping value for alarm set error", LV_ERR);
  }
}

void dpConnect_alarm_repeat()
{
  string dp_alarm;
  dyn_string dyn_dp;
  try
  {
    for(int i=1;i<=mappinglen(mapp_repeat_alarm_dp);i++)
    {
      dp_alarm = mappingGetKey(mapp_repeat_alarm_dp, i);
      dyn_dp = mappingGetValue(mapp_repeat_alarm_dp, i);

      if(dpConnectUserData("CB_AlarmCheck", dp_alarm, dyn_dp) == 0)
      {
        writeLog(g_script_name, "dpConnect for repeat Alarm OK", LV_DBG1);
      }
      else
      {
        writeLog(g_script_name, "dpConnect for repeat Alarm NG", LV_ERR);
      }
      delay(0, 10);
    }
  }
  catch
  {
    writeLog(g_script_name, "dpConnect for repeat Alarm error", LV_ERR);
  }
}

void dpConnect_runtime()
{
  string dp_alarm;
  dyn_string dyn_dp;
  try
  {
    for(int i=1;i<=mappinglen(mapp_runtm_dp);i++)
    {
      dp_alarm = mappingGetKey(mapp_runtm_dp, i);
      dyn_dp = mappingGetValue(mapp_runtm_dp, i);
      if(dpConnectUserData("CB_RuntimeAlarmCheck", dp_alarm, dyn_dp) == 0)
      {
        writeLog(g_script_name, "dpConnect for RUMTIME Alarm OK", LV_DBG1);
      }
      else
      {
        writeLog(g_script_name, "dpConnect for RUMTIME Alarm error", LV_ERR);
      }
      delay(0, 10);
    }
  }
  catch
  {
    writeLog(g_script_name, "dpConnect for RUMTIME Alarm error", LV_ERR);
  }
}

void dpConnect_alarm_set()
{
  string dp_alarm;
  dyn_string dyn_dp;
  try
  {
    for(int i=1;i<=mappinglen(mapp_auto_alarm_set_dp);i++)
    {
      dp_alarm = mappingGetKey(mapp_auto_alarm_set_dp, i);
      dyn_dp = mappingGetValue(mapp_auto_alarm_set_dp, i);

      if(dpConnectUserData("CB_AlarmSetCheck", dp_alarm, dyn_dp) == 0)
      {
        writeLog(g_script_name, "dpConnect for AUTO_ALARM_SET OK", LV_DBG1);
      }
      else
      {
        writeLog(g_script_name, "dpConnect for AUTO_ALARM_SET OK", LV_ERR);
      }
      delay(0, 10);
    }
  }
  catch
  {
    writeLog(g_script_name, "dpConnect for AUTO_ALARM_SET error", LV_ERR);
  }
}

void dpConnect_alarm_reset(dyn_string dyn_dp)
{
  writeLog(g_script_name, "8-2. CB_AlarmReset() -- dpConnect for Alarm Reset start!", LV_INFO);
  try
  {
    for(int i=1;i<=dynlen(dyn_dp);i++)
    {
      if(dpConnectUserData("CB_AlarmReset", dyn_dp[i], dyn_dp[i] + param_OVER_ALARM_RESET, dyn_dp[i] + param_UNDER_ALARM_RESET, dyn_dp[i] + param_RUNTIME_ALARM_RESET) == 0)
      {
        writeLog(g_script_name, "8-2. CB_AlarmReset() -- dpConnect for Alarm Reset OK", LV_DBG1);
      }
      else
      {
        writeLog(g_script_name, "8-2. CB_AlarmReset() -- dpConnect for Alarm Reset OK", LV_ERR);
      }
      delay(0, 10);
    }
  }
  catch
  {
    writeLog(g_script_name, "8-2. CB_AlarmReset() -- dpConnect for Alarm Reset error", LV_ERR);
  }
}

void CB_AlarmReset(string dp, string dp_over_reset, bool over_reset, string dp_under_reset, bool under_reset, string dp_rt_reset, bool rt_reset)
{
  int return_value = RTN_VALUE_ERROR;
	//1. PitPumpEWSAlarm Active? ====================================================
	if (!isScriptActive)
	{
		return;
	}

  string dp_alarm, dp_run_count, dp_run_time;
  if(over_reset == true)
  {
    return_value = dpSet(dpSubStr(dp_over_reset, DPSUB_SYS_DP_EL), false,
                         dp + param_OVERCNTALM, false,
                         dp + param_OVERCNT_REPALM, false,
                         dp + param_RUN_COUNT, 0);
    if(return_value == RTN_VALUE_ERROR)
    {
      writeLog(g_script_name, "9. CB_AlarmReset() -- dpSet for Alarm Reset error", LV_ERR);
    }
    else
    {
      writeLog(g_script_name, "9. CB_AlarmReset() -- dpSet for Alarm Reset OK.", LV_DBG1);
    }
  }
  if(under_reset == true)
  {
    return_value = dpSet(dpSubStr(dp_under_reset, DPSUB_SYS_DP_EL), false,
                         dp + param_UNDERCNTALM, false,
                         dp + param_UNDERCNT_REPALM, false);
    if(return_value == RTN_VALUE_ERROR)
    {
      writeLog(g_script_name, "9. CB_AlarmReset() -- dpSet for Alarm Reset error", LV_ERR);
    }
    else
    {
      writeLog(g_script_name, "9. CB_AlarmReset() -- dpSet for Alarm Reset OK.", LV_DBG1);
    }
  }
  if(rt_reset == true)
  {
    return_value = dpSet(dpSubStr(dp_rt_reset, DPSUB_SYS_DP_EL), false,
                         dp + param_RUN_TMALM, false,
                         dp + param_RUN_REPALM, false,
                         dp + param_RUN_TM, 0);
    if(return_value == RTN_VALUE_ERROR)
    {
      writeLog(g_script_name, "9. CB_AlarmReset() -- dpSet for Alarm Reset error", LV_ERR);
    }
    else
    {
      writeLog(g_script_name, "9. CB_AlarmReset() -- dpSet for Alarm Reset OK.", LV_DBG1);
    }
  }
}

// mapp_repeat_alarm_conf
// const int ALM = 1;
// const int INVALIDITY = 2;
// const int MAXCNT = 3;
// const int CURRCNT = 4;
// const int REPALM = 5;
void CB_AlarmCheck(string dp_alarm, dyn_string dyn_dp, dyn_anytype dyn_value)
{
  dyn_anytype oldValues, newValues;
  try
  {
    if(mappingHasKey(mapp_repeat_alarm_conf, dp_alarm))
      oldValues = mapp_repeat_alarm_conf[dp_alarm];
    else
      oldValues = makeDynAnytype(false, false, 0, 0, false);
//       oldValues = makeDynAnytype(dyn_value[ALM], dyn_value[INVALIDITY], dyn_value[MAXCNT], dyn_value[CURRCNT], dyn_value[REPALM]);

    if((oldValues[ALM] != dyn_value[ALM]) || (oldValues[INVALIDITY] != dyn_value[INVALIDITY]) || (oldValues[MAXCNT] != dyn_value[MAXCNT]) || (oldValues[CURRCNT] != dyn_value[CURRCNT]))
      newValues = makeDynAnytype(dyn_value[ALM], dyn_value[INVALIDITY], dyn_value[MAXCNT], dyn_value[CURRCNT], oldValues[REPALM]);
    else
      newValues = oldValues;

    if((oldValues[ALM] != dyn_value[ALM]) || (oldValues[INVALIDITY] != dyn_value[INVALIDITY]) || (oldValues[MAXCNT] != dyn_value[MAXCNT]) || (oldValues[CURRCNT] != dyn_value[CURRCNT]))
    {
      writeLog(g_script_name, "CB_AlarmCheck Change!! ````"+newValues, LV_DBG1);
      mapp_repeat_alarm_conf[dp_alarm] = newValues;
    }
  }
  catch
  {
    writeLog(g_script_name, "CB_AlarmCheck error!", LV_ERR);
  }
}

// mapp_runtm_dp
// 1. alarm = param_RUN_TMALM
// 2. max count = param_RUN_TMSET
// 3. current count = param_RUN_TM
// 4. pm mode = cfg_pmmode
//
// mapp_runtm_conf
// 1. alarm = ALM
// 2. max count = MAXRT
// 3. current count = CURRT
// 4. pm mode = PM
// 5. status = STATUS
void CB_RuntimeAlarmCheck(string dp_alarm, dyn_string dyn_dp, dyn_anytype dyn_value)
{
  dyn_anytype oldValues, newValues;
  try
  {
    if(mappingHasKey(mapp_runtm_conf, dp_alarm))
      oldValues = mapp_runtm_conf[dp_alarm];
    else
      oldValues = makeDynAnytype(false, 0, 0, false, false);

    if((oldValues[ALM] != dyn_value[ALM]) || (oldValues[MAXRT] != dyn_value[MAXRT]) || (oldValues[CURRT] != dyn_value[CURRT]) || (oldValues[PM] != dyn_value[PM]) || (oldValues[STATUS] != dyn_value[STATUS]))
      newValues = makeDynAnytype(dyn_value[ALM], dyn_value[MAXRT], dyn_value[CURRT], dyn_value[PM], dyn_value[STATUS]);
    else
      newValues = oldValues;

    if((oldValues[ALM] != dyn_value[ALM]) || (oldValues[MAXRT] != dyn_value[MAXRT]) || (oldValues[CURRT] != dyn_value[CURRT]) || (oldValues[PM] != dyn_value[PM]) || (oldValues[STATUS] != dyn_value[STATUS]))
    {
      writeLog(g_script_name, "CB_RuntimeAlarmCheck Change!! ````"+newValues, LV_DBG1);
      mapp_runtm_conf[dp_alarm] = newValues;
    }
  }
  catch
  {
    writeLog(g_script_name, "CB_RuntimeAlarmCheck error!", LV_ERR);
  }
}

// mapp_auto_alarm_set_conf
// const int ALM = 1;
// const int MODE = 2;
// const int MANU = 3;
// const int AUTOMAX = 4;
// const int AUTORANGE = 5;
// const int MAN = 6;
// const int RANGE = 7;
void CB_AlarmSetCheck(string dp_alarm_set, dyn_string dyn_dp, dyn_anytype dyn_value)
{
  dyn_anytype oldValues, newValues;
  try
  {
    if(mappingHasKey(mapp_auto_alarm_set_conf, dp_alarm_set))
      oldValues = mapp_auto_alarm_set_conf[dp_alarm_set];
    else
      oldValues = makeDynAnytype(0, 0, 0, 0, 0, 0, 0, 0);

    if((oldValues[MODE] != dyn_value[MODE]) || (oldValues[MANU] != dyn_value[MANU]) || (oldValues[AUTOMAX] != dyn_value[AUTOMAX]) || (oldValues[AUTORANGE] != dyn_value[AUTORANGE]) ||
       (oldValues[MONTHMAN] != dyn_value[MONTHMAN]) || (oldValues[MONTHRANGE] != dyn_value[MONTHRANGE]) || (oldValues[DAYRANGE] != dyn_value[DAYRANGE]))
      newValues = makeDynAnytype(oldValues[ALM], dyn_value[MODE], dyn_value[MANU], dyn_value[AUTOMAX], dyn_value[AUTORANGE], dyn_value[MONTHMAN], dyn_value[MONTHRANGE], dyn_value[DAYRANGE]);
    else
      newValues = oldValues;

    if((oldValues[MODE] != dyn_value[MODE]) || (oldValues[MANU] != dyn_value[MANU]) || (oldValues[AUTOMAX] != dyn_value[AUTOMAX]) || (oldValues[AUTORANGE] != dyn_value[AUTORANGE]) ||
       (oldValues[MONTHMAN] != dyn_value[MONTHMAN]) || (oldValues[MONTHRANGE] != dyn_value[MONTHRANGE]) || (oldValues[DAYRANGE] != dyn_value[DAYRANGE]))
    {
      writeLog(g_script_name, "CB_AlarmSetCheck Change!! ````"+newValues, LV_DBG1);
      mapp_auto_alarm_set_conf[dp_alarm_set] = newValues;
    }
  }
  catch
  {
    writeLog(g_script_name, "CB_AlarmSetCheck error!", LV_ERR);
  }
}

//*******************************************************************************
// name         : CheckRunTimeOver()
// argument     :
// return value :
// date         : 2022-03-14
// developed by : htj
// brief        : runtime alarm on/off
// over or under alarm connect.
void CheckRunTimeOver()
{
	// API 실행 후 결과값
	int return_value = RTN_VALUE_ERROR;

  string dp_alarm;
  dyn_anytype oldValues, newValues, dpSet_dps, dpSet_values;
  mapping mapp_runtm_conf_old;

  mapp_runtm_conf_old = mapp_runtm_conf;

  writeLog(g_script_name, "7-2. CheckRunTimeOver() - thread start.", LV_INFO);

  while(true)
  {
    try
    {
      for(int i=1;i<=mappinglen(mapp_runtm_conf);i++)
      {
        dp_alarm = mappingGetKey(mapp_runtm_conf, i);
        // mapp_runtm_conf = makeDynAnytype(alarm status, repeat invalidity, max count, current count, repeat alarm)
        if(mappingHasKey(mapp_runtm_conf_old,dp_alarm))
          oldValues = mapp_runtm_conf_old[dp_alarm];
        else
          oldValues =  mapp_runtm_conf[dp_alarm];
        newValues = mapp_runtm_conf[dp_alarm];
        if(newValues[STATUS] == true && newValues[PM] == false)
        {
          newValues[CURRT]++;
          if(newValues[ALM] == false)
          {
            if(newValues[CURRT] > newValues[MAXRT] && newValues[MAXRT] != 0)
            {
              newValues[ALM] = true;
            }
          }
          else
          {
            if(newValues[CURRT] <= newValues[MAXRT])
            {
              newValues[ALM] = false;
            }
          }
        }
        else
        {
          newValues[ALM] = false;
          newValues[CURRT] = 0;
        }

        // alarm data set
        if(oldValues[ALM] != newValues[ALM])
        {
          if(dynAppend(dpSet_dps, mapp_runtm_dp[dp_alarm][ALM]) > 0)
            dynAppend(dpSet_values, newValues[ALM]);
        }
        // current count data set
        if(oldValues[CURRT] != newValues[CURRT])
        {
          if(dynAppend(dpSet_dps, mapp_runtm_dp[dp_alarm][CURRT]) > 0)
            dynAppend(dpSet_values, newValues[CURRT]);
        }

        mapp_runtm_conf_old[dp_alarm] = newValues;

        // Script 상태에 대한 감시 추가
		// if (!isScriptActive)
		// {
			// delay_cycle(1);
			// continue;
		// }

        // if(dynlen(dpSet_dps) > 0)
        // {
          // setDpValue_block(dpSet_dps, dpSet_values);
			// dynClear(dpSet_dps);
			// dynClear(dpSet_values);
        // }
        // delay(0,10);

      } //for

	    if(isScriptActive == true && dynlen(dpSet_dps) > 0)
        {
            setDpValue_block(dpSet_dps, dpSet_values);
        }
    }
    catch
    {
      update_user_alarm(manager_dpname, "Exception of CheckRunTimeOver() \n" + getLastException());
      delay_cycle(1);
    }
    delay_cycle(1);
			dynClear(dpSet_dps);
			dynClear(dpSet_values);
  }
}

//*******************************************************************************
// name         : CheckAutoAlarmSet()
// argument     :
// return value :
// date         : 2022-03-14
// developed by : htj
// brief        : runtime alarm on/off
// over or under alarm connect.
void CheckAutoAlarmSet()
{
	// API 실행 후 결과값
	int return_value = RTN_VALUE_ERROR;

  string dp_alarm_set;
  dyn_anytype oldValues, newValues, dpSet_dps, dpSet_values;
  mapping mapp_auto_alarm_set_conf_old;

  mapp_auto_alarm_set_conf_old = mapp_auto_alarm_set_conf;

  while(true)
  {
    try
    {
      for(int i=1;i<=mappinglen(mapp_auto_alarm_set_conf);i++)
      {
        dp_alarm_set = mappingGetKey(mapp_auto_alarm_set_conf, i);
        if(mappingHasKey(mapp_auto_alarm_set_conf_old,dp_alarm_set))
          oldValues = mapp_auto_alarm_set_conf_old[dp_alarm_set];
        else
          oldValues =  mapp_auto_alarm_set_conf[dp_alarm_set];
        newValues = mapp_auto_alarm_set_conf[dp_alarm_set];

        if(oldValues[MODE] == 0 && newValues[MODE] == 1)
        {
          // mode 수동에서 자동으로 변경 시 수동값 자동으로 move.
          newValues[AUTOMAX] = newValues[MANU];
        }
        else if(newValues[MODE] == 1)
        {
          if(newValues[AUTOMAX] == 0)
          {
            newValues[ALM] = newValues[MANU];
          }
          else
          {
            newValues[ALM] = newValues[AUTOMAX];
          }
        }
        else if(newValues[MODE] == 2)
        {
          if(newValues[AUTORANGE] == 0)
          {
            newValues[ALM] = newValues[MANU];
          }
          else
          {
            newValues[ALM] = newValues[AUTORANGE];
          }
        }

        if((oldValues[MONTHMAN] != newValues[MONTHMAN]) || (oldValues[MONTHRANGE] != newValues[MONTHRANGE]))
        {
          string tmp_dp = dp_alarm_set;
          int month_max_count;
          strreplace(tmp_dp, param_AUTO_ALARM_SET, param_MONTH_MAX_COUNT);
          return_value = dpGet(tmp_dp, month_max_count);
          if(return_value == RTN_VALUE_ERROR)
          {
            writeLog(g_script_name, "CheckAutoAlarmSet dpGet error.", LV_ERR);
          }
          else
          {
            if(month_max_count > 0 && month_max_count < 10)
            {
            // 10회 미만 설정값 변경
              newValues[AUTOMAX] = month_max_count + newValues[MONTHMAN];
            }
            else if(month_max_count >= 10)
            {
            // 10회 이상 설정값 변경
              newValues[AUTOMAX] = month_max_count + (month_max_count * newValues[MONTHRANGE] / 100);
            }
          }
        }

        if(oldValues[DAYRANGE] != newValues[DAYRANGE])
        {
          // 증가율(일단위)
          // param_AUTO_ALARM_SET -> param_YESTERDAY_COUNT
          string tmp_dp = dp_alarm_set;
          int yesterday_count;
          strreplace(tmp_dp, param_AUTO_ALARM_SET, param_YESTERDAY_COUNT);
          return_value = dpGet(tmp_dp, yesterday_count);
          if(return_value == RTN_VALUE_ERROR)
          {
            writeLog(g_script_name, "CheckAutoAlarmSet dpGet error.", LV_ERR);
          }
          else
          {
            newValues[AUTORANGE] = yesterday_count + (yesterday_count * newValues[DAYRANGE] / 100);
          }
        }

        // alarm data set
        if(oldValues[ALM] != newValues[ALM])
        {
          if(dynAppend(dpSet_dps, mapp_auto_alarm_set_dp[dp_alarm_set][ALM]) > 0)
            dynAppend(dpSet_values, newValues[ALM]);
        }
        if(oldValues[AUTOMAX] != newValues[AUTOMAX])
        {
          if(dynAppend(dpSet_dps, mapp_auto_alarm_set_dp[dp_alarm_set][AUTOMAX]) > 0)
            dynAppend(dpSet_values, newValues[AUTOMAX]);
        }
        if(oldValues[AUTORANGE] != newValues[AUTORANGE])
        {
          if(dynAppend(dpSet_dps, mapp_auto_alarm_set_dp[dp_alarm_set][AUTORANGE]) > 0)
            dynAppend(dpSet_values, newValues[AUTORANGE]);
        }

        mapp_auto_alarm_set_conf_old[dp_alarm_set] = newValues;

	 // Script 상태에 대한 감시 추가
		// if (!isScriptActive)
		// {
			// delay_cycle(1);
			// continue;
		// }

        // if(dynlen(dpSet_dps) > 0)
        // {
          // setDpValue_block(dpSet_dps, dpSet_values);
  				// dynClear(dpSet_dps);
  				// dynClear(dpSet_values);
        // }
        // delay(0,10);
      }	//for

		if(isScriptActive == true && dynlen(dpSet_dps) > 0)
        {
			setDpValue_block(dpSet_dps, dpSet_values);
        }
    }
    catch
    {
      update_user_alarm(manager_dpname, "Exception of CheckAutoAlarmSet() \n" + getLastException());
      delay_cycle(1);
    }
    delay_cycle(1);
			dynClear(dpSet_dps);
			dynClear(dpSet_values);
  }
}


