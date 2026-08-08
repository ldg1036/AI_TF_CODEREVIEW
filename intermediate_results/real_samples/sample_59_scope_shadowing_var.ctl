global int g_var = 100;
void shadow_test() { int g_var = 200; DebugN(g_var); }
