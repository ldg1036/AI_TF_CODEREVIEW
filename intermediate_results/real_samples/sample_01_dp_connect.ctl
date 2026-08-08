main() { dpConnect("add_cb", "A.:_online.._value", "B.:_online.._value"); }
void add_cb(string dp1, int a, string dp2, int b) { dpSet("C.:_original.._value", a+b); }
