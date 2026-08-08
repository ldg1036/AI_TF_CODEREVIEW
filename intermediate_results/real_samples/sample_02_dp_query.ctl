void fetch() { string q = "SELECT '_online.._value' FROM 'Motor_*'"; dyn_dyn_anytype tab; int rc = dpQuery(q, tab); if(rc!=0) DebugN(getLastError()); }
