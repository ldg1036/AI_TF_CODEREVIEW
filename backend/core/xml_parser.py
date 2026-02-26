import xml.etree.ElementTree as ET
import html
import os

class XmlParser:
    """
    WinCC OA XML 패널 형식을 파싱하여 스크립트를 추출하는 파서.
    """
    def parse(self, content: str) -> str:
        try:
            root = ET.fromstring(content)
            extracted_blocks = []

            # 1. Panel Global Scripts
            for events in root.findall('./events'):
                for script in events.findall('script'):
                    event_type = script.get('name', 'Panel_Event')
                    code = script.text
                    if code:
                        code = html.unescape(code).strip()
                        header = f"─// [(Panel)] [0] - [{event_type}]"
                        separator = "─" * 75
                        extracted_blocks.append(f"{separator}\n{header}\n{separator}\n{code}\n")

            # 2. Shape Scripts
            for shape in root.iter('shape'):
                shape_name = shape.get('Name', 'UnknownShape')
                shape_id = "999999"
                properties = shape.find('properties')
                if properties is not None:
                    for prop in properties.findall('prop'):
                        if prop.get('name') == 'serialId':
                            shape_id = prop.text
                            break
                
                for script in shape.iter('script'):
                    event_type = script.get('name', 'Event')
                    code = script.text
                    if code:
                        code = html.unescape(code).strip()
                        header = f"─// [{shape_name}] [{shape_id}] - [{event_type}]"
                        separator = "─" * 75
                        extracted_blocks.append(f"{separator}\n{header}\n{separator}\n{code}\n")

            return "\n".join(extracted_blocks)
        except Exception as e:
            return f"// Error parsing XML content: {e}"

    def normalize_xml(self, content: str) -> list:
        """
        HeuristicChecker에서 사용하는 구조로 변환 (Internal use)
        """
        results = []
        try:
            root = ET.fromstring(content)
            # Panel
            panel_obj = {"name": "(Panel)", "id": "0", "type": "Panel", "events": []}
            for events in root.findall('./events'):
                for script in events.findall('script'):
                    if script.text:
                        panel_obj["events"].append({
                            "event": script.get('name', 'Initialize'),
                            "code": html.unescape(script.text).strip(),
                            "line_start": 1
                        })
            if panel_obj["events"]: results.append(panel_obj)

            # Shapes
            for shape in root.iter('shape'):
                shape_name = shape.get('Name', 'Unknown')
                shape_id = "0"
                properties = shape.find('properties')
                if properties is not None:
                    for prop in properties.findall('prop'):
                        if prop.get('name') == 'serialId':
                            shape_id = prop.text
                            break
                
                obj = {"name": shape_name, "id": shape_id, "type": "Shape", "events": []}
                for script in shape.iter('script'):
                    if script.text:
                        obj["events"].append({
                            "event": script.get('name', 'Event'),
                            "code": html.unescape(script.text).strip(),
                            "line_start": 1
                        })
                if obj["events"]: results.append(obj)
        except Exception as e:
            print(f"[!] XmlParser.normalize_xml: Error parsing XML content: {e}")
        return results
