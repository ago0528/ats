import requests
import json
from datetime import datetime
import time

class AgentTester:
    def __init__(self, bearer_token: str, cms_token: str, mrs_session: str):
        self.base_url = "https://api-llm.ats.kr-st2-midasin.com"
        self.headers = {
            "authorization": f"Bearer {bearer_token}",
            "cms-access-token": cms_token,
            "mrs-session": mrs_session,
            "content-type": "application/json",
            "accept": "application/json, text/plain, */*",
            "origin": "https://qa-jobda02-cms-recruiter-co-kr.midasweb.net",
            "referer": "https://qa-jobda02-cms-recruiter-co-kr.midasweb.net/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        self.results = []
    
    def send_query(self, message: str, conversation_id: str = None) -> str:
        """질의 전송 후 conversationId 반환"""
        url = f"{self.base_url}/api/v2/ai/orchestrator/query"
        payload = {
            "conversationId": conversation_id,
            "userMessage": message
        }
        
        response = requests.post(url, headers=self.headers, json=payload)
        data = response.json()
        return data.get("conversationId")
    
    def subscribe_sse(self, conversation_id: str) -> dict:
        """SSE 구독하여 결과 수신"""
        url = f"{self.base_url}/api/v1/ai/orchestrator/chat-room/sse/subscribe"
        params = {"conversationId": conversation_id}
        
        sse_headers = self.headers.copy()
        sse_headers["accept"] = "text/event-stream"
        del sse_headers["content-type"]  # GET 요청이므로 제거
        
        connect_time = None
        chat_time = None
        button_url = None
        
        response = requests.get(url, headers=sse_headers, params=params, stream=True)
        
        buffer = ""
        current_event = None
        
        for chunk in response.iter_content(chunk_size=1, decode_unicode=True):
            if chunk:
                buffer += chunk
                
                # 완전한 라인이 있는지 확인
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    
                    if line.startswith("event:"):
                        current_event = line.replace("event:", "").strip()
                        
                        if current_event == "CONNECT":
                            connect_time = datetime.now()
                            print(f"  [{connect_time.strftime('%H:%M:%S.%f')[:-3]}] CONNECT")
                    
                    elif line.startswith("data:"):
                        data_str = line.replace("data:", "", 1).strip()
                        
                        if current_event == "CHAT" and data_str.startswith("{"):
                            try:
                                data = json.loads(data_str)
                                if data.get("messageType") == "ASSISTANT":
                                    chat_time = datetime.now()
                                    
                                    # buttonUrl 추출
                                    assistant = data.get("assistant", {})
                                    for ui in assistant.get("dataUIList", []):
                                        ui_value = ui.get("uiValue", {})
                                        if "buttonUrl" in ui_value:
                                            button_url = ui_value["buttonUrl"]
                                            break
                                    
                                    print(f"  [{chat_time.strftime('%H:%M:%S.%f')[:-3]}] CHAT → {button_url}")
                                    response.close()
                                    
                                    # 결과 반환
                                    response_time = "-"
                                    if connect_time and chat_time:
                                        delta = (chat_time - connect_time).total_seconds()
                                        response_time = f"{delta:.2f}"
                                    
                                    return {
                                        "테스트일시": chat_time.strftime("%Y-%m-%d %H:%M:%S"),
                                        "응답시간(초)": response_time,
                                        "실제URL": button_url or "-"
                                    }
                            
                            except json.JSONDecodeError:
                                pass
        
        return {"테스트일시": "-", "응답시간(초)": "-", "실제URL": "-"}
    
    def run_test(self, message: str) -> dict:
        """단일 테스트 실행"""
        print(f"\n{'='*60}")
        print(f"질의: {message}")
        print("-" * 60)
        
        # 1. Query 전송
        conversation_id = self.send_query(message)
        print(f"  conversationId: {conversation_id}")
        
        if not conversation_id:
            print("  ❌ conversationId 획득 실패")
            return None
        
        # 2. SSE 구독
        result = self.subscribe_sse(conversation_id)
        result["질의"] = message
        self.results.append(result)
        
        print("-" * 60)
        print(f"📋 엑셀: {result['테스트일시']}\t{result['응답시간(초)']}\t{result['실제URL']}")
        
        return result
    
    def run_batch_test(self, queries: list, delay: float = 1.0):
        """배치 테스트 실행"""
        total = len(queries)
        
        for i, query in enumerate(queries, 1):
            print(f"\n[{i}/{total}]", end="")
            self.run_test(query)
            
            if i < total:
                time.sleep(delay)  # 서버 부하 방지
        
        print(f"\n\n{'='*60}")
        print(f"✅ 총 {len(self.results)}건 테스트 완료")
        self.save_results()
    
    def save_results(self, filename: str = None):
        """결과 CSV 저장"""
        if not filename:
            filename = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(filename, 'w', encoding='utf-8-sig') as f:
            f.write("질의,테스트일시,응답시간(초),실제URL\n")
            for r in self.results:
                # CSV에서 쉼표 이스케이프
                query = r.get('질의', '').replace('"', '""')
                f.write(f'"{query}",{r["테스트일시"]},{r["응답시간(초)"]},{r["실제URL"]}\n')
        
        print(f"저장 완료: {filename}")
        return filename


# ============================================================
# 실행
# ============================================================
if __name__ == "__main__":
    
    # 토큰 설정 (크롬 개발자 도구에서 복사)
    BEARER_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJqdGkiOiJkODEyNjk3Mi1hYmRkLTQzZjQtYWYyZS1mYjk3ZjQzOTEwMzkiLCJpYXQiOjE3Njc3ODI4NzgsImlzcyI6IlJldGVudGlvbiIsImV4cCI6MTc2Nzc5MDA3OCwiU0VSVklDRV9OQU1FIjoiTVJTIiwiQ09NUEFOWV9OQU1FIjoi7LGE7Jqp7ZiB7Iug6rCc67Cc7YyAIiwiU1BBQ0VfSUQiOiI2NiIsIkpPQkRBX0RFVl9BRE1JTl9ET01BSU4iOiJxYS1qb2JkYTAyLmNtcy5kdHMua3Itc3QtamFpbndvbi5jb20iLCJBQ0NfRE9NQUlOIjoicWEtam9iZGEwMi5hY2NhLmtyLXN0Mi1qYWlud29uLmNvbSIsIkpPQkRBX0RFVl9ET01BSU4iOiJxYS1qb2JkYTAyLnN0Mi1waHMtaW0uZHRzLmtyLXN0LWphaW53b24uY29tIiwiVE9LRU5fVFlQRSI6Ik1FTUJFUiIsIlRFTkFOVF9JRCI6IjMzMjU0MyIsIk1FTUJFUl9JRCI6Njg1OSwiQUNDX0FETUlOX0RPTUFJTiI6InFhLWpvYmRhMDIuY21zLmFjY2Eua3Itc3QyLWphaW53b24uY29tIiwiRU1BSUwiOiJhZ28wNTI4QGphaW53b24uY29tIn0.tYbv-m49ufqP_O0Co_Wu3OrrL2AafkYjWLbYGlvygoE"
    
    CMS_TOKEN = "eyJhbGciOiJSUzI1NiJ9.eyJhdWQiOiJtcnNfYXBpIiwic3ViIjoiYWdvMDUyOCIsInNwYWNlU24iOjY2LCJjb21wYW55U24iOjMzMjU0MywiaWQiOiJhZ28wNTI4IiwidXNlcl9uYW1lIjoiYWdvMDUyOCIsImFjY0F1dGhUb2tlbiI6ImV5SmhiR2NpT2lKSVV6STFOaUo5LmV5SnpkV0lpT2lKTlFVNUJSMFZTSWl3aVlYVmtJam9pTXpjMUlpd2lWRVZPUVU1VVgxTk9Jam8zT1N3aWMzQmhZMlZUYmlJNk1Td2lhWE5WYzJWVGNHRmpaU0k2ZEhKMVpTd2ljM0JoWTJWU2IyeGxUR2x6ZENJNlczc2ljM0JoWTJWVGJpSTZNU3dpY205c1pTSTZJazFCVGtGSFJWSWlmVjBzSW1saGRDSTZNVGMyTnpjNE1qZzNOU3dpWlhod0lqb3hOelkzT0RBME5EYzFmUS40SWI2V2x1c3FOc2UxWV9fZHh3ZHF6LTd5Z1oybDFNSlM4OUk1Z1MyVEhFIiwiaXNTbXNDb25maXJtIjpmYWxzZSwiaXNFbWFpbENvbmZpcm0iOmZhbHNlLCJqb2JkYURldlNlc3Npb25JZCI6IjI4YmM2NDA3LWNmODUtNDc0NS05ZWViLTBiMmViN2U3YjJlYSIsImF1dGhvcml0aWVzIjpbIlJPTEVfVVNFUiJdLCJleHAiOjE3NjgzODc2NzV9.fImilk3_u9SHfaCFZoRvw1epqh1vdkfCLF2ez25unvAWpcAIlwLM28g7nRASp71E6o9nzEipO6X3DmfBwvyu7Nr11QdqCHfFqaNEfqSjSp9Zi_nPju7m-Fg-LUiyp9nm-Y60ny63gV1olGLOtLqH2a2df4InWZ4umeTERsvBxcBdi0U1BmuqfvPn4u3nanwhNJZUkr-NOH3roPIl4zonpoSXwXgCSHfj2n3CbogcamnV1lCnWKJcscWDyfehqiN7hUhXwmYoJ3i_Uel-tV9McsqE_CoSn-97wX1HpovycI1HAGC1EgAVQuh2jgHEdBOdbHvfFAhxa6LxeZG5_kMuwA"

    MRS_SESSION = "YjI2MWM5ZDgtNzdmMi00Y2ZhLTk4NDAtNjhjN2RmNjBhNTEx"
    
    # 테스터 생성
    tester = AgentTester(BEARER_TOKEN, CMS_TOKEN, MRS_SESSION)
    
    # ============================================================
    # 방법 1: 단일 테스트
    # ============================================================
    # tester.run_test("이전 채용을 복사해서 새로운 채용 만들어줘")
    
    # ============================================================
    # 방법 2: 배치 테스트 (질의 목록)
    # ============================================================
    queries = [
        "JOBDA 연동 설정",
        "역량검사 볼 때 본인인증 하게 해줘",
        "역검 본인인증 설정",
        "역량검사 접속 몇 번까지 허용할지 설정할게",
        "역량검사 재접속 횟수를 제한하고 싶어",
        "채용 사이트에서 역량검사 안내 문구 수정",
        "역검 사이트 설정",
        "응시자 사이트 로고나 색상 변경하고 싶어",
        "수험자 사이트 설정",
        "역검 종류 설정",
        "수험자 옵션 설정",
        "결과 점수 가중치를 다르게 주고 싶어",
        "점수 반영 비율 설정",
        "결과표에서 직군 대표 구성원 비교 설정",
        "유사 구성원 비교 콘텐츠 켜고 싶어",
        "역량검사 결과 리포트 콘텐츠 설정",
        "역검 결과 화면 설정",
        "우리 회사가 중요하게 보는 관심 역량 설정",
        "AI 면접 가이드 같은 콘텐츠 설정할래",
        "AI 분석 설정",
        "면접 방식을 화상면접으로 바꾸고 싶어",
        "대면 면접으로 변경",
        "비대면 면접 설정",
        "면접 진행 기간 설정해줘",
        "면접 일정 조율 기능 사용하고 싶어",
        "면접 스케줄 조정",
        "면접비 지급 여부 설정할게",
        "교통비 지급 설정",
        "면접 때 수험표 뽑아가야 하는지 설정",
        "면접 확인서 발급 가능하게 해줘",
        "참석 확인서 설정",
        "면접관 배정하러 가기",
        "누가 면접할지 설정",
    ]
    
    tester.run_batch_test(queries, delay=1.0)
    
    # ============================================================
    # 방법 3: 대화형 모드 (수동 입력)
    # ============================================================
    # while True:
    #     query = input("\n질의 입력 (q=종료, s=저장): ").strip()
    #     if query.lower() == 'q':
    #         break
    #     elif query.lower() == 's':
    #         tester.save_results()
    #     elif query:
    #         tester.run_test(query)