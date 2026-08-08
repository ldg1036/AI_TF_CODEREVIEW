void write_log_file(string msg)
{
  int file_id = fopen("C:\logs\scada_event.log", "a");
  if (file_id > 0)
  {
    fputs(msg + "
", file_id);
    fclose(file_id);
  }
}
