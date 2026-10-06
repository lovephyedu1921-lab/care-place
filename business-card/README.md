# 김무용 디지털 명함

QR을 찍으면 열리는 모바일 명함 페이지와 인쇄용 명함 파일입니다.

- 명함 주소: https://kimmuyong-card.vercel.app/
- QR 코드: `qr/kimmuyong-card-qr.png` (진한 초록) · `qr/kimmuyong-card-qr-black.png` (검정) · `qr/kimmuyong-card-qr.svg`
- 인쇄용: `print/card-print-92x52mm.pdf` (앞·뒤 2쪽, 재단 여백 1mm 포함, 완성 크기 90×50mm)
- 미리보기: `print/card-front.png`, `print/card-back.png` (300dpi)

## 폴더 구성

| 경로 | 내용 |
| --- | --- |
| `site/` | Vercel에 올라가는 명함 페이지 (`index.html`, 연락처 파일 `kimmuyong.vcf`, 공유 이미지 `og.jpg`) |
| `print/` | 인쇄용 명함 PDF·PNG와 원본 HTML |
| `qr/` | QR 코드 이미지 |
| `scripts/` | 생성 스크립트와 템플릿 (`card.json`에 이름·연락처) |

## 정보 수정하기

1. `scripts/card.json`에서 이름, 직함, 전화번호, 이메일을 고칩니다.
2. 다시 생성합니다.

   ```sh
   pip install segno
   python3 business-card/scripts/build.py
   NODE_PATH="$(npm root -g)" node business-card/scripts/render.cjs   # Playwright 필요
   ```

3. `site/` 폴더를 Vercel 프로젝트 `kimmuyong-card`에 다시 배포합니다.

명함 주소(`siteUrl`)가 바뀌지 않으면 이미 인쇄한 QR은 그대로 쓸 수 있습니다.
