//-----------------------------------------------------------
// v1.0 (2026.01.28)
// v1.01 (2026.02.02)
// 코드리뷰 1차 반영, dpSet 일괄처리
//-----------------------------------------------------------

// #uses "lib_Common.ctl"
#uses "library_standard.ctl"
#uses "hosts.ctl"
// #uses "CtrlPv2Admin"

//---------------------------------------------
// configuration path & filename
//---------------------------------------------
string script_path;
string config_filename = "config/config.GoldenTime";

//---------------------------------------------
// general option
//---------------------------------------------
const string g_script_release_version = "v1.0";
const string g_script_release_date = "2026.01.28";

// [Global Variables]
string g_script_name = "GoldenTime";
string manager_dpname = "";
string ScriptActive_Condition = "ACTIVE";

const string PVLAST = ".PVLAST";

// [Optimized Global Variables]
mapping g_parsedConfig;
mapping g_bufferMap;
int g_lastExecutedHour = -1;
mapping g_lastValidUsageMap;

//*******************************************************************************
// name         : main()
// argument     :
// return value : void
// date         : 2026-01-28
// script by    :
// brief        : GoldenTime main
//*******************************************************************************
void main()
{
  int thread_ID;

  try
  {
    writeLog(g_script_name, "===== Script initialize start =====", LV_INFO);

    init_lib_Commmon();

    writeLog(g_script_name, "0. Script info. Ver=" + g_script_release_version + ", Date=" + g_script_release_date, LV_INFO);

    manager_dpname = init_program_info(g_script_name, g_script_release_version, g_script_release_date);


    //---------------------------------------------
    //1. Load config file
    //---------------------------------------------
    if (load_config() == false)
    {
      update_user_alarm(manager_dpname, "1. Config Load Failed.");
      exit();
    }
    else
    {
      writeLog(g_script_name, "1. Config Load & Parsing OK.", LV_INFO);
    }

    //---------------------------------------------
    //2. Apply script active conditions
    //---------------------------------------------
    writeLog(g_script_name, "2. Apply Script Active Condition", LV_INFO);

    if (dpExists(manager_dpname + ".Action.ActiveCondition"))
    {
      dpConnect("CB_ChangeActiveCondition", manager_dpname + ".Action.ActiveCondition");
    }
    else
    {
      init_script_active();
    }

    init_user_alarm(manager_dpname);

    delay(1);

    //---------------------------------------------
    //3. Start Calculation Thread
    //---------------------------------------------
    thread_ID = startThread("Calculation");

    if(thread_ID >= 0)
      writeLog(g_script_name, "3. Thread Start OK. ID=" + thread_ID, LV_INFO);
    else
    {
      writeLog(g_script_name, "3. Thread Start Failed.", LV_WARN);
      update_user_alarm(manager_dpname, "3. Thread Start Failed.");
      exit();
    }

    writeLog(g_script_name, "---- Complete : GoldenTime Script --------", LV_INFO);
  }
  catch
  {
    update_user_alarm(manager_dpname, "Exception of main(). Error=" + getLastException());
  }
}

//*******************************************************************************
// name         : load_config
// argument     :
// return value : bool
// date         : 2026-01-28
// developed by :
// brief        : Script config information Load
//*******************************************************************************
bool load_config()
{
  try
  {
      script_path = getPath(SCRIPTS_REL_PATH);
      if(substr(script_path, strlen(script_path)-1) != "/") script_path += "/";

      string config_file = script_path + config_filename;
      dyn_string raw_config_list;

      // [general]
      if(paCfgReadValue(config_file,"general","g_script_name", g_script_name)!=0)
        writeLog(g_script_name,"Failed to load : [general]g_script_name.", LV_WARN);

      if(paCfgReadValue(config_file,"general","Active_Condition", ScriptActive_Condition)!=0)
        writeLog(g_script_name,"Failed to load : [general] Active_Condition", LV_WARN);

      // [group_settings]
      if(paCfgReadValueList(config_file,"group_settings","GROUP_INFO", raw_config_list)!=0)
      {
        writeLog(g_script_name,"Failed to load : [group_settings] GROUP_INFO empty", LV_WARN);
        return false;
      }

      // [Parsing Logic]
      for(int i=1; i<=dynlen(raw_config_list); i++)
      {
          dyn_string parts = strsplit(raw_config_list[i], "|");

          if(dynlen(parts) < 6)
          {
              writeLog(g_script_name, "Config Parse Error at line " + i + ": " + raw_config_list[i], LV_WARN);
              continue;
          }

          string groupName = parts[1];

          dyn_anytype parsedData;
          parsedData[1] = parts[2]; // NLevel DP
          parsedData[2] = parts[3]; // Usage DP
          parsedData[3] = parts[4]; // GT DP
          parsedData[4] = (float)parts[5]; // Margin
          parsedData[5] = strsplit(parts[6], ","); // Tank List

          g_parsedConfig[groupName] = parsedData;

          string logMsg = "[Config Loaded] Group: " + groupName +
                          " / Tanks: " + dynlen(parsedData[5]) +
                          " / Margin: " + parsedData[4];
          writeLog(g_script_name, logMsg, LV_INFO);
      }

      return true;
  }
  catch
  {
      writeLog(g_script_name, "Exception in load_config: " + getLastException(), LV_ERR);
      return false;
  }
}

//*******************************************************************************
// name         : Calculation
// argument     :
// return value : void
// date         : 2026-01-28
// developed by :
// brief        : Hourly execution loop checking active state
//*******************************************************************************
void Calculation()
{
  writeLog(g_script_name, "Calculation Thread Start.", LV_INFO);
  time t;

  while(true)
  {
    try
    {
      t = getCurrentTime();

      if(isScriptActive == true)
      {
         if (minute(t) == 0 && hour(t) != g_lastExecutedHour)
         {
            GoldenTimeCalculation();
            g_lastExecutedHour = hour(t);
         }
      }
    }
    catch
    {
       update_user_alarm(manager_dpname, "Exception in Thread: " + getLastException());
       delay(10);
    }
    finally
    {
      delay(10);
    }
  }
}

//*******************************************************************************
// name         : GoldenTimeCalculation
// argument     :
// return value : void
// date         : 2026-01-28
// developed by :
// brief        : Execute Golden Time logic for all groups
//*******************************************************************************
void GoldenTimeCalculation()
{
  writeLog(g_script_name, "Start Golden Time Calculation...", LV_INFO);

  try
  {
    for(int i = 1; i <= mappinglen(g_parsedConfig); i++)
    {
      string groupName = mappingGetKey(g_parsedConfig, i);
      dyn_anytype data = g_parsedConfig[groupName];

      string nLevelDP  = data[1];
      string usageDP   = data[2];
      string gtDP      = data[3];
      float  margin    = data[4];
      dyn_string tanks = data[5];

      float sum = 0.0;
      int validCount = 0;

      for(int k=1; k<=dynlen(tanks); k++)
      {
        float val;
        if(dpGet(tanks[k] + PVLAST, val) == 0)
        {
           sum += val;
           validCount++;
        }
      }

      if(validCount > 0)
      {
        float currentAvg = sum / (float)validCount;
        processAndSave(groupName, currentAvg, nLevelDP, usageDP, gtDP, margin);
      }
      else
      {
        writeLog(g_script_name, "[" + groupName + "] No valid tank values read.", LV_WARN);
      }
    }
  }
  catch
  {
    writeLog(g_script_name,"Exception of GoldenTimeCalculation() \n" + getLastException(), LV_ERR);
  }
}

//*******************************************************************************
// name         : processAndSave
// argument     : 그룹명, 최근 평균 Level, N-Level DP, 사용량 DP, GoldenTime DP, 마진율
// return value : void
// date         : 2026-02-02
// developed by :
// brief        : Calculate usage, Golden Time, and save results
//*******************************************************************************
void processAndSave(string group, float currentAvg, string nLvlDP, string useDP, string gtDP, float margin)
{
    try
    {
        if(!mappingHasKey(g_bufferMap, group)) g_bufferMap[group] = makeDynFloat();
        dyn_float buffer = g_bufferMap[group];

        dynAppend(buffer, currentAvg);

        if(dynlen(buffer) >= 2)
        {
            float pastAvg = buffer[1];
            float calculatedUsage = pastAvg - currentAvg;
            float finalUsageToApply = 0.001;

            if (calculatedUsage > 0)
            {
                finalUsageToApply = calculatedUsage;
                g_lastValidUsageMap[group] = calculatedUsage;
            }
            else
            {
                if (mappingHasKey(g_lastValidUsageMap, group))
                {
                    finalUsageToApply = g_lastValidUsageMap[group];
                    writeLog(g_script_name, "[" + group + "] Filling/Hold. Using Last Valid: " + finalUsageToApply, LV_INFO);
                }
                else
                {
                    finalUsageToApply = 0.001;
                    writeLog(g_script_name, "[" + group + "] Filling/Hold. No History. Using Default.", LV_WARN);
                }
            }

            float remaining = currentAvg - margin;
            float goldenTime = remaining / finalUsageToApply;

            // dpSet 일괄 처리 (Code Review v.1)
            if(dpSet(nLvlDP + PVLAST, currentAvg,
                     useDP  + PVLAST, finalUsageToApply,
                     gtDP   + PVLAST, goldenTime) != 0)
            {
                 writeLog(g_script_name, "Batch dpSet Failed for Group: " + group, LV_WARN);
            }
            else
            {
                 writeLog(g_script_name, "[" + group + "] GT: " + goldenTime + " (Usage: " + finalUsageToApply + ")", LV_INFO);
            }

            dynRemove(buffer, 1);
        }
        else
        {
            if(dpSet(nLvlDP + PVLAST, currentAvg) != 0)
            {
                writeLog(g_script_name, "dpSet Failed (Init N-Level): " + nLvlDP, LV_WARN);
            }
            writeLog(g_script_name, "[" + group + "] Buffering Data... (Count: " + dynlen(buffer) + ")", LV_INFO);
        }

        g_bufferMap[group] = buffer;
    }
    catch
    {
        writeLog(g_script_name, "Exception in processAndSave (Group: " + group + "): " + getLastException(), LV_ERR);
    }
}
