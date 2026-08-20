# Local Field 프로젝트 구조

Local Field는 로컬 AI 미디어 생성 시스템을 제어·관리하는 웹과 서버로 구성합니다.

```text
local_field_project/
├── web/
│   ├── src/
│   │   ├── lib/
│   │   │   └── configs/
│   │   │       └── constants.ts  # 웹 상수 및 공개 환경변수 설정
│   │   └── routes/               # 웹 페이지 및 라우트
│   ├── .env.development          # 웹 개발 환경변수
│   ├── .env.production           # 웹 배포 환경변수
│   └── Dockerfile
│
├── server/
│   ├── app/
│   │   └── configs/
│   │       └── constants.py      # 서버 상수 및 환경변수 설정
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

## configs/constants

웹과 서버는 각각 `configs/constants` 하나를 환경변수와 상수의 기준으로 사용합니다.

- `web/src/lib/configs/constants.ts`: 공개 환경변수, API 서버 주소, API 문서 경로, 웹 상수
- `server/app/configs/constants.py`: 서버·DB 포트, CORS, 데이터베이스 환경변수, 서버 상수
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
- `server/.env.*`: API 서버 포트, DB 포트, PostgreSQL 연결 값 등 서버에서 사용하는 값
- 루트 `.env`는 사용하지 않습니다.
- 인증 정보와 비밀값은 Git에 커밋하지 않습니다.
- 개발 Compose는 `docker-compose.yml`, 배포 Compose는 `docker-compose.production.yml`을 사용합니다.

## 스타일 라이브러리

- 라이브러리: Tailwind CSS + shadcn-svelte
- 아이콘: Lucide (`lucide-svelte`)
