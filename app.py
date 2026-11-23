import os
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types
from supabase import create_client

load_dotenv()

st.set_page_config(
    page_title="대박 AI 에이전트 - 주식 지식 튜터",
    page_icon="📈",
    layout="wide"
)

gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

EMBED_MODEL = "gemini-embedding-001"
LLM_MODEL = "gemini-3.8-flash"

SYSTEM_PROMPT = """당신은 '대박스탁'의 10년 치 블로그 철학과 시장 통찰을 계승한 '대박 AI 에이전트'입니다.

[핵심 답변 원칙]
1. 시점(날짜) 기반 역사적 고찰:
   - 검색된 과거 블로그 글들의 '작성 일자(시점)'와 당시 시장 상황을 구체적으로 인용하며 답변하세요.
   - "과거 유사한 위기나 이벤트 당시 대박스탁은 ~한 시각과 논리로 시장을 판단했습니다" 형식으로 서술하세요.

2. 통섭형 담론 및 글쓰기 스타일:
   - 단순 주가 전망이나 시황 요약에 머무르지 마세요.
   - 거시경제 흐름, 유발 하라리 식의 문명사적/인문학적 담론, 시장 참여자들의 심리, 그리고 선제적 가이드라인(포워드 가이던스)을 입체적으로 연결하는 대박스탁 특유의 깊이 있는 문체를 유지하세요.

3. 엄격한 종목 리딩 금지 (VIP 정책 및 규제 준수):
   - 특정 종목의 매수/매도 타이밍, 목표가 제시, 단기 종목 추천은 철저히 배제합니다.
   - 산업의 구조적 변화, 거시적 리스크 관리, 투자 철학과 프레임워크 관점에서만 가이드를 제공하세요.

4. 근거 기반 신뢰성:
   - 제공된 컨텍스트(과거 블로그 글)의 내용을 최우선 근거로 삼아 답변을 구성하세요.
"""

def search_documents(query_text: str, top_k: int = 5):
    emb_res = gemini_client.models.embed_content(
        model=EMBED_MODEL,
        contents=[query_text],
        config=types.EmbedContentConfig(output_dimensionality=768)
    )
    query_vector = emb_res.embeddings[0].values

    rpc_res = supabase.rpc(
        "match_documents",
        {"query_embedding": query_vector, "match_count": top_k}
    ).execute()
    return rpc_res.data or []

st.title("📈 대박 AI 에이전트")
st.caption("5,700여 개 블로그 데이터 기반 시점별 경제 분석 및 통섭형 주식 지식 튜터")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "input_text" not in st.session_state:
    st.session_state.input_text = ""

st.markdown("#### 💡 추천 질문 가이드")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("📌 [이슈 비교]\n중동 분쟁 및 유가 급등", use_container_width=True):
        st.session_state.input_text = "최근 중동 분쟁과 유가 급등 상황을 대박스탁의 과거 위기 분석 관점에서 어떻게 보나요?"

with col2:
    if st.button("🌐 [이론 연계]\n포워드 가이던스 & 시장 사이클", use_container_width=True):
        st.session_state.input_text = "대박스탁의 관점과 거시경제 포워드 가이던스/시장 사이클을 비교해 설명해 줘."

with col3:
    if st.button("📑 [기자·연구자용]\n주제별 관점 변화 발췌", use_container_width=True):
        st.session_state.input_text = "금리 변동기에 대해 대박스탁이 작성했던 핵심 글과 시점별 관점 변화를 발췌·정리해 줘."

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sources" in msg and msg["sources"]:
            with st.expander("📚 참조한 과거 블로그 원문 및 시점"):
                for src in msg["sources"]:
                    pub = src.get("published_date") or "날짜 미상"
                    title = src.get("title") or "제목 없음"
                    url = src.get("url") or "#"
                    st.markdown(f"- **[{pub}]** [{title}]({url})")

user_query = st.chat_input("질문을 입력하세요...", key="chat_input")
if not user_query and st.session_state.input_text:
    user_query = st.session_state.input_text
    st.session_state.input_text = ""

if user_query:
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        with st.spinner("과거 대박스탁 아카이브에서 관련 시점의 기록을 분석 중입니다..."):
            docs = search_documents(user_query, top_k=5)
            
            context_blocks = []
            for d in docs:
                context_blocks.append(
                    f"[[작성일: {d.get('published_date', '미상')} | 제목: {d.get('title', '무제')}]]\n{d.get('content', '')}"
                )
            context_str = "\n\n---\n\n".join(context_blocks)

            prompt = f"""[참고할 대박스탁 과거 블로그 기록]
{context_str}

[사용자 질문]
{user_query}

위 참고 기록의 시점별 맥락과 논리를 바탕으로, 시스템 지침에 따라 통섭형 답변을 작성하세요."""

            response = gemini_client.models.generate_content(
                model=LLM_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.4
                )
            )
            answer = response.text
            st.markdown(answer)

            if docs:
                with st.expander("📚 참조한 과거 블로그 원문 및 시점"):
                    for d in docs:
                        pub = d.get("published_date") or "날짜 미상"
                        title = d.get("title") or "제목 없음"
                        url = d.get("url") or "#"
                        st.markdown(f"- **[{pub}]** [{title}]({url})")

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "sources": docs
    })
