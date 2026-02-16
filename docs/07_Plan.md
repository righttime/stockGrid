# 07_Plan: Technical Implementation Roadmap

## 1. Summary
- **기술적 가치**: 키움 REST API의 물리적 한계를 백엔드 비동기 큐와 프론트엔드 캔버스 최적화를 통해 극복하여, TradingView 수준의 16분할 실시간 대시보드를 로컬 미니 서버 환경에서 구현함.
- **핵심 전략**: Python FastAPI 기반의 API 게이트웨이 구축 및 Vue 3 + Lightweight Charts를 통한 저지연 렌더링.

---

## 2. Tech Selection & Profile
- **Profile**: [Profile B: General Web/Service] 기반이나, [Profile A]의 메모리 관리 원칙을 준수함.
- **Backend**: Python 3.10+, FastAPI, HTTPX (Async API Client), WebSockets.
- **Frontend**: Vue 3 (Composition API), Vite, Tailwind CSS, Lightweight Charts.
- **Storage**: SQLite (Encrypted) for configuration, Redis (Optional) for real-time cache.

---

## 3. Implementation Roadmap

### Phase 1: Core Infrastructure (Core API)
- **목표**: 키움 REST API 인증 및 기본 시세 조회 기능 확보.
- **Task**: 
  - FastAPI 프로젝트 구조 설정.
  - API Key 암호화 저장소(AES-256) 및 인증 로직 구현.
  - 기본 TR(현재가, 일봉) 요청 함수 작성.
- **DoD**: Swagger UI에서 특정 종목의 현재가 JSON 응답 확인 성공.

### Phase 2: Real-time Data Stream (Broadcasting)
- **목표**: WebSocket을 통한 실시간 데이터 멀티플렉싱 엔진 구축.
- **Task**:
  - Token Bucket 기반 Rate Limiter 구현.
  - WebSocket 서버 개설 및 데이터 브로드캐스트 핸들러 작성.
  - Kiwoom 실시간 데이터 수신 및 JSON 정규화 로직 구현.
- **DoD**: 백엔드 로그 상에서 초당 5회 미만의 속도로 실시간 체결 데이터 수신 및 브로드캐스트 확인.

### Phase 3: Grid UI & Rendering (UI Integration)
- **목표**: 4x4 그리드 레이아웃 및 차트 엔진 연동.
- **Task**:
  - Vue 3 + Grid Layout 컴포넌트 개발.
  - Lightweight Charts 연동 및 차트 수명 주기(Lifecycle) 관리 로직 구현.
  - WebSocket 데이터 연동 및 차트 실시간 업데이트.
- **DoD**: 브라우저에서 16개 차트가 동시에 실시간으로 움직이는 화면 확인.

### Phase 4: Security & Optimization (QA)
- **목표**: 시스템 안정화 및 보안 강화.
- **Task**:
  - 미니 서버 자동 실행 설정 (Systemd/Docker Compose).
  - 대용량 데이터 수신 시 메모리 누수 테스트.
  - 최종 UI 디테일(다크 모드, 상태바) 보정.
- **DoD**: 24시간 연속 가동 테스트 통과 및 메모리 점유율 안정화 확인.

---

## 4. Constitution & Project Structure
- **헌법 준수**: `English Code, Korean Doc` 원칙에 따라 프로젝트 폴더 구성.

```text
/ (Project Root)
├── backend/                # FastAPI Application
│   ├── app/
│   │   ├── api/            # API Endpoints
│   │   ├── core/           # Security & Rate Limiting
│   │   ├── models/         # Pydantic Schemas
│   │   └── services/       # Kiwoom API Logic
│   ├── main.py
│   └── requirements.txt
├── frontend/               # Vue.js Application
│   ├── src/
│   │   ├── components/     # Grid & Chart Components
│   │   ├── composables/    # WS & API Logic
│   │   └── views/          # Dashboard View
│   ├── package.json
│   └── vite.config.ts
└── docs/                   # Documentation (Korean)
```

---

## 5. Verification & Risk Report
- **최대 기술적 병목(Risk)**: 키움 REST API의 로그인 세션 유지 및 WebSocket 연결 안정성.
- **대응 방안**: 백엔드에서 Heartbeat 체크 로직을 구현하여 연결 단절 시 자동 재인증 및 세션 복구 프로세스 가동.
