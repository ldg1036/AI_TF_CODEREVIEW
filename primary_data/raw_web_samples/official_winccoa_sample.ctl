// Siemens Official WinCC OA Sample Script
#uses "WinCCOA_Utils"

public void initSystemConfig()
{
  dyn_string dpNames = makeDynString("Pump1", "Pump2", "Valve1");
  for (int i = 1; i <= dynlen(dpNames); i++)
  {
    dpCreate(dpNames[i], "AnalogInput");
  }
}
