# GLB 입출력

Linux ARM64의 bpy 배포 부재를 보완하는 GLB 2.0 입출력 계층이다. 기본 scene의 node transform을 world space로 반영해 mesh를 읽고 인스턴스별로 mesh를 분리한다. 삼각형 primitive의 POSITION과 index를 입력으로 사용한다. 외부 buffer/image, required extensions, sparse accessors, 기존 skin과 morph target은 지원하지 않는다. 최대 100만 vertex·200만 face를 허용한다.

원본 GLB의 geometry·vertex color·material·texture bytes와 mesh node transform은 유지한다. 새 skeleton node, JOINTS_0·WEIGHTS_0(정점당 최대 4개 영향), node별 inverse bind matrix·skin만 추가한다. 뼈대의 cycle과 범위를 검사하고 가중치를 정규화한다. joint world matrix의 역행렬과 mesh world transform으로 inverse bind를 만들며 rest pose에서 원본 위치를 보존한다. 새로운 동작 animation은 생성하지 않는다.
