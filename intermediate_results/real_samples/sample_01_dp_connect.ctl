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
