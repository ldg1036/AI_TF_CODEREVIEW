// Vim WinCC OA Syntax Highlight Test File
synchronized void processData(dyn_string &dataList)
{
  for (int i = 1; i <= dynlen(dataList); i++)
  {
    if (dataList[i] == "") continue;
    dpSet("System1:Tag_" + i + ".value", dataList[i]);
  }
}
