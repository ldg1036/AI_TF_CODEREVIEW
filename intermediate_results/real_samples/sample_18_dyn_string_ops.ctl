void process_tags()
{
  dyn_string tags = makeDynString("Tag1", "Tag2", "Tag3");
  for (int i = 1; i <= dynlen(tags); i++)
  {
    DebugN("Processing tag:", tags[i]);
  }
}
