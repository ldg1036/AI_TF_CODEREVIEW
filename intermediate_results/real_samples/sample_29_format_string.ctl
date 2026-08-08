void format_display(float val)
{
  string txt = sprintf("%.2f %s", val, "bar");
  setValue("lbl_val", "text", txt);
}
