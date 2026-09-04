# Vault 콘텐츠 목록 표시

Vault API는 Storage signed URL이 있는 이미지에는 external URL을, Local Field가 반환한 relative path에는 authenticated Blob load를 사용한다. 목록은 latest·oldest·most viewed 정렬과 server-side search, page size 10 pagination을 제공한다.

이미지 tab은 visible `IMAGE` title 없이 `IMAGE`, `VIDEO`, `3D` top tab과 그 아래 `ANIMA`, `ILLUSTRIOUS`, `KREA2` family tab, `T2I`, `I2I` mode tab을 같은 간격으로 표시한다. 기본 선택은 `ANIMA`와 `T2I`다. 선택은 `generation_mode`와 `model_family`를 함께 `GET /vault/images` 및 `DELETE /vault/images/filtered`에 보낸다. 둘 중 하나만 보낸 API request는 422로 거절한다. 따라서 목록 count, pagination, filtered delete 모두 정확한 T2I/I2I × Anima/Illustrious/Krea2 category만 대상으로 한다. Krea2 T2I completed rows는 Krea2 filter에 표시된다. Krea2 I2I/R2I workflow는 아직 설치되지 않아 해당 category는 empty일 수 있다.

각 image card는 type·status·created time·prompt·checkpoint·elapsed·view count와 download/favorite/delete actions를 표시한다. image와 video download action은 signed Storage URL을 browser에서 직접 fetch하지 않고, owner-scoped `GET /vault/images/{generation_id}/download`와 `GET /vault/videos/{generation_id}/download` attachment response로 파일을 내려받는다. detail link는 `/vault/images/{generation_id}`다. video와 3D tab은 기존 category와 pagination behavior를 유지한다.
