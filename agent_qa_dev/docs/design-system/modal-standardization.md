# 모달 컴포넌트 공통 규칙 (Backoffice Frontend)

## 목적

백오피스에서 Ant Design `Modal` 사용을 일관되게 유지하고,
`조회(View)`, `수정(Edit)`, `cURL 토큰 파싱` 같은 주요 오버레이에서
동일한 구조와 동작을 보장한다.

현재 기준 구현 위치: `backoffice/frontend/src/components/common/StandardModal.tsx`

---

## 1) 공통 사용 원칙

### 1-1. 모든 일반 모달은 `StandardModal` 사용

- 직접 `<Modal />` 를 페이지에서 새로 만들지 않는다.
- 예외: `Modal.confirm()` 형태의 브릿지/확인 다이얼로그는 기존 `Modal.confirm` 사용 가능.
- 새 모달은 기본적으로 `StandardModal`로 열고, 필요한 경우 `styles`/`bodyPadding`/`destroyOnHidden`를 오버라이드한다.

### 1-2. 제목은 `title` 프롭으로 관리
- 모달 상단 제목(antd 헤더)은 `StandardModal`의 `title` prop으로 전달.
- `title`은 **모달 성격**만 표현한다.
  - 예: `프롬프트 조회`, `프롬프트 수정`, `cURL 토큰 파싱`
- 선택된 항목 식별자/명칭은 제목에 넣지 않는다.
  - `title` 안에 `ORCHESTRATOR_WORKER` 같은 선택값을 넣지 않는다.

### 1-3. 선택 항목/메타 정보는 본문에서 표현
- 모달 본문 최상단에 `StandardModalMetaBlock` 사용.
- 형식 예시:
  - `선택된 프롬프트: ORCHESTRATOR_WORKER`
- 메타 블록은 제목이 아닌 `body` 요소로 둔다.
- 기존 “PROMPT” 라벨 같은 중복 제목성 행은 제거한다.

---

## 2) 뷰/에디트 모달 레이아웃 규칙

### 2-1. 기본 레이아웃

- 모달 본문은 기본적으로 `flex column` + `height: 100%` 구조로 구성.
- 큰 텍스트 영역(TextArea, Monaco Diff)는 `flex: 1` + `min-height: 0` + 부모 체인에서 높이 전파가 되도록 구성.
- Monaco Diff는 wrapper에 `height: '100%'` 또는 유사한 명시 높이를 둬야 한다.

### 2-2. 좌우 패딩 정책

- 조회 모달 본문은 `bodyPadding={0}` 사용해 좌우 full-bleed.
- `선택된 프롬프트` 같은 메타 블록/문맥 텍스트는 별도 래퍼로 `padding: 0 16px` 또는 16 기반 간격 적용.
- 필요시 모달 내부 개별 섹션마다 별도 패딩을 부여해 가독성만 보정한다.

### 2-3. 간격

- 메타 블록 하단은 최소 `margin-bottom: 12px` 확보(권장 12~16).
- 버튼/요약/에디터 구간 사이 간격을 8~12px로 정렬.

### 2-4. 모달 본문 메타 블록 예시 (cURL 토큰 파싱)

- cURL 모달은 본문 상단에 `StandardModalMetaBlock`을 두어 안내 문구를 노출한다.
- 예시 문구:
  - `브라우저에서 복사한 전체 cURL 명령어를 넣어 주세요. 토큰은 이 본문에서 추출됩니다.`

### 2-5. 텍스트 뷰어/에디터

- 조회 모달 텍스트 에어리어는 `height/width`만으로 렌더링 크기를 고정하지 말고,
  부모 flex 성장 규칙(`flex:1`, `minHeight:0`)에 의존해 자연스럽게 확장.
- 편집 모달의 Monaco Diff는 열림 시 `layout()` 리프레시(예: `afterOpenChange`/`ResizeObserver`) 필요.

### 2-6. 모달 항목 간 간격 (`gap`)

- 모달 내부에서 항목 목록이 겹쳐보일 경우, 기본 세로 간격은 `12px`로 통일한다.
- 재사용 규칙:
  - `standard-modal-field-stack` 클래스를 Form 또는 항목 컨테이너에 적용
  - 내부 `.ant-form-item`의 기본 `margin-bottom`을 `0`으로 리셋
  - 컨테이너에 `gap: 12px` 적용
- 적용 위치: `backoffice/frontend/src/styles.css`의 `.standard-modal-field-stack`
- 적용 예시(현재 cURL 모달): `Form` 본문에 `className="standard-modal-field-stack"`

---

## 3) 컴포넌트 매핑 규칙

- `StandardModal` : 모달 컨테이너
- `StandardModalMetaBlock` : 본문 메타 헤더 라인

예시:

```tsx
<StandardModal title="프롬프트 조회" open={open} width={...} bodyPadding={0}>
  <StandardModalMetaBlock marginBottom={12} padding={0}>
    <div>선택된 프롬프트: {selectedWorker}</div>
  </StandardModalMetaBlock>
  ...
</StandardModal>
```

---

## 4) 변경 이력/적용 범위

- 이 규칙은 다음 모달들에 적용됨:
  - `backoffice/frontend/src/features/prompts/PromptManagementPage.tsx`
    - 조회 모달
    - 수정 모달
  - `backoffice/frontend/src/app/AppLayout.tsx`
    - cURL 토큰 파싱 모달

향후 추가되는 모달도 동일 규칙을 사용해 누락 없이 반영한다.
