void check_mask(int status_word)
{
  if ((status_word & 0x01) != 0)
  {
    DebugN("Bit 0 set: Fault condition");
  }
}
