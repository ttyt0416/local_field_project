# Vault 콘텐츠 목록 표시

Vault API는 Storage signed URL이 있는 이미지에는 external URL을, Local Field가 반환한 relative path에는 authenticated Blob load를 사용한다. 목록은 latest·oldest·most viewed 정렬과 server-side search, page size 10 pagination을 제공한다.

이미지 tab은 visible `IMAGE` title 없이 `ANIMA`, `ILLUSTRIOUS`, `KREA2` family tab과 그 아래 `T2I`, `I2I` mode tab을 표시한다. 기본 선택은 `ANIMA`와 `T2I`다. 선택은 `generation_mode`와 `model_family`를 함께 `GET /vault/images` 및 `DELETE /vault/images/filtered`에 보낸다. 둘 중 하나만 보낸 API request는 422로 거절한다. 따라서 목록 count, pagination, filtered delete 모두 정확한 T2I/I2I × Anima/Illustrious/Krea2 category만 대상으로 한다. Krea2는 generator workflow가 아직 없어 현재 empty category로 표시될 수 있다.

각 image card는 type·status·created time·prompt·checkpoint·elapsed·view count와 download/favorite/delete actions를 표시한다. detail link는 `/vault/images/{generation_id}`다. video와 3D tab은 기존 category와 pagination behavior를 유지한다.
