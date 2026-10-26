# 웹 상호작용·API 오류 기록

전 페이지 루트 레이아웃에서 document capture 리스너를 한 번 설치한다. 버튼·링크뿐 아니라 모든 DOM 요소의 click/pointerdown, change, submit, Enter/Escape, 재생·일시정지·탐색·음량·속도·전체화면 이벤트를 기록한다. 이벤트를 취소하거나 원래 핸들러를 기다리지 않는다.

composedPath로 중첩 SVG와 open shadow DOM의 실제 요소를 찾는다. 실제 클릭 요소와 의미상 상위 컨트롤을 함께 기록한다. ID가 없으면 태그·nth-of-type 경로로 식별하며 모달/영역의 경로와 제목 및 가까운 상위 요소 4개의 ID·텍스트를 보존해 같은 이름의 선택 버튼이 속한 항목도 확인할 수 있다. 라벨은 data-audit-label, aria-label, aria-labelledby, 연결된 label, title, alt, name, 텍스트 순으로 찾는다. 명시적인 안정 ID가 필요하면 data-audit-id를 지원한다. 라벨은 512자로 제한하고 전체 DOM 경로를 별도로 저장한다.

기록에는 event UUID, 클라이언트 시각, query/hash를 포함한 페이지, 링크, 실제 요소·컨트롤 경로, 상태·좌표·키가 포함된다. 서버가 JWT를 검증해 user_id를 붙이고 익명/로그인 공통 방문자·세션 UUID도 보존한다. Storage가 막히면 메모리 ID로 유지한다. 입력 텍스트·비밀번호·선택 파일 내용은 수집하지 않는다.

루트 afterNavigate가 최초 진입과 모든 경로 이동·뒤로/앞으로 이동을 기록한다. 전/후 경로, route ID, navigation_type을 포함한다. 18개 페이지 경로에 같은 유틸을 적용하며 페이지별 버튼 누락을 만드는 개별 등록 방식은 사용하지 않는다.

apiJson/apiForm/apiBlob/apiDelete/streamSse 및 외부 downloadMedia는 안내 문구 변환 전에 reportApiError로 원래 오류 종류·문구·스택·HTTP 상태·응답 본문을 전달한다. 의도적인 AbortError는 제외하고 기록 전송 자체는 재귀 기록하지 않는다.

fetch는 void로 호출하고 완료를 기다리지 않는다. 작은 본문은 keepalive를 사용하며 60,000바이트 초과 기록은 브라우저 keepalive 제한을 피한다. 전송 타임아웃은 5초이며 실패는 기능으로 전파하지 않는다. 오프라인·탭 강제 종료·서버 큐 초과 등에서는 best effort 기록이 유실될 수 있다. 비공개 shadow root·브라우저 자체 미디어 UI 내부는 브라우저가 노출하는 호스트/미디어 이벤트까지만 식별할 수 있다.
