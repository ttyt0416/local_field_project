# 이미지 Storage 메타데이터

`image_generations.storage_file_id`는 실제 이미지 바이트를 저장하지 않고 독립 Storage 서비스의 파일 식별자만 보관한다.

`presets`는 사용자별 설정 모음이다. `type`으로 프리셋 종류를 구분하고 현재는 `t2i`를 사용하며, 선택 저장된 설정만 `values` JSONB에 기록한다. 같은 이름도 여러 개 저장할 수 있고 UUID로 수정·삭제 대상을 구분한다. `is_default`는 사용자와 프리셋 타입 조합별로 최대 1개만 허용하는 partial unique index로 관리한다.

기존 `presets` 테이블에는 시작 시 migration statement가 `is_default` 컬럼을 추가한다. 기본값은 `FALSE`이며, 이후 `presets_one_default_per_user_type_idx`가 사용자·타입별 기본 프리셋 중복을 방지한다.

기존 데이터베이스에는 시작 시 migration statement가 nullable 컬럼을 추가한다. 기존 `file_path`, `filename`, `subfolder`, `image_type` 값과 기존 이미지 프록시 fallback은 유지한다.
