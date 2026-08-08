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
