void safe_get() { try { anytype val; dpGet("S1.:_online.._value", val); } catch { DebugN("err"); } }
