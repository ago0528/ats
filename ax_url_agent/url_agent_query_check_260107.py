# python url_agent_query_check_260107.py

import json
import re
from datetime import datetime

def parse_chrome_format(response_text: str) -> dict:
    """
    크롬 개발자 도구에서 복사한 SSE 응답을 파싱합니다.
    
    형식 예시:
    Event:xxx	CONNECT	connected!	
    17:53:32.362
    Event:xxx	CHAT	{...json...}	
    17:53:46.981
    """
    lines = response_text.strip().split('\n')
    
    connect_time = None
    chat_time = None
    button_url = None
    test_date = datetime.now().strftime('%Y-%m-%d')  # 오늘 날짜
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Event 라인 파싱: Event:xxx	TYPE	DATA
        if line.startswith('Event:'):
            parts = line.split('\t')
            if len(parts) >= 3:
                event_type = parts[1].strip()
                event_data = parts[2].strip()
                
                # 다음 줄이 시간인지 확인
                time_str = None
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # 시간 형식: HH:MM:SS.mmm
                    if re.match(r'^\d{2}:\d{2}:\d{2}\.\d{3}$', next_line):
                        time_str = next_line
                        i += 1  # 시간 줄 건너뛰기
                
                # CONNECT 이벤트
                if event_type == 'CONNECT' and time_str:
                    connect_time = time_str
                
                # CHAT 이벤트 (ASSISTANT 메시지)
                if event_type == 'CHAT' and event_data.startswith('{'):
                    try:
                        chat_data = json.loads(event_data)
                        if chat_data.get('messageType') == 'ASSISTANT':
                            chat_time = time_str
                            
                            # buttonUrl 추출
                            assistant_info = chat_data.get('assistant', {})
                            for ui_item in assistant_info.get('dataUIList', []):
                                ui_value = ui_item.get('uiValue', {})
                                if 'buttonUrl' in ui_value:
                                    button_url = ui_value['buttonUrl']
                                    break
                    except json.JSONDecodeError:
                        pass
        
        i += 1
    
    # 응답 시간 계산 (초)
    response_time_sec = '-'
    if connect_time and chat_time:
        try:
            fmt = '%H:%M:%S.%f'
            t1 = datetime.strptime(connect_time, fmt)
            t2 = datetime.strptime(chat_time, fmt)
            delta = (t2 - t1).total_seconds()
            response_time_sec = f'{delta:.2f}'
        except:
            pass
    
    # 테스트일시: 오늘 날짜 + CHAT 시간
    test_datetime = '-'
    if chat_time:
        # HH:MM:SS.mmm -> HH:MM:SS
        time_only = chat_time.split('.')[0]
        test_datetime = f'{test_date} {time_only}'
    
    return {
        '테스트일시': test_datetime,
        '응답시간(초)': response_time_sec,
        '실제URL': button_url or '-'
    }


def main():
    print("=" * 60)
    print("SSE 응답 파서 - 크롬 개발자 도구 형식")
    print("=" * 60)
    print("사용법:")
    print("  1. 크롬에서 복사한 내용 붙여넣기")
    print("  2. 빈 줄에서 Enter 2번 -> 파싱")
    print("  3. 'q' = 종료 / 's' = CSV 저장")
    print("=" * 60)
    
    results = []
    test_count = 0
    
    while True:
        print(f"\n[테스트 #{test_count + 1}] 응답 붙여넣기 (또는 q/s):")
        
        first_line = input().strip()
        
        if first_line.lower() in ['q', 'quit', 'exit']:
            print(f"\n총 {test_count}건 완료.")
            break
        
        if first_line.lower() == 's':
            if results:
                filename = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                with open(filename, 'w', encoding='utf-8-sig') as f:
                    f.write("테스트일시,응답시간(초),실제URL\n")
                    for r in results:
                        f.write(f"{r['테스트일시']},{r['응답시간(초)']},{r['실제URL']}\n")
                print(f"저장: {filename} ({len(results)}건)")
            else:
                print("저장할 결과 없음")
            continue
        
        # 응답 수집
        lines = [first_line]
        empty_count = 0
        
        while True:
            try:
                line = input()
                if line.strip() == '':
                    empty_count += 1
                    if empty_count >= 2:
                        break
                else:
                    empty_count = 0
                    lines.append(line)
            except EOFError:
                break
        
        response_text = '\n'.join(lines)
        
        if 'Event:' in response_text:
            result = parse_chrome_format(response_text)
            results.append(result)
            test_count += 1
            
            print("\n" + "-" * 50)
            print(f"테스트일시: {result['테스트일시']}")
            print(f"응답시간(초): {result['응답시간(초)']}")
            print(f"실제URL: {result['실제URL']}")
            print("-" * 50)
            print("📋 엑셀 복사용:")
            print(f"{result['테스트일시']}\t{result['응답시간(초)']}\t{result['실제URL']}")
        else:
            print("Event: 형식이 아닙니다.")


if __name__ == '__main__':
    main()