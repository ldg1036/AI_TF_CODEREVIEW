// Mooware CtrlRegex Sample Script
#uses "CtrlRegex"

main()
{
  string pattern = "^[A-Z_]+$";
  string inputStr = "WINCC_OA_VAR";
  bool isMatch = patternMatch(pattern, inputStr);
  DebugN("Regex match result:", isMatch);
}
