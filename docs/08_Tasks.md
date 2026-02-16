# 08_Tasks: Micro-Task Breakdown

## Phase 1: Core Infrastructure & API
- **[T1.1] [P0] [Setup] Backend Project Scaffold**
  - 내용: FastAPI 기초 구조 및 `requirements.txt` 생성.
  - 파일: `backend/main.py`, `backend/requirements.txt`
  - DoD: `pip install -r requirements.txt && python -m uvicorn main:app` 실행 확인.
- **[T1.2] [P0] [Security] Key Derivation & Encryption**
  - 내용: Machine UUID와 사용자 Salt를 조합한 마스터 키 생성 및 AES-256 암호화 모듈 구현.
  - 파일: `backend/app/core/security.py`, `.env.example`
  - DoD: 다른 로컬 환경으로 .env 복사 시 복호화가 차단되는지 확인.
- **[T1.3] [P0] [API] Kiwoom REST Client Wrapper**
  - 내용: `httpx`를 사용한 키움 API 인증 및 기본 조회 함수 작성.
  - 파일: `backend/app/services/kiwoom_client.py`
  - DoD: Mock 데이터를 활용한 API 호출 성공 여부 확인.
- **[T1.4] [P1] [Schema] Data Models Definition**
  - 내용: Pydantic을 이용한 시세 및 응답 규격 정의 (Explicit Typing).
  - 파일: `backend/app/models/stock.py`
  - DoD: `pytest`를 통한 스키마 유효성 검사 통과.

## Phase 2: Real-time Engine (WebSocket & Logic)
- **[T2.1] [P0] [Logic] Token Bucket & Staggered Request**
  - 내용: 초당 5회 제한 준수 및 초기 16개 종목 로딩 시 200ms 간격의 순차 요청 로직 구현.
  - 파일: `backend/app/core/rate_limiter.py`
  - DoD: 16개 종목 초기화 시 API 차단 없이 순차적으로 시세 수신 확인.
- **[T2.2] [P0] [WS] WebSocket Broadcast Handler**
  - 내용: 클라이언트 관리 및 JSON 브로드캐스트 로직 구현.
  - 파일: `backend/app/api/websocket.py`
  - DoD: `wscat` 등으로 접속 시 웰컴 메시지 수신 확인.
- **[T2.3] [P1] [Logic] Real-time Data Multiplexer**
  - 내용: 키움 실시간 데이터를 1개의 소켓 스트림으로 통합.
  - 파일: `backend/app/services/streamer.py`
  - DoD: 백엔드 로그에 통합된 JSON 데이터 출력 확인.

## Phase 3: Frontend & Rendering
- **[T3.1] [P0] [Setup] Vue 3 Project Scaffold**
  - 내용: Vite + Vue 3 + Tailwind CSS 환경 구성.
  - 파일: `frontend/package.json`, `frontend/tailwind.config.js`
  - DoD: `npm run dev` 실행 및 초기 화면 확인.
- **[T3.2] [P0] [UI] 4x4 Responsive Grid Layout**
  - 내용: CSS Grid를 활용한 16개 셀 레이아웃 구현.
  - 파일: `frontend/src/views/Dashboard.vue`
  - DoD: 브라우저에서 4x4 격자가 정확히 표시되는지 확인.
- **[T3.3] [P0] [Render] Chart Engine Integration**
  - 내용: Lightweight Charts 기본 설정 및 컴포넌트화.
  - 파일: `frontend/src/components/StockChart.vue`
  - DoD: 개별 셀에 빈 차트가 렌더링되는지 확인.
- **[T3.4] [P1] [Perf] Non-reactive Data Pipeline**
  - 내용: Vue Proxy를 우회하여 시세 데이터를 차트 엔진에 직접 주입 (shallowRef 및 Raw Object 사용).
  - 파일: `frontend/src/composables/useWebSocket.ts`
  - DoD: 16개 차트 실시간 구동 시 CPU 점유율의 안정성 확인.
- **[T3.5] [P2] [Memory] Chart Cleanup Logic**
  - 내용: 컴포넌트 언마운트 시 차트 인스턴스 명시적 해제 (Memory Cleanup).
  - 파일: `frontend/src/components/StockChart.vue`
  - DoD: 차트 반복 생성/삭제 시 메모리 사용량 추이 관찰.

## Phase 4: Integration & QA
- **[T4.1] [P1] [Integration] End-to-End Stock Search**
  - 내용: 검색 창을 통해 차트 종목 변경 기능 구현.
  - 파일: `frontend/src/components/SearchBox.vue`, `backend/app/api/stocks.py`
  - DoD: 종목 코드 입력 시 해당 차트의 데이터가 갱신되는지 확인.
- **[T4.2] [P2] [UX] Status Bar & Error Handling**
  - 내용: API 제한 및 연결 상태 표시 UI 구현.
  - 파일: `frontend/src/components/StatusBar.vue`
  - DoD: 백엔드 종료 시 "Disconnected" 상태 표시 확인.
- **[T4.3] [P2] [Deploy] Docker Compose Config**
  - 내용: 미니 서버 배포를 위한 컨테이너 설정.
  - 파일: `docker-compose.yml`, `Dockerfile`
  - DoD: `docker-compose up`으로 전체 시스템 기동 성공.

---

## 핵심 리스크 및 주의 사항
1. **[T2.1] Rate Limiter**: 이 로직이 실패하면 키움 계정이 일시 차단될 수 있으므로 가장 먼저 철저히 테스트해야 함.
2. **[T3.4] WS Multi-plexing**: 16개 차트에 데이터를 분배할 때 Vue의 반응성 시스템(`Proxy`) 부하를 줄이기 위해 `shallowRef` 사용 권장.
3. **[T4.3] Docker on Windows**: 키움 API가 Windows 전용 모듈을 요구할 경우 Docker 대신 네이티브 실행 환경 구성으로 변경될 수 있음.
