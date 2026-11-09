import json
import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from supabase import create_client

load_dotenv()

gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

embed_model = "gemini-embedding-001"
available = [
    m.name.replace("models/", "")
    for m in gemini_client.models.list()
    if "embedContent" in (m.supported_actions or [])
]
if available and embed_model not in available:
    embed_model = available[0]
print(f"사용할 임베딩 모델: {embed_model}")

def chunk_text(text, chunk_size=1000, overlap=150):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

with open("stocktutor_posts.json", "r", encoding="utf-8") as f:
    posts = json.load(f)

print(f"총 {len(posts)}개 게시글 로드 완료. 텍스트 분할 중...")

records = []
for post in posts:
    title = post.get("title", "제목 없음")
    url = post.get("url") or post.get("link") or ""
    pub_date = post.get("date") or post.get("published_date") or ""
    body = post.get("content") or post.get("text") or post.get("body") or ""
    
    if not body.strip():
        continue
        
    for chunk in chunk_text(body):
        full_text = f"제목: {title}\n작성일: {pub_date}\n내용: {chunk}"
        records.append({
            "title": title,
            "url": url,
            "published_date": pub_date,
            "content": full_text
        })

print(f"총 {len(records)}개의 검색 조각(청크) 생성됨. Supabase 업로드를 시작합니다...")

BATCH_SIZE = 50
for i in range(0, len(records), BATCH_SIZE):
    batch = records[i:i + BATCH_SIZE]
    texts = [item["content"] for item in batch]
    
    for attempt in range(3):
        try:
            res = gemini_client.models.embed_content(
                model=embed_model,
                contents=texts,
                config=types.EmbedContentConfig(output_dimensionality=768)
            )
            rows_to_insert = []
            for item, emb in zip(batch, res.embeddings):
                rows_to_insert.append({
                    "title": item["title"],
                    "url": item["url"],
                    "published_date": item["published_date"],
                    "content": item["content"],
                    "embedding": emb.values
                })
            supabase.table("documents").insert(rows_to_insert).execute()
            print(f"진행률: {min(i + BATCH_SIZE, len(records))} / {len(records)} 완료")
            time.sleep(0.5)
            break
        except Exception as e:
            print(f"일시적 오류 발생 (재시도 {attempt + 1}/3): {e}")
            time.sleep(5)

print("모든 블로그 데이터의 Supabase 적재가 완료되었습니다!")
