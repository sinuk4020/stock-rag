import json
import re
import time
from bs4 import BeautifulSoup
import requests

BLOG_ID = "stocktutor"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": f"https://blog.naver.com/PostList.naver?blogId={BLOG_ID}",
}


def get_all_post_metadata(blog_id):
    """1단계: 블로그의 모든 글 번호(logNo), 제목, 작성일을 가져옵니다."""
    posts_meta = []
    page = 1
    count_per_page = 30  # 한 번에 최대 30개씩 조회

    print(f"[{blog_id}] 전체 글 목록 수집 시작...")

    while True:
        url = (
            f"https://blog.naver.com/PostTitleListAsync.naver"
            f"?blogId={blog_id}&viewdate=&currentPage={page}"
            f"&categoryNo=0&parentCategoryNo=0&countPerPage={count_per_page}"
        )
        res = requests.get(url, headers=HEADERS)

        # 네이버 응답 JSON 내부의 비표준 이스케이프 문자 정제
        raw_text = res.text.replace("\\'", "'")
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            print(f"{page}페이지 JSON 파싱 오류 발생, 중단합니다.")
            break

        post_list = data.get("postList", [])
        if not post_list:
            break

        for item in post_list:
            log_no = item.get("logNo")
            # URL 인코딩된 제목 디코딩
            title = requests.utils.unquote(item.get("title", "")).replace(
                "+", " "
            )
            add_date = item.get("addDate", "")  # 예: 2018. 5. 12.

            posts_meta.append({
                "logNo": log_no,
                "title": title,
                "date": add_date,
                "url": f"https://blog.naver.com/{blog_id}/{log_no}",
            })

        print(f"페이지 {page} 완료 (누적 {len(posts_meta)}개)")

        # 마지막 페이지 도달 확인
        total_count = int(data.get("totalCount", 0))
        if len(posts_meta) >= total_count:
            break

        page += 1
        time.sleep(0.3)

    return posts_meta


def get_post_content(blog_id, log_no):
    """2단계: 모바일 페이지에서 순수 본문 텍스트만 추출합니다."""
    mobile_url = f"https://m.blog.naver.com/{blog_id}/{log_no}"
    res = requests.get(mobile_url, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")

    # 스마트에디터 ONE (최신) / 스마트에디터 2.0 (구버전) 본문 컨테이너 탐색
    content_area = (
        soup.select_one(".se-main-container")
        or soup.select_one("#postViewArea")
        or soup.select_one(".post_ct")
    )

    if not content_area:
        return ""

    # 불필요한 태그(스크립트, 스타일, 지도, 스티커 등) 제거
    for trash in content_area.select(
        "script, style, .se-oglink, .se-sticker, .__se_object"
    ):
        trash.decompose()

    # 줄바꿈을 유지하며 텍스트 추출 및 연속 공백 정리
    text = content_area.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def main():
    meta_list = get_all_post_metadata(BLOG_ID)
    print(f"\n총 {len(meta_list)}개의 게시글 목록 확보 완료. 본문 수집을 시작합니다.\n")

    results = []
    for idx, meta in enumerate(meta_list, 1):
        try:
            content = get_post_content(BLOG_ID, meta["logNo"])
            if content:
                results.append({
                    "id": meta["logNo"],
                    "title": meta["title"],
                    "date": meta["date"],
                    "url": meta["url"],
                    "content": content,
                })
            print(f"[{idx}/{len(meta_list)}] 수집 완료: {meta['title'][:30]}...")
        except Exception as e:
            print(f"[{idx}/{len(meta_list)}] 실패 ({meta['logNo']}): {e}")

        # 네이버 IP 차단 방지를 위한 딜레이 (필수)
        time.sleep(0.5)

        # 중간 유실 방지를 위해 100개 단위로 자동 백업 저장
        if idx % 100 == 0:
            with open(
                f"{BLOG_ID}_posts_backup.json", "w", encoding="utf-8"
            ) as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

    # 최종 파일 저장
    output_file = f"{BLOG_ID}_posts.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n전체 작업 완료! '{output_file}'에 총 {len(results)}개 글 저장됨.")


if __name__ == "__main__":
    main()