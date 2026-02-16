# 06_Spec: Master Implementation Specification

## 1. 구현 우선순위 (Priority Reasoning)
1. **P0 (Critical)**: 키움 REST API 인증 및 1개 종목 실시간 체결가 수신 (기초 인프라).
2. **P0 (Critical)**: 4x4 그리드 레이아웃 및 16개 차트 캔버스 초기화 (핵심 UI).
3. **P1 (High)**: API Rate Limiter 및 WebSocket 멀티플렉싱 (시스템 안정성).
4. **P2 (Normal)**: 계좌 정보 연동 및 보안 저장소 (완성도).

---

## 2. 사용자 시나리오 (User Scenarios - Given/When/Then)

### S-1: 정상 데이터 수신
- **Given**: 사용자가 4x4 그리드를 열고 16개 종목을 설정함.
- **When**: 장중 실시간 체결 데이터가 발생함.
- **Then**: 백엔드는 1개의 WebSocket으로 모든 종목 데이터를 묶어 전송하고, 16개 차트는 각각 200ms 이내에 갱신됨.

### S-2: API 제한 도달 (Negative Case)
- **Given**: 시스템이 초당 5회 이상의 TR 요청을 시도함.
- **When**: 토큰 버킷의 토큰이 소진됨.
- **Then**: 백엔드는 요청을 큐에 대기시키고, 프론트엔드 하단 상태바에 "API 요청 대기 중" 경고를 표시함.

### S-3: 네트워크 단절 및 재연결
- **Given**: 인터넷 연결이 일시적으로 끊김.
- **When**: WebSocket 연결이 종료됨.
- **Then**: 프론트엔드는 5초 간격으로 재연결을 시도하며, 성공 시 차트의 끊긴 구간(Gap) 데이터를 자동으로 재요청(Backfill)함.

---

## 3. 성공 기준 (Success Criteria)
- **성능 (Latency)**: 백엔드 수신 시점부터 프론트엔드 렌더링까지 지연 시간 **평균 150ms 이하**.
- **안정성 (Memory)**: 16개 차트 24시간 구동 시 브라우저 메모리 증가량(Leak) **10MB 미만**.
- **정확성 (Integrity)**: 백엔드 수신 체결 수와 프론트엔드 반영 체결 수 일치율 **100%**.

---

## 4. Technical Risks & Non-Goals

### Technical Risks
- **Kiwoom API Stability**: 키움 REST API 서버의 간헐적 응답 지연. -> **완화**: 타임아웃 3초 설정 및 지수 백오프(Exponential Backoff) 적용.
- **Browser Thread Blocking**: 16개 차트 동시 렌더링 시 UI 스레드 점유. -> **완화**: `requestAnimationFrame` 및 Web Worker 활용 검토.

### Non-Goals
- **Mobile Native App**: 현재는 Web SPA 버전만 개발하며 네이티브 앱은 범위 외임.
- **Cloud Sync**: 사용자 데이터는 로컬에만 저장하며 클라우드 동기화 기능은 제공하지 않음.

---

## 5. Verification (Traceability)
- **FR-1 (Grid-16)**: 02_SRS.md의 3.2절 요구사항 반영.
- **FR-2 (Kiwoom API)**: 01_PRD.md의 핵심 데이터 소스 명세 반영.
- **FR-3 (Secure Storage)**: 04_Architecture.md의 ADR-2(보안) 반영.

---

## 6. [NEEDS CLARIFICATION]
1. 키움 REST API의 실시간 WebSocket이 제공하는 최대 동시 구독 종목 수 확인 필요 (현재 100개로 가정).
2. 미니 서버의 운영체제(Windows vs Linux)에 따른 키움 API 연동 방식 차이 확인 필요.
   - *참고: 키움 REST API 서버가 별도로 구동 중인지, 아니면 직접 Python으로 게이트웨이를 구축해야 하는지 확인 부탁드립니다.*
