void run_worker_loop()
{
  while (true)
  {
    do_work();
    delay(1);
  }
}
