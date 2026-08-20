# Local Field 프로젝트 구조

Local Field는 로컬 AI 미디어 생성 시스템을 제어·관리하는 웹과 서버로 구성합니다.

```text
local_field_project/
├── web/
│   ├── src/
│   │   ├── app.css                 # Tailwind 테마 및 컬러 팔레트
│   │   ├── lib/
│   │   │   ├── configs/
│   │   │   │   └── constants.ts  # 웹 상수 및 공개 환경변수 설정
│   │   │   ├── utils/
│   │   │   │   ├── api.ts          # ky API client·인증 SSE stream·오류 변환
│   │   │   │   └── jwt.ts          # JWT payload·만료·사용 가능 상태 확인
│   │   │   └── stores/
│   │   │       └── auth.svelte.ts # JWT 인증 상태 및 자동로그인 상태관리
│   │   └── routes/
│   │       ├── login/
│   │       │   └── +page.svelte    # 로그인·회원가입 화면
│   │       ├── generate/
│   │       │   └── image/
│   │       │       └── +page.svelte # ComfyUI Anima 이미지 생성 화면
│   │       └── vault/
│   │           └── +page.svelte    # 인증 사용자 개인 보관함
│   ├── components/
│   │   ├── buttons/
│   │   │   ├── primary-button.svelte
│   │   │   ├── outlined-button.svelte
│   │   │   └── icon-outlined-button.svelte
│   │   ├── inputs/
│   │   │   ├── input.svelte
│   │   │   └── select.svelte
│   │   ├── layouts/
│   │   │   ├── body.svelte
│   │   │   ├── layout.svelte
│   │   │   ├── navbar.svelte
│   │   │   └── sidebar.svelte
│   │   ├── loadings/
│   │   │   ├── loading-shimmer.svelte
│   │   │   └── loading-spinner.svelte
│   │   ├── modals/
│   │   │   └── modal.svelte
│   │   ├── media/
│   │   │   ├── image.svelte
│   │   │   ├── model-viewer.svelte
│   │   │   └── video.svelte
│   │   ├── feedback/
│   │   │   └── toast.svelte
│   │   ├── tabs/
│   │   │   └── tab.svelte
│   │   └── typography/
│   │       └── typography.svelte
│   ├── .env.development          # 웹 개발 환경변수
│   ├── .env.production           # 웹 배포 환경변수
│   └── Dockerfile
│
├── server/
│   ├── app/
│   │   ├── auth.py               # JWT 회원가입·로그인·현재 사용자 API
│   │   ├── comfyui.py            # ComfyUI Anima 옵션·생성·결과 프록시 API
│   │   ├── database.py           # PostgreSQL users·auth_history·API 로그 스키마 및 기록
│   │   ├── main.py               # FastAPI 앱과 API 감사 미들웨어
│   │   └── configs/
│   │       └── constants.py      # 서버 상수·환경변수·JWT·ComfyUI 주소
│   ├── .env.development          # 서버 개발 환경변수
│   ├── .env.production           # 서버 배포 환경변수
│   └── Dockerfile
│
├── docker-compose.yml            # 개발 환경
├── docker-compose.production.yml # 배포 환경
└── STRUCTURE.md
```

## Web 프레임워크

- 프레임워크: SvelteKit
- UI 런타임: Svelte 5
- 언어: TypeScript
- 개발·빌드 도구: Vite
- 배포 어댑터: `@sveltejs/adapter-node`

## Web components

- `web/components/buttons/primary-button.svelte`: 주요 액션 버튼
- `web/components/buttons/outlined-button.svelte`: 보조·취소 액션 버튼
- `web/components/buttons/icon-outlined-button.svelte`: 아이콘 전용 외곽선 버튼
- 세 버튼은 `active`, `deactive`, `loading` 상태를 제공합니다.
- `web/components/inputs/input.svelte`: 라벨, 힌트, 오류, disabled를 지원하는 입력 컴포넌트
- `web/components/inputs/select.svelte`: 기본 select와 prop으로 켜는 autocomplete select
- `web/components/media/image.svelte`: 로컬·서버 이미지, 서버 로딩 shimmer, 확대 갤러리
- `web/components/media/model-viewer.svelte`: 로컬·서버 GLB/GLTF 모델과 마우스 드래그 카메라 조작
- `web/components/media/video.svelte`: 로컬·서버 영상, 서버 로딩 shimmer, 앞부분 preview
- `web/components/loadings/loading-spinner.svelte`: 회전형 로딩 상태
- `web/components/loadings/loading-shimmer.svelte`: 콘텐츠 로딩 placeholder
- `web/components/modals/modal.svelte`: 제목, 설명, 본문, footer를 지원하는 반응형 모달
- `web/components/typography/typography.svelte`: display, heading, body, muted, label, caption 텍스트 스타일
- `web/components/tabs/tab.svelte`: 재사용 가능한 선택형 탭 목록
- `web/components/layouts/sidebar.svelte`: 데스크톱 고정 사이드바와 모바일 하단 시트 메뉴
- `web/components/layouts/navbar.svelte`: 데스크톱 상단 내비게이션
- `web/components/layouts/body.svelte`: 반응형 max-width 콘텐츠 영역
- `web/components/layouts/layout.svelte`: Sidebar, Navbar, Body를 조합하는 전체 레이아웃

## 인증

- `server/app/auth.py`: `/auth/signup`, `/auth/login`, `/auth/me` JWT API
- `server/app/database.py`: 사용자·인증 이력·API 감사·오류 로그 DB 처리
- `server/app/comfyui.py`: ComfyUI Anima 옵션·생성 요청·WebSocket 진행 이벤트의 인증 SSE 변환·결과 프록시
- `web/src/routes/generate/image/+page.svelte`: 프롬프트, 체크포인트, LoRA, CFG, steps와 queued·progress·completed SSE 상태를 표시하는 이미지 생성 화면
- `web/components/feedback/toast.svelte`: 비동기 생성 오류·완료 상태 알림
- `web/src/lib/utils/api.ts`: ky 기반 API·인증 SSE stream 호출, JWT header 주입, HTTP 오류 변환
- `web/src/lib/utils/jwt.ts`: JWT payload decode와 만료·사용 가능 상태 확인
- `web/src/lib/stores/auth.svelte.ts`: Svelte 5 rune 기반 JWT 상태관리와 `localStorage` 자동로그인 복원
- 로그인·회원가입 성공 후 `/vault`로 이동합니다.
- `/vault`는 `/auth/me`로 JWT를 검증한 인증 사용자만 접근합니다.

## configs/constants

웹과 서버는 각각 `configs/constants` 하나를 환경변수와 상수의 기준으로 사용합니다.

- `web/src/lib/configs/constants.ts`: 공개 환경변수, API 서버 주소, API 문서 경로, 웹 상수
- `server/app/configs/constants.py`: 서버·DB 포트, CORS, 데이터베이스 환경변수, JWT 서명 비밀값, ComfyUI 주소, 서버 상수
- `config.*`와 `constants.*`를 별도 파일로 분리하지 않습니다.
- 웹 페이지와 서버 모듈은 환경변수를 직접 읽지 않고 `configs/constants`를 사용합니다.

## 환경변수

웹과 서버의 환경변수는 각 프로젝트에 개발용과 배포용으로 분리합니다.

```text
web/.env.development
web/.env.production
server/.env.development
server/.env.production
```

- `web/.env.*`: Web 포트와 공개 API 서버 주소·포트 등 웹에서 사용하는 값
- `server/.env.*`: API 서버 포트, DB 포트, PostgreSQL 연결 값, JWT 서명 비밀값, 선택적 `COMFYUI_URL` 등 서버에서 사용하는 값
- 루트 `.env`는 사용하지 않습니다.
- 인증 정보와 비밀값은 Git에 커밋하지 않습니다.
- 개발 Compose는 `docker-compose.yml`, 배포 Compose는 `docker-compose.production.yml`을 사용합니다.

## 스타일 라이브러리

- 라이브러리: Tailwind CSS + shadcn-svelte
- 아이콘: Lucide (`@lucide/svelte`)
- Tailwind 테마: `web/src/app.css`
- 기본 모드: Dark mode
- Dark mode 전환: `.dark` 클래스
- 컬러 방향: Slate/Zinc 기반 + Violet 포인트

### 브랜드 팔레트

| 토큰 | Light mode | Dark mode | 용도 |
|---|---|---|---|
| `primary` | `#7C3AED` | `#8B5CF6` | 주요 버튼, 활성 상태, 핵심 액션 |
| `secondary` | `#0284C7` | `#38BDF8` | 보조 액션, 정보성 강조 |
| `tertiary` | `#0F766E` | `#2DD4BF` | 세 번째 액션, 미디어·생성 상태 강조 |

Tailwind에서는 `bg-primary`, `text-secondary`, `border-tertiary`처럼 사용합니다.

### 상태 팔레트

- `success`: Light `#16A34A`, Dark `#22C55E`
- `warning`: Light `#D97706`, Dark `#F59E0B`
- `destructive`: Light `#DC2626`, Dark `#F87171`
- `info`: Light `#0284C7`, Dark `#38BDF8`
