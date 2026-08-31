# 이미지를 이미지로

## 목적

로컬 이미지 한 장을 기준 이미지로 사용해 `Anima` 또는 `Illustrious` 이미지-투-이미지 생성을 시작한다. 라우트 제목은 쿼리의 모델 패밀리에 따라 `이미지를 이미지로 (Anima)` 또는 `이미지를 이미지로 (Illustrious)`로 표시한다.

## 모델 패밀리와 옵션

- 라우트: `/generate/image-to-image?family=anima|illustrious`
- 쿼리가 없거나 지원하지 않는 값이면 `anima`를 사용한다.
- 모델 옵션은 `GET generation/image/options?family=${family}`에서 가져온다.
- 패밀리가 바뀌면 체크포인트, LoRA, 샘플러와 스케줄러를 해당 패밀리의 옵션으로 다시 초기화한다.

## 소스 이미지

- 기기에서 이미지 파일을 정확히 한 장만 선택한다. 이미지 상세 재생성에서는 owner-checked 기존 `source_file_id`와 signed preview URL을 재사용한다.
- 선택 단계에서는 서버로 업로드하지 않는다. 새 local 파일 전송은 생성 요청을 제출할 때만 발생한다.
- 선택한 파일은 기존 `ImageMedia`에 `sourceType="local"`로 전달해 미리 본다.
- 파일 이름, MIME 형식, 파일 크기, `naturalWidth × naturalHeight`를 표시한다.
- `이 사이즈 사용`은 원본 비율을 기준으로 긴 변이 최대 2048을 넘지 않도록 축소한 뒤 각 변을 가장 가까운 8의 배수로 맞춘다. 서버가 허용하는 최소 크기 64와 최대 크기 2048도 적용한다.

## 생성 설정

긍정·부정 프롬프트, 체크포인트, 최대 8개 LoRA와 LoRA별 Strength, 가로·세로, Denoise(0.0~1.0), CFG(0~20), Steps(1~100), 샘플러·스케줄러, Seed를 제공한다. Anima는 Diffusion Model, Illustrious는 full checkpoint를 사용한다. Illustrious prompt의 Embedding picker는 `embeddings/Illustrious` 파일을 native `embedding:Illustrious/파일명` token으로 긍정 또는 부정 prompt에 삽입한다. Seed는 무작위일 때 `null`, 직접 입력할 때 0부터 `9223372036854775807` 사이의 정수 문자열로 전송한다. 큰 정수의 정밀도를 잃지 않도록 직접 입력 Seed를 JavaScript `number`로 변환하지 않는다. 이 MVP에는 프리셋과 프롬프트 개선을 포함하지 않는다.

## 생성 요청

`POST generation/image/i2i`에 multipart `FormData`를 보낸다.

- `payload`: `{model_family, source:{file_index:0}, prompt, negative_prompt, checkpoint, loras, cfg, steps, sampler_name, scheduler, width, height, seed, denoise}` JSON 문자열
- `files`: 선택한 로컬 이미지 한 장

파일, 이미지 메타데이터, 프롬프트, 모델 선택, 숫자 범위, 이미지 크기의 8배수 여부, LoRA 수와 Strength, Seed 문자열을 제출 전에 검증한다. 옵션 조회, 파일 전송, 생성 대기, 취소 중에는 대응하는 로딩 상태와 비활성 상태를 표시하며 통신 실패는 toast로 알린다.

## 작업 상태와 결과

서버가 생성 요청을 수락하면 전역 `generationJobStore`에 `kind: 'image'`로 해당 작업을 등록한다. 기존 이미지 SSE와 취소 경로를 그대로 사용하고 진행 상태, 대기 순서, 경과 또는 소요 시간을 표시한다. 화면 진입 시에는 이 라우트가 가진 작업 키와 결과 상태만 초기화하며 전역 store의 작업을 삭제하거나 가장 최근 전역 작업을 자동 선택하지 않는다. 완료 이미지는 기존 `ImageMedia`로 표시하고 `/vault/images/{generation_id}` 상세 화면으로 연결한다.
