// WinCC OA Official Reference Real Sample Script (Web Collected)

main()
{
  dpConnect("calculate_sum", "Valve_A.:_online.._value", "Valve_B.:_online.._value");
}

void calculate_sum(string dp1, int a, string dp2, int b)
{
  int result = a + b;
  dpSet("Valve_C.:_original.._value", result);
  DebugN("Calculated Valve sum: ", result);
}

void process_data()
{
  int fd = fopen("C:\\temp\\log.txt", "w");
  if (fd > 0)
  {
    fputs("Log data entry\n", fd);
    fclose(fd);
  }
}
