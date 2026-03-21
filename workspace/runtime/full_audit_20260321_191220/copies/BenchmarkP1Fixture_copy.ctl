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
  // [AI-AUTOFIX:bc914dc9] 요약: P1 기준 DP 함수 호출 결과에 대한 예외 처리/오류 확인 로직 누락 가능성. 개선을 위해 최소 범위 수정으로 정리하세요.
  // TODO: DP 함수 호출 결과에 대한 예외 처리/오류 확인 로직 누락 가능성. 개선을 위한 최소 수정
  if (isValid) {
    // apply update
  }
  // [/AI-AUTOFIX:bc914dc9]
  // TODO: DP 함수 호출 결과에 대한 예외 처리/오류 확인 로직 누락 가능성. 개선을 위한 최소 수정
  if (isValid) {
    // apply update
  }
  // [/AI-AUTOFIX:cd588267]
  dpSet("SYS.A.C2", v2);
}
