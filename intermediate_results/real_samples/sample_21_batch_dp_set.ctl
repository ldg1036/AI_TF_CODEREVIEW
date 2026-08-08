void batch_update()
{
  dyn_string dps = makeDynString("P1.:_original.._value", "P2.:_original.._value");
  dyn_anytype vals = makeDynAnytype(10, 20);
  dpSetWait(dps, vals);
}
