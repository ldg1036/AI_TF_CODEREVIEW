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
