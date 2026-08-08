main() { string stdOut, stdErr; int code = system("ls -l /tmp", stdOut, stdErr); DebugN(code, stdOut); }
