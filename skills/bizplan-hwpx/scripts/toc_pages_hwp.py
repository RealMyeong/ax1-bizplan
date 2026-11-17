"""선택 도구: 한컴 PDF 로 경량 생성물의 목차 쪽 번호를 실제 쪽에 맞춘다.

    python toc_pages_hwp.py <생성물.hwpx> -o <새 경로.hwpx> [--pdf <확인용.pdf>]

경량 생성기(build_headless_artifact.py)는 한컴을 실행하지 않으므로 목차 쪽 번호를 줄 배치·표
높이로 추정해 넣는다. 한/글은 문서를 열거나 PDF 로 바꿀 때 차례 쪽 번호를 저절로 채우지 않는다.
이 도구는 **경량 경로 밖의 선택 단계**다.

- Windows + 한컴오피스 + PowerShell COM(`HWPFrame.HwpObject`)과 PDF 글자 추출용
  PyMuPDF(`pymupdf`)가 필요하다. 한컴 창이 잠깐 보일 수 있다
- 한글 경로는 한컴이 열지 못하므로 임시 ASCII 폴더에 복사해 변환한다
- 쪽 번호는 1장 제목이 놓인 쪽을 1쪽으로 센다 (본문 쪽 번호와 같은 기준)
- 쪽 번호와 점선 탭 폭만 바꾼다. 원본은 고치지 않고 존재하지 않는 새 경로에만 쓴다.
  쓴 뒤 check_headless_artifact.py 와 같은 검사를 다시 돌린다
- CI·빌드는 이 도구를 실행하지 않는다
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True

import headless_hwpx as H  # noqa: E402
import check_headless_artifact as C  # noqa: E402

PS_EXPORT = r'''
$ErrorActionPreference = "Stop"
$hwp = New-Object -ComObject HWPFrame.HwpObject
try {{ $hwp.XHwpWindows.Item(0).Visible = $false }} catch {{}}
try {{
  $ok = $hwp.Open("{src}", "HWPX", "forceopen:true")
  if (-not $ok) {{ throw "open failed" }}
  $r = $hwp.SaveAs("{pdf}", "PDF", "")
  if (-not $r) {{ throw "pdf failed" }}
}} finally {{
  $hwp.Clear(1); $hwp.Quit()
}}
'''

TOC_LINE_RE = re.compile(r"[·.]{6,}")


def export_pdf(hwpx: Path, pdf: Path) -> None:
    """한컴 COM 으로 HWPX -> PDF. 두 경로 모두 ASCII 여야 한다."""
    if not sys.platform.startswith("win"):
        raise H.HeadlessHwpxError("한컴 PDF 변환은 Windows 에서만 실행할 수 있음")
    script = PS_EXPORT.format(src=str(hwpx), pdf=str(pdf))
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True, encoding="mbcs", errors="replace", timeout=240)
    if result.returncode != 0 or not pdf.is_file():
        raise H.HeadlessHwpxError(f"한컴 PDF 변환 실패: {(result.stderr or '').strip()[:300]}")


def heading_pages(page_texts: list, titles: list) -> list:
    """제목이 한 줄로 놓인 쪽(0부터)을 차례대로 찾는다. 점선이 있는 목차 쪽은 건너뛴다."""
    lines = [[line.strip() for line in text.splitlines()] for text in page_texts]
    toc_pages = [i for i, text in enumerate(page_texts) if TOC_LINE_RE.search(text)]
    start = toc_pages[-1] + 1 if toc_pages else 0
    found = []
    for title in titles:
        hit = next((i for i in range(start, len(lines)) if title.strip() in lines[i]), None)
        found.append(hit)
        if hit is not None:
            start = hit
    return found


def pdf_page_texts(pdf: Path) -> list:
    try:
        import pymupdf  # 선택 의존성. 경량 생성 경로는 이 도구를 쓰지 않는다
    except ImportError as exc:
        raise H.HeadlessHwpxError("PDF 글자 추출에 pymupdf 가 필요함 (pip install pymupdf)") from exc
    with pymupdf.open(str(pdf)) as doc:
        return [page.get_text() for page in doc]


def correct(src: Path, out: Path, pdf_copy: Path | None = None) -> list:
    if out.exists():
        raise H.HeadlessHwpxError(f"출력 경로가 이미 있음. 덮어쓰지 않음: {out}")
    if src.resolve() == out.resolve():
        raise H.HeadlessHwpxError("원본과 출력 경로는 달라야 함")
    entries = H.read_hwpx(src)
    header = H.get_text(entries, H.HEADER)
    section = H.get_text(entries, H.SECTION)
    toc = H.toc_entries(section)
    if not toc:
        raise H.HeadlessHwpxError("차례 필드 목차가 없는 문서")
    log = []
    with tempfile.TemporaryDirectory(prefix="ax1toc_") as temp:
        temp = Path(temp)
        export_pdf(shutil.copy2(src, temp / "in.hwpx"), temp / "in.pdf")
        found = heading_pages(pdf_page_texts(temp / "in.pdf"), [title for _, title, _, _ in toc])
        if found[0] is None:
            raise H.HeadlessHwpxError(f"PDF 에서 첫 제목을 찾지 못함: {toc[0][1]}")
        missing = [title for (_, title, _, _), index in zip(toc, found) if index is None]
        if missing:
            raise H.HeadlessHwpxError("PDF 에서 찾지 못한 제목: " + ", ".join(missing[:5]))
        pages = {target: index - found[0] + 1 for (target, _, _, _), index in zip(toc, found)}
        before = {target: page for target, _, page, _ in toc}
        regular, boldfont = H.Font(H.MALGUN), H.Font(H.MALGUN_BOLD)
        section, changed = H.set_toc_pages(section, pages, H.parse_char_prs(header), regular, boldfont)
        H.set_text(entries, H.SECTION, section)
        staged = temp / out.name  # 검사기가 파일명·버전 규칙도 보므로 최종 이름으로 둔다
        H.write_hwpx(entries, staged)
        issues = C.check(staged)
        if issues:
            raise H.HeadlessHwpxError("보정 후 자동검사 실패: "
                                      + "; ".join(f"{i['rule']}: {i['detail']}" for i in issues[:5]))
        if pdf_copy:
            export_pdf(staged, temp / "out.pdf")
            shutil.copy2(temp / "out.pdf", pdf_copy)
        H.publish_new_file(staged, out)
    log.append(f"목차 {len(toc)}개 중 쪽 번호 {changed}개 고침 -> {out}")
    log += [f"  {title}: {before[target]} -> {pages[target]}" for target, title, _, _ in toc
            if str(pages[target]) != before[target]]
    return log


def main() -> int:
    ap = argparse.ArgumentParser(description="한컴 PDF 로 목차 쪽 번호를 실제 쪽에 맞춘다 (선택 도구)")
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True, help="존재하지 않는 새 출력 경로")
    ap.add_argument("--pdf", type=Path, default=None, help="보정 뒤 확인용 PDF 저장 경로")
    args = ap.parse_args()
    try:
        for line in correct(args.input, args.out, args.pdf):
            print(line)
    except (H.HeadlessHwpxError, OSError) as exc:
        print(f"[중단] {exc}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
