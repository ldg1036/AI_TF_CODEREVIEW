main()
{
  int v1 = 1;
  int v2 = 2;
  int v3 = 3;

  // P1 fixture: repeated setValue updates in one block
  setValue("A.B.C1", v1);
  setValue("A.B.C2", v2);
  setValue("A.B.C3", v3);
// [RULE-AUTOFIX:d46c8c46] Rule template suggestion for EXC-DP-01 (DP 함수 예외 처리)
// TODO: apply deterministic fix pattern or review manually
// [/RULE-AUTOFIX:d46c8c46]
  dpSet("SYS.A.C1", v1);
  dpSet("SYS.A.C2", v2);
}
