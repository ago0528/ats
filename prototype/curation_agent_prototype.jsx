import React, { useState, useEffect, useRef } from "react";

const CurationAgentV2 = () => {
  // 대화 시나리오 정의 - 자연스러운 흐름
  const conversationScenario = [
    {
      id: "welcome",
      type: "assistant",
      content:
        "안녕하세요! 채용 계획을 함께 세워볼게요.\n\n새로운 채용을 준비 중이시라면, 어떤 포지션을 뽑으실 계획인지 편하게 말씀해주세요.",
      delay: 0,
    },
    {
      id: "user-1",
      type: "user",
      content:
        "2026년 1월 3주부터 2개월 동안 기획자, 개발자 상시 채용할 계획이야",
      trigger: "welcome",
    },
    {
      id: "ack-1",
      type: "assistant",
      content:
        "기획자, 개발자 채용이시군요. 1월 3주 시작해서 3월 중순까지로 잡아둘게요.\n\n혹시 각 포지션별로 몇 명 정도 생각하고 계세요?\n신입/경력 선호도 있으시면 같이 말씀해주세요.",
      delay: 1200,
      updatePanel: { step: 1 },
    },
    {
      id: "user-2",
      type: "user",
      content: "기획자 1명, 개발자는 2~3명. 경력직 위주로",
      trigger: "ack-1",
    },
    {
      id: "ack-2",
      type: "assistant",
      content:
        "네, 경력직 중심으로 기획자 1명, 개발자 2~3명이요.\n\n이번 채용이 기존 인원 충원인가요, 아니면 새로운 프로젝트 때문인가요?\n→ 어떤 '역량'이 중요한지 파악하는 데 도움이 돼서요.",
      delay: 1200,
      updatePanel: { step: 2 },
    },
    {
      id: "user-3",
      type: "user",
      content: "신규 서비스 론칭 때문에 팀 확장하는 거야",
      trigger: "ack-2",
    },
    {
      id: "ack-3",
      type: "assistant",
      content:
        '신규 서비스 론칭이시구나요.\n그러면 "0에서 1을 만들어본 경험"이 핵심 역량이 되겠네요.\n\n한 가지 여쭤볼게요.\n개발자분들 뽑으실 때 보통 어떤 기준으로 서류 검토하세요?',
      delay: 1200,
      updatePanel: { step: 3 },
    },
    {
      id: "user-4",
      type: "user",
      content: "음... 경력 연차랑 학력? 그리고 이전 회사 보는 편이야",
      trigger: "ack-3",
    },
    {
      id: "transition",
      type: "assistant",
      content:
        "솔직하게 말씀해주셔서 감사해요.\n사실 많은 분들이 그렇게 하시는데, 한번 같이 살펴볼 게 있어요.",
      delay: 1200,
      isPlanModeStart: true,
    },
    {
      id: "diagnosis",
      type: "assistant",
      content: null,
      delay: 800,
      isDiagnosis: true,
      diagnosisData: {
        title: "과거 채용 데이터를 분석해봤어요",
        subtitle: "작년 9월 개발자 채용 결과",
        metrics: {
          applicants: 82,
          passed: 10,
          hired: 2,
          passRate: "12%",
          hireRate: "2.4%",
        },
        findings: [
          {
            label: "합격한 2명의 공통점",
            items: [
              {
                key: "학력",
                value: "1명 4년제, 1명 전문대",
                highlight: "학력 무관",
              },
              { key: "경력", value: "2년, 4년", highlight: "연차 무관" },
              {
                key: "공통 역량",
                value: "문제해결력 상위 15%, 협업 역량 상위 20%",
                highlight: true,
              },
            ],
          },
        ],
        insight:
          '서류에서 탈락한 72명 중\n역량검사 기준으로 보면 "합격자와 비슷한 역량"을 가진 분이\n최소 8명은 있었을 거예요.',
        conclusion: "즉, 스펙 기준으로 좋은 사람을 놓쳤을 가능성이 있어요.",
      },
      updatePanel: { step: 4, showDiagnosis: true },
    },
    {
      id: "user-5",
      type: "user",
      content: "헐 그래? 그럼 어떻게 해야 돼?",
      trigger: "diagnosis",
    },
    {
      id: "proposal",
      type: "assistant",
      content: null,
      delay: 1000,
      isProposal: true,
      proposalData: {
        title: "이번 채용에서 한 가지 실험을 제안드려요",
        comparison: {
          before: {
            label: "기존",
            flow: ["지원", "서류(스펙)", "면접", "합격"],
            problem: "72명 탈락 (좋은 인재 포함 가능성)",
          },
          after: {
            label: "제안",
            flow: ["지원", "역량검사", "서류(역량 기반)", "면접", "합격"],
            benefit: "스펙에 가려진 인재 발굴",
          },
        },
      },
    },
    {
      id: "competency-detail",
      type: "assistant",
      content: null,
      delay: 600,
      isCompetencyDetail: true,
      competencyData: {
        title: "이번 채용에 적용하면?",
        positions: [
          {
            name: "개발자",
            icon: "👨‍💻",
            competencies: [
              {
                name: "문제해결력",
                desc: "정의되지 않은 문제를 스스로 구조화",
              },
              { name: "학습민첩성", desc: "새로운 기술 스택 빠르게 습득" },
              { name: "협업 역량", desc: "기획/디자인과 긴밀한 소통" },
            ],
          },
          {
            name: "기획자",
            icon: "📊",
            competencies: [
              { name: "분석적 사고", desc: "데이터 기반 의사결정" },
              { name: "커뮤니케이션", desc: "이해관계자 설득 및 조율" },
              { name: "실행력", desc: "불확실한 상황에서 빠른 실행" },
            ],
          },
        ],
        note: '이 역량들을 1차 스크리닝 기준으로 쓰면,\n"경력 2년이지만 역량 뛰어난 사람"도 면접까지 올라와요.',
      },
      updatePanel: { step: 5, showCompetencies: true },
    },
    {
      id: "user-6",
      type: "user",
      content: "오... 근데 이렇게 하면 실제로 효과가 있어?",
      trigger: "competency-detail",
    },
    {
      id: "evidence",
      type: "assistant",
      content: null,
      delay: 1200,
      isEvidence: true,
      evidenceData: {
        title: "역량 중심 채용 도입 효과",
        subtitle: "실제 사례",
        cases: [
          {
            company: "B사",
            context: "개발자 채용 (2025년 상반기)",
            metrics: [
              { label: "서류 통과율", before: "15%", after: "28%" },
              { label: "입사 후 3개월 이탈률", before: "18%", after: "6%" },
              { label: "채용 소요 기간", before: "52일", after: "38일" },
            ],
            change:
              '"학력/경력 기준"에서 "역량검사 + 포트폴리오 기준"으로 전환\n→ 지원자 풀 다양화, 실제 업무 적합도 향상',
          },
        ],
        testimonial: {
          quote:
            "채용 담당자가 서류 보는 시간이 절반으로 줄었어요. 역량검사 결과로 1차 필터링하니까 '봐야 할 사람'만 집중해서 볼 수 있더라고요.",
          source: "C사 인사팀장",
        },
        prediction: {
          title: "귀사에 적용 시 예상 효과",
          items: [
            { label: "서류 검토 시간", value: "50% 단축", icon: "⏱️" },
            { label: "적합 인재 발굴률", value: "2배 향상", icon: "🎯" },
            { label: "입사 후 조기 이탈", value: "60% 감소", icon: "📉" },
          ],
          note: "* 과거 데이터 + 업계 평균 기반 추정치예요. 실제 결과는 달라질 수 있어요.",
        },
      },
      updatePanel: { step: 6, showEvidence: true },
    },
    {
      id: "user-7",
      type: "user",
      content: "좋아. 이 방식으로 해보자",
      trigger: "evidence",
    },
    {
      id: "final",
      type: "assistant",
      content:
        "좋아요! 지금까지 나눈 내용으로 채용 계획서를 만들었어요.\n우측 패널에서 확인해보세요.",
      delay: 800,
      isFinal: true,
    },
    {
      id: "final-summary",
      type: "assistant",
      content: null,
      delay: 600,
      isFinalSummary: true,
      summaryData: {
        title: "이번 채용에서 달라지는 것",
        changes: [
          {
            category: "전형 순서 변경",
            before: "서류 → 면접",
            after: "역량검사 → 서류 → 면접",
          },
          {
            category: "서류 평가 기준 변경",
            before: "학력, 경력 연차, 이전 회사",
            after: "역량검사 결과 + 프로젝트 경험 + 기술스택 적합도",
          },
          {
            category: "블라인드 옵션 적용",
            before: null,
            after: "출신학교, 사진 블라인드 ON\n→ 역량에만 집중할 수 있는 환경",
          },
        ],
        tips: [
          "공고에 \"역량 중심 채용\" 문구를 넣으면 지원자들도 '스펙보다 실력으로 평가받겠구나' 기대하고 지원해요.\n→ 다양한 배경의 우수 인재 유입 효과",
          "역량검사는 지원 직후 자동 발송되도록 설정할게요. 응시 완료된 분들만 서류 검토 대상이 돼서 효율적이에요.",
        ],
      },
      updatePanel: { step: 7, showFinal: true },
      hasConfirmButton: true,
    },
  ];

  const [currentScenarioIndex, setCurrentScenarioIndex] = useState(0);
  const [messages, setMessages] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  const [isPlanMode, setIsPlanMode] = useState(false);
  const [panelStep, setPanelStep] = useState(0);
  const [panelData, setPanelData] = useState({
    showDiagnosis: false,
    showCompetencies: false,
    showEvidence: false,
    showFinal: false,
  });
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 초기 메시지 로드
  useEffect(() => {
    const welcomeMsg = conversationScenario[0];
    setMessages([{ ...welcomeMsg, timestamp: new Date() }]);
    setCurrentScenarioIndex(1);
  }, []);

  const addMessage = (msg) => {
    setMessages((prev) => [...prev, { ...msg, timestamp: new Date() }]);
  };

  const handleNextMessage = () => {
    if (currentScenarioIndex >= conversationScenario.length) return;

    const currentMsg = conversationScenario[currentScenarioIndex];

    if (currentMsg.type === "user") {
      addMessage(currentMsg);
      setCurrentScenarioIndex((prev) => prev + 1);

      // 다음 assistant 메시지들 자동 재생
      setTimeout(() => {
        playAssistantMessages(currentScenarioIndex + 1);
      }, 500);
    }
  };

  const playAssistantMessages = (startIndex) => {
    let index = startIndex;

    const playNext = () => {
      if (index >= conversationScenario.length) return;

      const msg = conversationScenario[index];
      if (msg.type !== "assistant") {
        setCurrentScenarioIndex(index);
        return;
      }

      setIsTyping(true);

      setTimeout(() => {
        setIsTyping(false);
        addMessage(msg);

        if (msg.isPlanModeStart) {
          setIsPlanMode(true);
        }

        if (msg.updatePanel) {
          setPanelStep(msg.updatePanel.step);
          setPanelData((prev) => ({
            ...prev,
            showDiagnosis: msg.updatePanel.showDiagnosis || prev.showDiagnosis,
            showCompetencies:
              msg.updatePanel.showCompetencies || prev.showCompetencies,
            showEvidence: msg.updatePanel.showEvidence || prev.showEvidence,
            showFinal: msg.updatePanel.showFinal || prev.showFinal,
          }));
        }

        index++;

        // 다음 메시지도 assistant면 계속 재생
        if (
          index < conversationScenario.length &&
          conversationScenario[index].type === "assistant"
        ) {
          setTimeout(playNext, conversationScenario[index].delay || 800);
        } else {
          setCurrentScenarioIndex(index);
        }
      }, msg.delay || 1200);
    };

    playNext();
  };

  const isUserTurn =
    currentScenarioIndex < conversationScenario.length &&
    conversationScenario[currentScenarioIndex].type === "user";

  const nextUserMessage = isUserTurn
    ? conversationScenario[currentScenarioIndex]
    : null;

  return (
    <div
      style={{
        display: "flex",
        height: "100vh",
        width: "100vw",
        backgroundColor: "#09090b",
        fontFamily:
          '"Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont, system-ui, sans-serif',
        color: "#fafafa",
        overflow: "hidden",
      }}
    >
      {/* 좌측 사이드바 */}
      <div
        style={{
          width: "260px",
          backgroundColor: "#0f0f12",
          borderRight: "1px solid rgba(255,255,255,0.06)",
          display: "flex",
          flexDirection: "column",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            padding: "20px 24px",
            borderBottom: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "10px",
                background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "18px",
                fontWeight: "700",
                color: "white",
              }}
            >
              H
            </div>
            <div>
              <div style={{ fontSize: "15px", fontWeight: "600" }}>
                채용에이전트
              </div>
              <div
                style={{
                  fontSize: "11px",
                  color: "rgba(255,255,255,0.4)",
                  marginTop: "2px",
                }}
              >
                역량 중심 채용
              </div>
            </div>
          </div>
        </div>

        <div style={{ padding: "16px 12px", flex: 1 }}>
          <div
            style={{
              padding: "10px 12px",
              borderRadius: "8px",
              backgroundColor: "rgba(59, 130, 246, 0.15)",
              color: "#93c5fd",
              fontSize: "13px",
              fontWeight: "500",
              display: "flex",
              alignItems: "center",
              gap: "10px",
              marginBottom: "4px",
            }}
          >
            <span>💬</span> 새 대화
          </div>
          {["📋 진행중인 채용", "👥 인재풀", "📊 분석"].map((item, idx) => (
            <div
              key={idx}
              style={{
                padding: "10px 12px",
                borderRadius: "8px",
                color: "rgba(255,255,255,0.5)",
                fontSize: "13px",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              {item}
            </div>
          ))}
        </div>

        <div
          style={{
            padding: "16px",
            borderTop: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              padding: "8px",
            }}
          >
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "50%",
                backgroundColor: "#27272a",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "14px",
              }}
            >
              👤
            </div>
            <div>
              <div style={{ fontSize: "13px", fontWeight: "500" }}>김가온</div>
              <div style={{ fontSize: "11px", color: "rgba(255,255,255,0.4)" }}>
                채용담당자
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 메인 채팅 영역 */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
          position: "relative",
        }}
      >
        {/* 큐레이팅 모드 배너 */}
        {isPlanMode && (
          <div
            style={{
              padding: "12px 24px",
              background:
                "linear-gradient(90deg, rgba(59, 130, 246, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%)",
              borderBottom: "1px solid rgba(59, 130, 246, 0.2)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <div
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  backgroundColor: "#22c55e",
                  boxShadow: "0 0 8px rgba(34, 197, 94, 0.5)",
                  animation: "pulse 2s infinite",
                }}
              />
              <span
                style={{
                  fontSize: "13px",
                  color: "#93c5fd",
                  fontWeight: "500",
                }}
              >
                플랜 모드 활성화
              </span>
              <span
                style={{ fontSize: "13px", color: "rgba(255,255,255,0.3)" }}
              >
                |
              </span>
              <span
                style={{ fontSize: "13px", color: "rgba(255,255,255,0.6)" }}
              >
                개발자 2~3명, 기획자 1명 채용
              </span>
            </div>
          </div>
        )}

        {/* 채팅 메시지 영역 */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "24px",
            paddingBottom: "120px",
          }}
        >
          <div style={{ maxWidth: "720px", margin: "0 auto" }}>
            {messages.map((message, idx) => (
              <MessageBubble key={idx} message={message} />
            ))}

            {isTyping && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* 입력 영역 */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            padding: "20px 24px",
            background: "linear-gradient(to top, #09090b 80%, transparent)",
          }}
        >
          <div style={{ maxWidth: "720px", margin: "0 auto" }}>
            {nextUserMessage && (
              <button
                onClick={handleNextMessage}
                disabled={isTyping}
                style={{
                  width: "100%",
                  padding: "16px 20px",
                  borderRadius: "16px",
                  border: "1px solid rgba(59, 130, 246, 0.3)",
                  backgroundColor: "rgba(59, 130, 246, 0.1)",
                  color: "#93c5fd",
                  fontSize: "14px",
                  textAlign: "left",
                  cursor: isTyping ? "not-allowed" : "pointer",
                  opacity: isTyping ? 0.5 : 1,
                  transition: "all 0.2s",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <span>💬 "{nextUserMessage.content}"</span>
                <span
                  style={{ fontSize: "12px", color: "rgba(255,255,255,0.4)" }}
                >
                  클릭하여 전송
                </span>
              </button>
            )}
            {!nextUserMessage &&
              currentScenarioIndex >= conversationScenario.length && (
                <div
                  style={{
                    padding: "16px 20px",
                    borderRadius: "16px",
                    backgroundColor: "#18181b",
                    border: "1px solid rgba(255,255,255,0.1)",
                    textAlign: "center",
                    color: "rgba(255,255,255,0.5)",
                    fontSize: "14px",
                  }}
                >
                  ✅ 데모 시나리오가 완료되었습니다
                </div>
              )}
          </div>
        </div>
      </div>

      {/* 우측 패널 - 채용 계획서 */}
      <div
        style={{
          width: isPlanMode ? "520px" : "0px",
          backgroundColor: "#0f0f12",
          borderLeft: isPlanMode ? "1px solid rgba(255,255,255,0.06)" : "none",
          transition: "width 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
          overflow: "hidden",
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
        }}
      >
        {isPlanMode && <PlanPanel step={panelStep} data={panelData} />}
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); }
          40% { transform: translateY(-6px); }
        }
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes slideInRight {
          from { opacity: 0; transform: translateX(20px); }
          to { opacity: 1; transform: translateX(0); }
        }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
      `}</style>
    </div>
  );
};

// 메시지 버블 컴포넌트
const MessageBubble = ({ message }) => {
  if (message.type === "user") {
    return (
      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          marginBottom: "20px",
          animation: "fadeInUp 0.3s ease",
        }}
      >
        <div
          style={{
            padding: "14px 18px",
            backgroundColor: "#3b82f6",
            borderRadius: "18px",
            borderBottomRightRadius: "4px",
            fontSize: "14px",
            lineHeight: "1.6",
            color: "white",
            maxWidth: "75%",
          }}
        >
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "12px",
        marginBottom: "20px",
        animation: "fadeInUp 0.3s ease",
      }}
    >
      <div
        style={{
          width: "32px",
          height: "32px",
          borderRadius: "10px",
          background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: "14px",
          flexShrink: 0,
        }}
      >
        🤖
      </div>

      <div style={{ flex: 1, maxWidth: "calc(100% - 44px)" }}>
        {message.isPlanModeStart && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "4px 10px",
              backgroundColor: "rgba(34, 197, 94, 0.15)",
              borderRadius: "4px",
              marginBottom: "8px",
            }}
          >
            <span style={{ fontSize: "12px" }}>✨</span>
            <span
              style={{ fontSize: "11px", color: "#4ade80", fontWeight: "500" }}
            >
              플랜 모드 시작
            </span>
          </div>
        )}

        {message.content && (
          <div
            style={{
              padding: "14px 18px",
              backgroundColor: "#18181b",
              borderRadius: "18px",
              borderTopLeftRadius: "4px",
              fontSize: "14px",
              lineHeight: "1.7",
              whiteSpace: "pre-wrap",
            }}
          >
            {message.content}
          </div>
        )}

        {message.isDiagnosis && <DiagnosisCard data={message.diagnosisData} />}
        {message.isProposal && <ProposalCard data={message.proposalData} />}
        {message.isCompetencyDetail && (
          <CompetencyCard data={message.competencyData} />
        )}
        {message.isEvidence && <EvidenceCard data={message.evidenceData} />}
        {message.isFinalSummary && (
          <FinalSummaryCard
            data={message.summaryData}
            hasConfirmButton={message.hasConfirmButton}
          />
        )}
      </div>
    </div>
  );
};

// 진단 카드
const DiagnosisCard = ({ data }) => (
  <div
    style={{
      marginTop: "12px",
      padding: "20px",
      backgroundColor: "rgba(239, 68, 68, 0.08)",
      border: "1px solid rgba(239, 68, 68, 0.2)",
      borderRadius: "16px",
      animation: "fadeInUp 0.4s ease",
    }}
  >
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        marginBottom: "16px",
      }}
    >
      <span style={{ fontSize: "18px" }}>📊</span>
      <span style={{ fontSize: "15px", fontWeight: "600", color: "#fca5a5" }}>
        {data.title}
      </span>
    </div>

    <div
      style={{
        padding: "16px",
        backgroundColor: "rgba(0,0,0,0.3)",
        borderRadius: "12px",
        marginBottom: "16px",
      }}
    >
      <div
        style={{
          fontSize: "12px",
          color: "rgba(255,255,255,0.5)",
          marginBottom: "12px",
        }}
      >
        {data.subtitle}
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          fontSize: "13px",
          color: "rgba(255,255,255,0.7)",
        }}
      >
        <span>
          지원자{" "}
          <strong style={{ color: "#fafafa" }}>
            {data.metrics.applicants}명
          </strong>
        </span>
        <span style={{ color: "rgba(255,255,255,0.3)" }}>→</span>
        <span>
          서류 통과{" "}
          <strong style={{ color: "#fafafa" }}>{data.metrics.passed}명</strong>
        </span>
        <span style={{ color: "rgba(255,255,255,0.3)" }}>→</span>
        <span>
          합격{" "}
          <strong style={{ color: "#fafafa" }}>{data.metrics.hired}명</strong>
        </span>
      </div>
      <div
        style={{
          display: "flex",
          gap: "16px",
          marginTop: "12px",
          fontSize: "12px",
          color: "rgba(255,255,255,0.5)",
        }}
      >
        <span>
          서류 통과율{" "}
          <strong style={{ color: "#fca5a5" }}>{data.metrics.passRate}</strong>
        </span>
        <span>
          최종 합격률{" "}
          <strong style={{ color: "#fca5a5" }}>{data.metrics.hireRate}</strong>
        </span>
      </div>
    </div>

    <div style={{ marginBottom: "16px" }}>
      <div
        style={{
          fontSize: "13px",
          fontWeight: "600",
          color: "#fafafa",
          marginBottom: "12px",
        }}
      >
        그런데 흥미로운 점이 있어요
      </div>
      {data.findings.map((finding, idx) => (
        <div key={idx}>
          <div
            style={{
              fontSize: "12px",
              color: "rgba(255,255,255,0.5)",
              marginBottom: "8px",
            }}
          >
            {finding.label}
          </div>
          {finding.items.map((item, iIdx) => (
            <div
              key={iIdx}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "8px 12px",
                backgroundColor:
                  item.highlight === true
                    ? "rgba(34, 197, 94, 0.15)"
                    : "rgba(255,255,255,0.03)",
                borderRadius: "8px",
                marginBottom: "6px",
                fontSize: "13px",
              }}
            >
              <span
                style={{ color: "rgba(255,255,255,0.5)", minWidth: "60px" }}
              >
                {item.key}
              </span>
              <span style={{ color: "#fafafa" }}>{item.value}</span>
              {item.highlight && typeof item.highlight === "string" && (
                <span
                  style={{
                    padding: "2px 8px",
                    backgroundColor: "rgba(251, 191, 36, 0.2)",
                    borderRadius: "4px",
                    fontSize: "11px",
                    color: "#fbbf24",
                    marginLeft: "auto",
                  }}
                >
                  {item.highlight}
                </span>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>

    <div
      style={{
        padding: "14px 16px",
        backgroundColor: "rgba(251, 191, 36, 0.1)",
        border: "1px solid rgba(251, 191, 36, 0.2)",
        borderRadius: "10px",
        marginBottom: "12px",
      }}
    >
      <div
        style={{
          fontSize: "13px",
          lineHeight: "1.6",
          color: "rgba(255,255,255,0.8)",
          whiteSpace: "pre-wrap",
        }}
      >
        {data.insight}
      </div>
    </div>

    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: "12px 16px",
        backgroundColor: "rgba(239, 68, 68, 0.15)",
        borderRadius: "10px",
      }}
    >
      <span style={{ fontSize: "16px" }}>💡</span>
      <span style={{ fontSize: "14px", fontWeight: "600", color: "#fca5a5" }}>
        {data.conclusion}
      </span>
    </div>
  </div>
);

// 제안 카드
const ProposalCard = ({ data }) => (
  <div
    style={{
      marginTop: "12px",
      padding: "20px",
      backgroundColor: "rgba(59, 130, 246, 0.08)",
      border: "1px solid rgba(59, 130, 246, 0.2)",
      borderRadius: "16px",
      animation: "fadeInUp 0.4s ease",
    }}
  >
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        marginBottom: "20px",
      }}
    >
      <span style={{ fontSize: "18px" }}>🔄</span>
      <span style={{ fontSize: "15px", fontWeight: "600", color: "#93c5fd" }}>
        {data.title}
      </span>
    </div>

    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* 기존 방식 */}
      <div
        style={{
          padding: "16px",
          backgroundColor: "rgba(239, 68, 68, 0.08)",
          border: "1px solid rgba(239, 68, 68, 0.15)",
          borderRadius: "12px",
        }}
      >
        <div
          style={{
            fontSize: "12px",
            color: "#fca5a5",
            fontWeight: "600",
            marginBottom: "12px",
          }}
        >
          [{data.comparison.before.label}]
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            flexWrap: "wrap",
            marginBottom: "12px",
          }}
        >
          {data.comparison.before.flow.map((step, idx) => (
            <React.Fragment key={idx}>
              <span
                style={{
                  padding: "6px 12px",
                  backgroundColor: "rgba(255,255,255,0.05)",
                  borderRadius: "6px",
                  fontSize: "13px",
                }}
              >
                {step}
              </span>
              {idx < data.comparison.before.flow.length - 1 && (
                <span style={{ color: "rgba(255,255,255,0.3)" }}>→</span>
              )}
            </React.Fragment>
          ))}
        </div>
        <div
          style={{
            fontSize: "12px",
            color: "#fca5a5",
            display: "flex",
            alignItems: "center",
            gap: "6px",
          }}
        >
          <span>↓</span>
          <span>{data.comparison.before.problem}</span>
        </div>
      </div>

      {/* 제안 방식 */}
      <div
        style={{
          padding: "16px",
          backgroundColor: "rgba(34, 197, 94, 0.08)",
          border: "1px solid rgba(34, 197, 94, 0.2)",
          borderRadius: "12px",
        }}
      >
        <div
          style={{
            fontSize: "12px",
            color: "#4ade80",
            fontWeight: "600",
            marginBottom: "12px",
          }}
        >
          [{data.comparison.after.label}]
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            flexWrap: "wrap",
            marginBottom: "12px",
          }}
        >
          {data.comparison.after.flow.map((step, idx) => (
            <React.Fragment key={idx}>
              <span
                style={{
                  padding: "6px 12px",
                  backgroundColor:
                    step === "역량검사"
                      ? "rgba(34, 197, 94, 0.2)"
                      : "rgba(255,255,255,0.05)",
                  border:
                    step === "역량검사"
                      ? "1px solid rgba(34, 197, 94, 0.3)"
                      : "none",
                  borderRadius: "6px",
                  fontSize: "13px",
                  color: step === "역량검사" ? "#4ade80" : "#fafafa",
                }}
              >
                {step}
                {step === "역량검사" && " ⭐"}
              </span>
              {idx < data.comparison.after.flow.length - 1 && (
                <span style={{ color: "rgba(255,255,255,0.3)" }}>→</span>
              )}
            </React.Fragment>
          ))}
        </div>
        <div
          style={{
            fontSize: "12px",
            color: "#4ade80",
            display: "flex",
            alignItems: "center",
            gap: "6px",
          }}
        >
          <span>→</span>
          <span>{data.comparison.after.benefit}</span>
        </div>
      </div>
    </div>
  </div>
);

// 역량 상세 카드
const CompetencyCard = ({ data }) => (
  <div
    style={{
      marginTop: "12px",
      padding: "20px",
      backgroundColor: "rgba(139, 92, 246, 0.08)",
      border: "1px solid rgba(139, 92, 246, 0.2)",
      borderRadius: "16px",
      animation: "fadeInUp 0.4s ease",
    }}
  >
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        marginBottom: "20px",
      }}
    >
      <span style={{ fontSize: "18px" }}>🎯</span>
      <span style={{ fontSize: "15px", fontWeight: "600", color: "#c4b5fd" }}>
        {data.title}
      </span>
    </div>

    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "16px",
        marginBottom: "16px",
      }}
    >
      {data.positions.map((pos, idx) => (
        <div
          key={idx}
          style={{
            padding: "16px",
            backgroundColor: "rgba(0,0,0,0.2)",
            borderRadius: "12px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              marginBottom: "12px",
              fontSize: "14px",
              fontWeight: "600",
            }}
          >
            <span>{pos.icon}</span>
            <span>{pos.name} 포지션 핵심 역량</span>
            <span style={{ fontSize: "11px", color: "rgba(255,255,255,0.4)" }}>
              (신규 서비스 기준)
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {pos.competencies.map((comp, cIdx) => (
              <div
                key={cIdx}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: "10px 14px",
                  backgroundColor: "rgba(139, 92, 246, 0.1)",
                  borderRadius: "8px",
                }}
              >
                <span
                  style={{
                    fontWeight: "600",
                    color: "#c4b5fd",
                    fontSize: "13px",
                    minWidth: "80px",
                  }}
                >
                  {comp.name}
                </span>
                <span
                  style={{
                    fontSize: "12px",
                    color: "rgba(255,255,255,0.6)",
                  }}
                >
                  — {comp.desc}
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>

    <div
      style={{
        padding: "14px 16px",
        backgroundColor: "rgba(34, 197, 94, 0.1)",
        border: "1px solid rgba(34, 197, 94, 0.2)",
        borderRadius: "10px",
        fontSize: "13px",
        lineHeight: "1.6",
        color: "rgba(255,255,255,0.8)",
        whiteSpace: "pre-wrap",
      }}
    >
      💡 {data.note}
    </div>
  </div>
);

// 근거 카드
const EvidenceCard = ({ data }) => (
  <div
    style={{
      marginTop: "12px",
      padding: "20px",
      backgroundColor: "rgba(34, 197, 94, 0.08)",
      border: "1px solid rgba(34, 197, 94, 0.2)",
      borderRadius: "16px",
      animation: "fadeInUp 0.4s ease",
    }}
  >
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        marginBottom: "8px",
      }}
    >
      <span style={{ fontSize: "18px" }}>📈</span>
      <span style={{ fontSize: "15px", fontWeight: "600", color: "#4ade80" }}>
        {data.title}
      </span>
    </div>
    <div
      style={{
        fontSize: "12px",
        color: "rgba(255,255,255,0.5)",
        marginBottom: "20px",
      }}
    >
      {data.subtitle}
    </div>

    {data.cases.map((caseItem, idx) => (
      <div
        key={idx}
        style={{
          padding: "16px",
          backgroundColor: "rgba(0,0,0,0.2)",
          borderRadius: "12px",
          marginBottom: "16px",
        }}
      >
        <div
          style={{ fontSize: "14px", fontWeight: "600", marginBottom: "4px" }}
        >
          {caseItem.company}
        </div>
        <div
          style={{
            fontSize: "12px",
            color: "rgba(255,255,255,0.5)",
            marginBottom: "16px",
          }}
        >
          {caseItem.context}
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "8px",
            marginBottom: "16px",
          }}
        >
          {caseItem.metrics.map((metric, mIdx) => (
            <div
              key={mIdx}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
                padding: "10px 14px",
                backgroundColor: "rgba(255,255,255,0.03)",
                borderRadius: "8px",
                fontSize: "13px",
              }}
            >
              <span style={{ color: "rgba(255,255,255,0.6)", flex: 1 }}>
                {metric.label}
              </span>
              <span style={{ color: "#fca5a5" }}>{metric.before}</span>
              <span style={{ color: "rgba(255,255,255,0.3)" }}>→</span>
              <span style={{ color: "#4ade80", fontWeight: "600" }}>
                {metric.after}
              </span>
            </div>
          ))}
        </div>

        <div
          style={{
            padding: "12px 14px",
            backgroundColor: "rgba(59, 130, 246, 0.1)",
            borderRadius: "8px",
            fontSize: "12px",
            lineHeight: "1.5",
            color: "rgba(255,255,255,0.7)",
            whiteSpace: "pre-wrap",
          }}
        >
          <strong style={{ color: "#93c5fd" }}>핵심 변화:</strong>{" "}
          {caseItem.change}
        </div>
      </div>
    ))}

    {data.testimonial && (
      <div
        style={{
          padding: "16px",
          backgroundColor: "rgba(255,255,255,0.03)",
          borderLeft: "3px solid rgba(139, 92, 246, 0.5)",
          borderRadius: "0 12px 12px 0",
          marginBottom: "20px",
        }}
      >
        <div
          style={{
            fontSize: "13px",
            lineHeight: "1.6",
            color: "rgba(255,255,255,0.8)",
            fontStyle: "italic",
            marginBottom: "8px",
          }}
        >
          "{data.testimonial.quote}"
        </div>
        <div style={{ fontSize: "12px", color: "rgba(255,255,255,0.5)" }}>
          — {data.testimonial.source}
        </div>
      </div>
    )}

    <div
      style={{
        padding: "16px",
        backgroundColor: "rgba(34, 197, 94, 0.1)",
        border: "1px solid rgba(34, 197, 94, 0.2)",
        borderRadius: "12px",
      }}
    >
      <div
        style={{
          fontSize: "14px",
          fontWeight: "600",
          color: "#4ade80",
          marginBottom: "16px",
        }}
      >
        🎯 {data.prediction.title}
      </div>
      <div style={{ display: "flex", gap: "12px", marginBottom: "12px" }}>
        {data.prediction.items.map((item, idx) => (
          <div
            key={idx}
            style={{
              flex: 1,
              padding: "14px",
              backgroundColor: "rgba(0,0,0,0.2)",
              borderRadius: "10px",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: "20px", marginBottom: "8px" }}>
              {item.icon}
            </div>
            <div
              style={{
                fontSize: "11px",
                color: "rgba(255,255,255,0.5)",
                marginBottom: "4px",
              }}
            >
              {item.label}
            </div>
            <div
              style={{ fontSize: "16px", fontWeight: "700", color: "#4ade80" }}
            >
              {item.value}
            </div>
          </div>
        ))}
      </div>
      <div style={{ fontSize: "11px", color: "rgba(255,255,255,0.4)" }}>
        {data.prediction.note}
      </div>
    </div>
  </div>
);

// 최종 요약 카드
const FinalSummaryCard = ({ data, hasConfirmButton }) => (
  <div
    style={{
      marginTop: "12px",
      animation: "fadeInUp 0.4s ease",
    }}
  >
    <div
      style={{
        padding: "20px",
        backgroundColor: "rgba(59, 130, 246, 0.08)",
        border: "1px solid rgba(59, 130, 246, 0.2)",
        borderRadius: "16px",
        marginBottom: "12px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          marginBottom: "20px",
        }}
      >
        <span style={{ fontSize: "18px" }}>✅</span>
        <span style={{ fontSize: "15px", fontWeight: "600", color: "#93c5fd" }}>
          {data.title}
        </span>
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "12px",
          marginBottom: "20px",
        }}
      >
        {data.changes.map((change, idx) => (
          <div
            key={idx}
            style={{
              padding: "14px 16px",
              backgroundColor: "rgba(0,0,0,0.2)",
              borderRadius: "12px",
            }}
          >
            <div
              style={{
                fontSize: "13px",
                fontWeight: "600",
                color: "#93c5fd",
                marginBottom: "10px",
              }}
            >
              {idx + 1}. {change.category}
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "12px",
                fontSize: "13px",
              }}
            >
              {change.before && (
                <>
                  <div style={{ color: "rgba(255,255,255,0.5)" }}>
                    <span style={{ color: "#fca5a5" }}>[기존]</span>{" "}
                    {change.before}
                  </div>
                  <span style={{ color: "rgba(255,255,255,0.3)" }}>→</span>
                </>
              )}
              <div style={{ color: "#fafafa", whiteSpace: "pre-wrap" }}>
                <span style={{ color: "#4ade80" }}>[변경]</span> {change.after}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>

    <div
      style={{
        padding: "20px",
        backgroundColor: "rgba(251, 191, 36, 0.08)",
        border: "1px solid rgba(251, 191, 36, 0.2)",
        borderRadius: "16px",
        marginBottom: "16px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          marginBottom: "16px",
        }}
      >
        <span style={{ fontSize: "18px" }}>💡</span>
        <span style={{ fontSize: "15px", fontWeight: "600", color: "#fcd34d" }}>
          추가 제안
        </span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {data.tips.map((tip, idx) => (
          <div
            key={idx}
            style={{
              padding: "12px 14px",
              backgroundColor: "rgba(0,0,0,0.2)",
              borderRadius: "10px",
              fontSize: "13px",
              lineHeight: "1.6",
              color: "rgba(255,255,255,0.8)",
              whiteSpace: "pre-wrap",
            }}
          >
            • {tip}
          </div>
        ))}
      </div>
    </div>

    {hasConfirmButton && (
      <button
        style={{
          width: "100%",
          padding: "16px 24px",
          borderRadius: "12px",
          border: "none",
          background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
          color: "white",
          fontSize: "15px",
          fontWeight: "600",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "8px",
          boxShadow: "0 4px 20px rgba(59, 130, 246, 0.3)",
        }}
      >
        <span>✨</span>
        <span>이대로 시작하기</span>
        <span>→</span>
      </button>
    )}
  </div>
);

// 타이핑 인디케이터
const TypingIndicator = () => (
  <div
    style={{
      display: "flex",
      alignItems: "center",
      gap: "12px",
      marginBottom: "20px",
    }}
  >
    <div
      style={{
        width: "32px",
        height: "32px",
        borderRadius: "10px",
        background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "14px",
      }}
    >
      🤖
    </div>
    <div
      style={{
        padding: "14px 18px",
        backgroundColor: "#18181b",
        borderRadius: "18px",
        borderTopLeftRadius: "4px",
        display: "flex",
        gap: "4px",
      }}
    >
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            width: "8px",
            height: "8px",
            borderRadius: "50%",
            backgroundColor: "rgba(255,255,255,0.4)",
            animation: `bounce 1.4s ease-in-out ${i * 0.2}s infinite`,
          }}
        />
      ))}
    </div>
  </div>
);

// 우측 패널
const PlanPanel = ({ step, data }) => {
  return (
    <>
      <div
        style={{
          padding: "20px 24px",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ fontSize: "18px" }}>📋</span>
          <span style={{ fontSize: "16px", fontWeight: "600" }}>
            채용 계획서
          </span>
        </div>
        <div
          style={{
            padding: "4px 10px",
            backgroundColor: "rgba(34, 197, 94, 0.15)",
            borderRadius: "4px",
            fontSize: "11px",
            color: "#4ade80",
            fontWeight: "500",
            display: "flex",
            alignItems: "center",
            gap: "6px",
          }}
        >
          <div
            style={{
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              backgroundColor: "#4ade80",
              animation: "pulse 2s infinite",
            }}
          />
          실시간 업데이트 중
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "20px" }}>
        {/* 기본 정보 */}
        <PanelSection title="기본 정보" step={step} showFrom={1}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "12px",
            }}
          >
            <InfoItem label="채용형태" value="수시 채용" active={step >= 1} />
            <InfoItem
              label="경력조건"
              value={step >= 2 ? "경력 1년 이상 (완화)" : "—"}
              active={step >= 2}
              highlight={step >= 4}
            />
            <InfoItem
              label="채용기간"
              value="2026.01.3주 ~ 03.중순"
              active={step >= 1}
              fullWidth
            />
            <InfoItem
              label="채용목적"
              value={step >= 3 ? "신규 서비스 팀 확장" : "—"}
              active={step >= 3}
              fullWidth
            />
          </div>
        </PanelSection>

        {/* 채용 포지션 */}
        <PanelSection title="채용 포지션" step={step} showFrom={2}>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            <PositionItem
              icon="👨‍💻"
              name="개발자"
              count="2~3명"
              active={step >= 2}
            />
            <PositionItem
              icon="📊"
              name="기획자"
              count="1명"
              active={step >= 2}
            />
          </div>
        </PanelSection>

        {/* 채용 현황 진단 */}
        {data.showDiagnosis && (
          <PanelSection
            title="🔍 채용 현황 진단"
            step={step}
            showFrom={4}
            highlight
          >
            <div
              style={{
                padding: "14px",
                backgroundColor: "rgba(239, 68, 68, 0.08)",
                border: "1px solid rgba(239, 68, 68, 0.15)",
                borderRadius: "10px",
                marginBottom: "12px",
              }}
            >
              <div
                style={{
                  fontSize: "12px",
                  fontWeight: "600",
                  color: "#fca5a5",
                  marginBottom: "10px",
                }}
              >
                ⚠️ 발견된 이슈
              </div>
              <div
                style={{
                  fontSize: "12px",
                  lineHeight: "1.6",
                  color: "rgba(255,255,255,0.7)",
                }}
              >
                <div style={{ marginBottom: "8px" }}>
                  <strong>1. 경력 연차 과의존</strong>
                  <br />
                  <span style={{ color: "rgba(255,255,255,0.5)" }}>
                    → 2년 이하 일괄 탈락, 고성과자 40%가 3년 미만
                  </span>
                </div>
                <div style={{ marginBottom: "8px" }}>
                  <strong>2. 학력과 성과 무관</strong>
                  <br />
                  <span style={{ color: "rgba(255,255,255,0.5)" }}>
                    → 상관계수 0.12 (무의미)
                  </span>
                </div>
                <div>
                  <strong>3. 역량 미검증</strong>
                  <br />
                  <span style={{ color: "rgba(255,255,255,0.5)" }}>
                    → 조기 이탈자 공통: 협업↓, 적응력↓
                  </span>
                </div>
              </div>
            </div>
            <div
              style={{
                padding: "12px 14px",
                backgroundColor: "rgba(34, 197, 94, 0.1)",
                borderRadius: "8px",
                fontSize: "12px",
                color: "#4ade80",
              }}
            >
              💡 그래서 역량검사 선행, 경력 기준 완화, 학력 블라인드를
              제안드려요
            </div>
          </PanelSection>
        )}

        {/* 역량 스크리닝 기준 */}
        {data.showCompetencies && (
          <PanelSection title="🎯 역량 스크리닝 기준" step={step} showFrom={5}>
            {/* 개발자 */}
            <div
              style={{
                padding: "14px",
                backgroundColor: "rgba(255,255,255,0.03)",
                borderRadius: "10px",
                marginBottom: "12px",
              }}
            >
              <div
                style={{
                  fontSize: "13px",
                  fontWeight: "600",
                  color: "#93c5fd",
                  marginBottom: "12px",
                }}
              >
                👨‍💻 개발자
              </div>
              <CompetencyRow
                name="문제해결력"
                method="H.역량검사"
                criteria="상위 30%"
                reason="고성과자 평균 상위 28%"
              />
              <CompetencyRow
                name="학습민첩성"
                method="H.역량검사"
                criteria="상위 40%"
                reason="신규서비스=새기술 습득 필수"
              />
              <CompetencyRow
                name="협업역량"
                method="H.역량검사"
                criteria="상위 50%"
                reason="조기이탈자 공통 약점"
              />
              <CompetencyRow
                name="기술적합도"
                method="서류검토"
                criteria="2개+"
                reason="Python, AWS 필수"
                isLast
              />
            </div>

            {/* 기획자 */}
            <div
              style={{
                padding: "14px",
                backgroundColor: "rgba(255,255,255,0.03)",
                borderRadius: "10px",
              }}
            >
              <div
                style={{
                  fontSize: "13px",
                  fontWeight: "600",
                  color: "#c4b5fd",
                  marginBottom: "12px",
                }}
              >
                📊 기획자
              </div>
              <CompetencyRow
                name="분석적사고"
                method="H.역량검사"
                criteria="상위 25%"
                reason="데이터 의사결정 필수"
              />
              <CompetencyRow
                name="커뮤니케이션"
                method="H.역량검사"
                criteria="상위 35%"
                reason="이해관계자 설득 빈도↑"
              />
              <CompetencyRow
                name="실행력"
                method="H.역량검사"
                criteria="상위 40%"
                reason="0→1 경험자 우대"
                isLast
              />
            </div>
          </PanelSection>
        )}

        {/* 전형 프로세스 */}
        {data.showCompetencies && (
          <PanelSection title="🔄 전형 프로세스" step={step} showFrom={5}>
            <div style={{ position: "relative" }}>
              <div
                style={{
                  position: "absolute",
                  left: "11px",
                  top: "24px",
                  bottom: "24px",
                  width: "2px",
                  backgroundColor: "rgba(255,255,255,0.1)",
                }}
              />
              {[
                { num: 1, title: "지원접수", isNew: false },
                { num: 2, title: "역량검사 (자동발송)", isNew: true },
                { num: 3, title: "자동 스크리닝", isNew: true },
                { num: 4, title: "서류검토 (역량 기반)", isNew: false },
                { num: 5, title: "1차 면접", isNew: false },
                { num: 6, title: "최종 면접", isNew: false },
                { num: 7, title: "최종 합격", isNew: false },
              ].map((item, idx) => (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "12px",
                    marginBottom: "8px",
                    position: "relative",
                  }}
                >
                  <div
                    style={{
                      width: "24px",
                      height: "24px",
                      borderRadius: "50%",
                      backgroundColor: item.isNew
                        ? "#3b82f6"
                        : "rgba(255,255,255,0.1)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "11px",
                      fontWeight: "600",
                      zIndex: 1,
                    }}
                  >
                    {item.num}
                  </div>
                  <span
                    style={{
                      fontSize: "13px",
                      color: item.isNew ? "#93c5fd" : "rgba(255,255,255,0.6)",
                    }}
                  >
                    {item.title}
                    {item.isNew && (
                      <span
                        style={{
                          marginLeft: "6px",
                          fontSize: "10px",
                          color: "#4ade80",
                        }}
                      >
                        NEW
                      </span>
                    )}
                  </span>
                </div>
              ))}
            </div>
          </PanelSection>
        )}

        {/* 예상 효과 */}
        {data.showEvidence && (
          <PanelSection title="📈 예상 효과" step={step} showFrom={6} highlight>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "10px",
                marginBottom: "12px",
              }}
            >
              <EffectItem label="서류검토 대상" before="100%" after="40%" />
              <EffectItem label="서류검토 시간" before="10시간" after="4시간" />
              <EffectItem label="적합인재 발굴률" before="12%" after="25%" />
              <EffectItem label="입사후 조기이탈" before="18%" after="7%" />
            </div>
            <div
              style={{
                padding: "12px 14px",
                backgroundColor: "rgba(34, 197, 94, 0.1)",
                borderRadius: "8px",
                fontSize: "12px",
                color: "#4ade80",
              }}
            >
              💡 스펙 기준 탈락자 중 역량 우수자 8명 → 이번엔 면접 기회 제공
            </div>
          </PanelSection>
        )}

        {/* 채용 설정 */}
        {data.showFinal && (
          <PanelSection title="⚙️ 채용 설정" step={step} showFrom={7}>
            <div
              style={{ display: "flex", flexDirection: "column", gap: "8px" }}
            >
              <SettingItem
                label="출신학교 블라인드"
                reason="학력-성과 상관없음 (r=0.12)"
                checked
              />
              <SettingItem
                label="사진 블라인드"
                reason="외모 편향 제거"
                checked
              />
              <SettingItem
                label="역량검사 자동 발송"
                reason="지원 직후 24시간 내 발송"
                checked
              />
              <SettingItem
                label="자동 스크리닝"
                reason="역량 기준 미달 시 자동 분류"
                checked
              />
            </div>
          </PanelSection>
        )}
      </div>

      {/* 패널 푸터 */}
      {data.showFinal && (
        <div
          style={{
            padding: "16px 20px",
            borderTop: "1px solid rgba(255,255,255,0.06)",
            display: "flex",
            gap: "10px",
          }}
        >
          <button
            style={{
              flex: 1,
              padding: "12px",
              borderRadius: "10px",
              border: "1px solid rgba(255,255,255,0.1)",
              backgroundColor: "transparent",
              color: "rgba(255,255,255,0.6)",
              fontSize: "13px",
              fontWeight: "500",
              cursor: "pointer",
            }}
          >
            수정하기
          </button>
          <button
            style={{
              flex: 1,
              padding: "12px",
              borderRadius: "10px",
              border: "none",
              background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
              color: "white",
              fontSize: "13px",
              fontWeight: "600",
              cursor: "pointer",
            }}
          >
            ✨ 시작하기
          </button>
        </div>
      )}
    </>
  );
};

// 패널 섹션
const PanelSection = ({ title, children, step, showFrom, highlight }) => {
  if (step < showFrom) return null;

  return (
    <div
      style={{
        marginBottom: "20px",
        animation: "slideInRight 0.4s ease",
      }}
    >
      <div
        style={{
          fontSize: "12px",
          fontWeight: "600",
          color: highlight ? "#4ade80" : "rgba(255,255,255,0.4)",
          textTransform: "uppercase",
          letterSpacing: "0.5px",
          marginBottom: "12px",
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
};

// 정보 아이템
const InfoItem = ({ label, value, active, fullWidth, highlight }) => (
  <div
    style={{
      gridColumn: fullWidth ? "1 / -1" : "auto",
      padding: "10px 12px",
      backgroundColor: active ? "rgba(255,255,255,0.03)" : "transparent",
      borderRadius: "8px",
      transition: "all 0.3s",
    }}
  >
    <div
      style={{
        fontSize: "11px",
        color: "rgba(255,255,255,0.4)",
        marginBottom: "4px",
      }}
    >
      {label}
    </div>
    <div
      style={{
        fontSize: "13px",
        fontWeight: "500",
        color: highlight
          ? "#4ade80"
          : active
          ? "#fafafa"
          : "rgba(255,255,255,0.2)",
      }}
    >
      {value}
    </div>
  </div>
);

// 포지션 아이템
const PositionItem = ({ icon, name, count, active }) => (
  <div
    style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "12px 14px",
      backgroundColor: active
        ? "rgba(59, 130, 246, 0.1)"
        : "rgba(255,255,255,0.03)",
      border: active
        ? "1px solid rgba(59, 130, 246, 0.2)"
        : "1px solid transparent",
      borderRadius: "10px",
      transition: "all 0.3s",
    }}
  >
    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
      <span style={{ fontSize: "16px" }}>{icon}</span>
      <span style={{ fontSize: "13px", fontWeight: "500" }}>{name}</span>
    </div>
    <span
      style={{
        padding: "4px 10px",
        backgroundColor: "rgba(59, 130, 246, 0.2)",
        borderRadius: "4px",
        fontSize: "12px",
        color: "#93c5fd",
        fontWeight: "600",
      }}
    >
      {count}
    </span>
  </div>
);

// 역량 행
const CompetencyRow = ({ name, method, criteria, reason, isLast }) => (
  <div
    style={{
      display: "grid",
      gridTemplateColumns: "70px 80px 60px 1fr",
      gap: "8px",
      alignItems: "center",
      padding: "8px 0",
      borderBottom: isLast ? "none" : "1px solid rgba(255,255,255,0.05)",
      fontSize: "11px",
    }}
  >
    <span style={{ fontWeight: "600", color: "#fafafa" }}>{name}</span>
    <span style={{ color: "rgba(255,255,255,0.5)" }}>{method}</span>
    <span style={{ color: "#4ade80", fontWeight: "600" }}>{criteria}</span>
    <span style={{ color: "rgba(255,255,255,0.4)", fontSize: "10px" }}>
      💡 {reason}
    </span>
  </div>
);

// 효과 아이템
const EffectItem = ({ label, before, after }) => (
  <div
    style={{
      padding: "12px",
      backgroundColor: "rgba(255,255,255,0.03)",
      borderRadius: "8px",
      textAlign: "center",
    }}
  >
    <div
      style={{
        fontSize: "11px",
        color: "rgba(255,255,255,0.4)",
        marginBottom: "8px",
      }}
    >
      {label}
    </div>
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "6px",
      }}
    >
      <span
        style={{
          fontSize: "13px",
          color: "#fca5a5",
          textDecoration: "line-through",
        }}
      >
        {before}
      </span>
      <span style={{ color: "rgba(255,255,255,0.3)" }}>→</span>
      <span style={{ fontSize: "15px", fontWeight: "700", color: "#4ade80" }}>
        {after}
      </span>
    </div>
  </div>
);

// 설정 아이템
const SettingItem = ({ label, reason, checked }) => (
  <div
    style={{
      display: "flex",
      alignItems: "flex-start",
      gap: "10px",
      padding: "10px 12px",
      backgroundColor: "rgba(255,255,255,0.03)",
      borderRadius: "8px",
    }}
  >
    <div
      style={{
        width: "18px",
        height: "18px",
        borderRadius: "4px",
        backgroundColor: checked ? "#3b82f6" : "transparent",
        border: checked ? "none" : "2px solid rgba(255,255,255,0.2)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "12px",
        color: "white",
        flexShrink: 0,
      }}
    >
      {checked && "✓"}
    </div>
    <div>
      <div style={{ fontSize: "13px", fontWeight: "500", marginBottom: "2px" }}>
        {label}
      </div>
      <div style={{ fontSize: "11px", color: "rgba(255,255,255,0.4)" }}>
        💡 {reason}
      </div>
    </div>
  </div>
);

export default CurationAgentV2;
