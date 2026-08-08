void safe_q() { try { dyn_dyn_anytype res; dpQuery("SELECT value", res); } catch { DebugN("err"); } }
