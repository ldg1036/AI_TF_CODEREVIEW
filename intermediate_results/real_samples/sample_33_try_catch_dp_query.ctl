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
