import re
import os
from typing import List, Dict, Optional

class PnlParser:
    """
    WinCC OA .pnl 파일을 파싱하여 오브젝트별 이벤트 스크립트를 추출하는 클래스.
    고도화된 패턴 분석을 통해 패널 및 오브젝트 스크립트를 모두 추출합니다.
    """

    def __init__(self):
        # 오브젝트 패턴: SerialID Name (또는 Type ID Name)
        self.obj_header_pattern = re.compile(r'^\s*(?:E?([0-9]+)\s+)?([0-9]+)\s*\n\s*"([^"]*)"', re.MULTILINE)

    def normalize_pnl(self, content: str) -> List[Dict]:
        """
        PNL 파일 내용을 분석하여 구조화된 리스트로 반환.
        """
        results = []
        
        # 1. 오브젝트 위치 인덱싱
        objects = []
        for m in self.obj_header_pattern.finditer(content):
            objects.append({
                'pos': m.start(),
                'id': m.group(2),
                'name': m.group(3)
            })
        
        # 패널 가상 오브젝트 추가
        objects.insert(0, {'pos': 0, 'id': '0', 'name': '(Panel)'})
        objects.sort(key=lambda x: x['pos'])

        # 2. 모든 따옴표 블록 (스크립트 후보) 추출
        quoted_pattern = re.compile(r'"((?:[^"\\]|\\.)*)"', re.DOTALL)

        for match in quoted_pattern.finditer(content):
            raw_code = match.group(1)
            code = raw_code.replace('\\"', '"')
            
            # 스크립트 필터링 (너무 짧거나 코드 키워드가 없는 경우 제외)
            if len(code.strip()) < 5: continue
            if not any(kw in code for kw in ['main', 'synchronized', '{', '}', 'dpGet', 'dpSet', 'dpConnect', 'setMultiValue', 'dyn_', 'mapping ']):
                continue
            
            # 단순 속성값 (예: picture path, color 등) 제외 로직
            if re.match(r'^[a-zA-Z0-9_/.]+\.(png|jpg|gif|bmp)$', code.strip()): continue
            if code.strip().startswith('[pattern,'): continue

            start_pos = match.start()
            
            # 소유자 찾기
            owner = objects[0]
            for obj in reversed(objects):
                if obj['pos'] < start_pos:
                    owner = obj
                    break
            
            # 이벤트 타입 결정
            prefix = content[max(0, start_pos-100):start_pos]
            # WinCC OA PNL에서 스크립트 블록 앞에는 보통 "EventName" ID 가 옴
            event_match = re.search(r'"([^"]+)"\s+\d+\s*$', prefix.strip(), re.MULTILINE)
            event_name = event_match.group(1) if event_match else "Script"
            
            if "main(" in code and event_name == "Script":
                event_name = "Initialize" if owner['name'] == "(Panel)" else "main"

            # 결과 리스트에 추가
            target_obj = next((item for item in results if item["name"] == owner['name']), None)
            if not target_obj:
                target_obj = {
                    "name": owner['name'],
                    "id": owner['id'],
                    "type": "Object",
                    "events": []
                }
                results.append(target_obj)
            
            # 중복 체크
            if not any(e['code'] == code for e in target_obj["events"]):
                target_obj["events"].append({
                    "event": event_name,
                    "code": code,
                    "line_start": content.count('\n', 0, start_pos) + 1
                })

        return results

    def convert_to_text(self, content: str) -> str:
        """
        PNL 파일을 분석하여 읽기 좋은 텍스트 형식으로 변환.
        """
        parsed_data = self.normalize_pnl(content)
        extracted_blocks = []
        for obj in parsed_data:
            for event in obj["events"]:
                header = f"─// [{obj['name']}] [{obj['id']}] - [{event['event']}]"
                separator = "─" * 75
                extracted_blocks.append(f"{separator}\n{header}\n{separator}\n{event['code']}\n")
        return "\n".join(extracted_blocks)
