void fetch_split_data(time t1, time t2)
{
  dyn_float vals;
  dyn_time tms;
  dpGetPeriodSplit(t1, t2, 3600, "Tank_Level.:_online.._value", vals, tms);
}
