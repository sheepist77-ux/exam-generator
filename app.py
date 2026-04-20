import streamlit as st
import json
import os
from datetime import datetime
from openai import OpenAI

# ── 파일 파싱 라이브러리 ──────────────────────
import pdfplumber
import docx
from PIL import Image
import io
import base64

# ─────────────────────────────────────────────
# 기본 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="📖 숙명여중 3학년 문제 출제기",
    page_icon="📖",
    layout="centered"
)

BANK_FILE = "question_bank.json"
WRONG_FILE = "wrong_note.json"

# ─────────────────────────────────────────────
# 유틸 함수
# ─────────────────────────────────────────────
def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─────────────────────────────────────────────
# 파일에서 텍스트 추출
# ─────────────────────────────────────────────
def extract_text_from_pdf(file_bytes):
    """PDF에서 텍스트 추출"""
    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()

def extract_text_from_docx(file_bytes):
    """Word 파일에서 텍스트 추출"""
    doc = docx.Document(io.BytesIO(file_bytes))
    text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
    return text.strip()

def extract_text_from_image(file_bytes, api_key):
    """이미지에서 GPT Vision으로 텍스트 추출 (OCR)"""
    client = OpenAI(api_key=api_key)
    b64 = base64.b64encode(file_bytes).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "이 이미지에 있는 시험 문제와 정답을 빠짐없이 그대로 텍스트로 옮겨줘. "
                        "문제 번호, 문제 내용, 보기, 정답이 있으면 모두 포함해줘. "
                        "이미지에 있는 내용만 그대로 옮기고, 추가 설명은 하지 마."
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64}"
                    }
                }
            ]
        }],
        max_tokens=2000
    )
    return response.choices[0].message.content.strip()

# ─────────────────────────────────────────────
# GPT로 문제/정답 구조화 파싱
# ─────────────────────────────────────────────
def parse_questions_from_text(text, api_key, subject, difficulty):
    """추출된 텍스트에서 문제/정답을 JSON으로 파싱"""
    client = OpenAI(api_key=api_key)

    prompt = f"""
너는 시험 문제를 분석하는 전문가야.
아래 텍스트는 중학교 3학년 [{subject}] 시험지에서 추출한 내용이야.

이 텍스트에서 문제와 정답을 추출해서 반드시 JSON 배열 형식으로만 응답해.
다른 설명은 절대 하지 마.

[규칙]
- 문제 번호가 있으면 포함해서 문제 내용을 작성해
- 정답이 명시되어 있으면 그대로 사용하고, 없으면 "확인 필요"라고 써
- topic(단원/주제)은 문제 내용을 보고 적절히 추론해줘
- 난이도는 "{difficulty}"로 통일해

[출력 형식]
[
  {{
    "subject": "{subject}",
    "topic": "추론한 단원명",
    "question": "문제 전체 내용",
    "answer": "정답",
    "difficulty": "{difficulty}"
  }}
]

[추출할 텍스트]
{text}
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content)

# ─────────────────────────────────────────────
# 유사 문제 생성
# ─────────────────────────────────────────────
def generate_questions(api_key, original, num):
    client = OpenAI(api_key=api_key)
    prompt = f"""
너는 중학교 3학년 시험 문제를 출제하는 전문 교사야.
아래 기출문제를 참고해서, 동일한 개념과 난이도의 유사한 문제를 {num}개 만들어줘.
반드시 JSON 배열 형식으로만 응답해. 다른 설명은 하지 마.

[기출문제 정보]
- 과목: {original['subject']}
- 주제: {original['topic']}
- 문제: {original['question']}
- 정답: {original['answer']}
- 난이도: {original['difficulty']}

[출력 형식]
[
  {{
    "question": "문제 내용",
    "answer": "정답",
    "explanation": "풀이 설명"
  }}
]
"""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content)

# ─────────────────────────────────────────────
# 세션 초기화
# ─────────────────────────────────────────────
for key, val in {
    "generated_questions": [],
    "current_index": 0,
    "score": 0,
    "quiz_done": False,
    "selected_original": None,
    "answered": False,
    "last_correct": None,
    "last_explanation": "",
    "last_user_ans": "",
    "last_answer": ""
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ─────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ 설정")
    api_key = st.text_input("🔑 OpenAI API 키", type="password", placeholder="sk-...")
    st.markdown("---")
    st.markdown("**📌 사용 방법**")
    st.markdown("""
1. API 키 입력  
2. [기출문제 관리] 탭에서 문제 추가  
   - 직접 입력 또는  
   - 파일 업로드 (PDF/Word/이미지)  
3. [문제 풀기] 탭에서 생성 & 풀기  
4. [오답 노트] 탭에서 복습  
""")

# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
st.title("📖 숙명여중 3학년 맞춤 문제 출제기")
tab1, tab2, tab3 = st.tabs(["📥 기출문제 관리", "🧠 문제 풀기", "📒 오답 노트"])

# ═════════════════════════════════════════════
# TAB 1 : 기출문제 관리
# ═════════════════════════════════════════════
with tab1:

    # ── 입력 방식 선택 ──────────────────────────
    input_mode = st.radio(
        "입력 방식 선택",
        ["✏️ 직접 입력", "📂 파일 업로드 (PDF / Word / 이미지)"],
        horizontal=True
    )

    st.markdown("---")

    # ────────────────────────────────────────────
    # 직접 입력
    # ────────────────────────────────────────────
    if input_mode == "✏️ 직접 입력":
        st.subheader("기출문제 직접 입력")
        col1, col2 = st.columns(2)
        with col1:
            subject    = st.selectbox("과목", ["수학","국어","영어","과학","사회","역사","기타"])
            topic      = st.text_input("단원/주제", placeholder="예: 이차방정식")
        with col2:
            difficulty = st.selectbox("난이도", ["하","중","상"])

        question = st.text_area("문제 내용", placeholder="기출문제를 입력하세요.")
        answer   = st.text_input("정답", placeholder="정답을 입력하세요.")

        if st.button("➕ 기출문제 저장", use_container_width=True):
            if topic and question and answer:
                bank = load_json(BANK_FILE)
                bank.append({
                    "subject": subject, "topic": topic,
                    "question": question, "answer": answer,
                    "difficulty": difficulty
                })
                save_json(BANK_FILE, bank)
                st.success("✅ 저장되었습니다!")
            else:
                st.warning("⚠️ 단원, 문제, 정답을 모두 입력해 주세요.")

    # ────────────────────────────────────────────
    # 파일 업로드
    # ────────────────────────────────────────────
    else:
        st.subheader("📂 파일로 기출문제 자동 추출")

        if not api_key:
            st.warning("🔑 왼쪽 사이드바에 OpenAI API 키를 먼저 입력해 주세요.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                up_subject    = st.selectbox("과목", ["수학","국어","영어","과학","사회","역사","기타"],
                                             key="up_subject")
            with col2:
                up_difficulty = st.selectbox("난이도", ["하","중","상"], key="up_diff")

            uploaded_file = st.file_uploader(
                "파일을 업로드하세요",
                type=["pdf", "docx", "jpg", "jpeg", "png"],
                help="PDF, Word(.docx), 이미지(JPG/PNG) 파일을 지원합니다."
            )

            if uploaded_file:
                file_bytes = uploaded_file.read()
                file_type  = uploaded_file.name.split(".")[-1].lower()

                # 이미지 미리보기
                if file_type in ["jpg", "jpeg", "png"]:
                    st.image(file_bytes, caption="업로드된 이미지", use_container_width=True)

                st.info(f"📄 파일명: `{uploaded_file.name}` | 형식: `{file_type.upper()}`")

                if st.button("🔍 문제 자동 추출하기", use_container_width=True):
                    with st.spinner("파일을 분석하고 있어요... 잠시만 기다려 주세요 ⏳"):
                        try:
                            # 1단계: 텍스트/내용 추출
                            if file_type == "pdf":
                                raw_text = extract_text_from_pdf(file_bytes)
                                if not raw_text:
                                    st.warning("⚠️ PDF에서 텍스트를 찾지 못했어요. 이미지 형태의 PDF일 수 있어요.")
                                    st.stop()

                            elif file_type == "docx":
                                raw_text = extract_text_from_docx(file_bytes)

                            elif file_type in ["jpg", "jpeg", "png"]:
                                raw_text = extract_text_from_image(file_bytes, api_key)

                            # 2단계: GPT로 문제/정답 구조화
                            parsed = parse_questions_from_text(
                                raw_text, api_key, up_subject, up_difficulty
                            )

                            # 결과 미리보기
                            st.success(f"✅ {len(parsed)}개의 문제가 추출되었습니다!")
                            st.markdown("### 📋 추출된 문제 미리보기")
                            st.markdown("내용을 확인하고 저장 버튼을 눌러주세요.")

                            st.session_state["parsed_preview"] = parsed

                        except Exception as e:
                            st.error(f"❌ 추출 실패: {e}")

            # 미리보기 & 저장
            if "parsed_preview" in st.session_state and st.session_state["parsed_preview"]:
                parsed = st.session_state["parsed_preview"]

                for i, q in enumerate(parsed):
                    with st.expander(f"[문제 {i+1}] {q.get('question','')[:50]}...", expanded=True):
                        col_a, col_b = st.columns(2)
                        with col_a:
                            parsed[i]["subject"] = st.selectbox(
                                "과목", ["수학","국어","영어","과학","사회","역사","기타"],
                                index=["수학","국어","영어","과학","사회","역사","기타"].index(
                                    q.get("subject","기타")
                                ) if q.get("subject","기타") in ["수학","국어","영어","과학","사회","역사","기타"] else 6,
                                key=f"ps_{i}"
                            )
                            parsed[i]["topic"] = st.text_input(
                                "단원/주제", value=q.get("topic",""), key=f"pt_{i}"
                            )
                        with col_b:
                            parsed[i]["difficulty"] = st.selectbox(
                                "난이도", ["하","중","상"],
                                index=["하","중","상"].index(q.get("difficulty","중"))
                                      if q.get("difficulty","중") in ["하","중","상"] else 1,
                                key=f"pd_{i}"
                            )

                        parsed[i]["question"] = st.text_area(
                            "문제 내용", value=q.get("question",""), key=f"pq_{i}"
                        )
                        parsed[i]["answer"] = st.text_input(
                            "정답", value=q.get("answer",""), key=f"pa_{i}"
                        )

                col_save, col_clear = st.columns(2)
                with col_save:
                    if st.button("💾 전체 저장하기", use_container_width=True, type="primary"):
                        bank = load_json(BANK_FILE)
                        bank.extend(parsed)
                        save_json(BANK_FILE, bank)
                        st.session_state["parsed_preview"] = []
                        st.success(f"✅ {len(parsed)}개 문제가 모두 저장되었습니다!")
                        st.rerun()
                with col_clear:
                    if st.button("🗑️ 취소", use_container_width=True):
                        st.session_state["parsed_preview"] = []
                        st.rerun()

    # ── 저장된 기출문제 목록 ────────────────────
    st.markdown("---")
    st.subheader("저장된 기출문제 목록")
    bank = load_json(BANK_FILE)

    if not bank:
        st.info("아직 저장된 기출문제가 없어요.")
    else:
        # 과목 필터
        all_subjects = list(set(q["subject"] for q in bank))
        filt = st.selectbox("과목 필터", ["전체"] + all_subjects, key="bank_filter")
        filtered_bank = bank if filt == "전체" else [q for q in bank if q["subject"] == filt]

        st.markdown(f"**총 {len(filtered_bank)}개**")
        for i, q in enumerate(filtered_bank):
            real_idx = bank.index(q)
            with st.expander(f"[{q['subject']}] {q['topic']} — {q['question'][:40]}..."):
                st.write(f"**문제:** {q['question']}")
                st.write(f"**정답:** {q['answer']}")
                st.write(f"**난이도:** {q['difficulty']}")
                if st.button("🗑️ 삭제", key=f"del_{real_idx}"):
                    bank.pop(real_idx)
                    save_json(BANK_FILE, bank)
                    st.rerun()

# ═════════════════════════════════════════════
# TAB 2 : 문제 풀기
# ═════════════════════════════════════════════
with tab2:
    bank = load_json(BANK_FILE)

    if not bank:
        st.info("먼저 [기출문제 관리] 탭에서 기출문제를 추가해 주세요.")
    elif not api_key:
        st.warning("🔑 왼쪽 사이드바에 OpenAI API 키를 입력해 주세요.")
    else:
        options = [f"[{q['subject']}] {q['topic']} — {q['question'][:35]}..." for q in bank]
        sel_idx = st.selectbox("📌 기출문제 선택", range(len(options)),
                               format_func=lambda x: options[x])
        num_q = st.slider("생성할 문제 수", 1, 5, 3)

        if st.button("🤖 유사 문제 생성하기", use_container_width=True):
            with st.spinner("GPT가 문제를 만들고 있어요... ✏️"):
                try:
                    generated = generate_questions(api_key, bank[sel_idx], num_q)
                    st.session_state.generated_questions = generated
                    st.session_state.selected_original   = bank[sel_idx]
                    st.session_state.current_index = 0
                    st.session_state.score         = 0
                    st.session_state.quiz_done     = False
                    st.session_state.answered      = False
                    st.session_state.last_correct  = None
                    st.session_state.last_explanation = ""
                    st.success(f"✅ {len(generated)}개 문제 생성 완료!")
                except Exception as e:
                    st.error(f"❌ 오류: {e}")

        if st.session_state.generated_questions and not st.session_state.quiz_done:
            questions = st.session_state.generated_questions
            idx  = st.session_state.current_index
            orig = st.session_state.selected_original
            q    = questions[idx]

            st.markdown("---")
            st.progress(idx / len(questions))
            st.markdown(f"**{idx+1} / {len(questions)} 문제**")
            st.markdown(f"### ❓ 문제 {idx+1}")
            st.info(q['question'])

            if not st.session_state.answered:
                user_ans = st.text_input("✏️ 내 답 입력", key=f"ans_{idx}")
                if st.button("✅ 제출", use_container_width=True, key=f"sub_{idx}"):
                    correct  = q['answer'].strip()
                    is_right = user_ans.strip() == correct
                    st.session_state.answered         = True
                    st.session_state.last_correct     = is_right
                    st.session_state.last_explanation = q.get('explanation','')
                    st.session_state.last_user_ans    = user_ans
                    st.session_state.last_answer      = correct
                    if is_right:
                        st.session_state.score += 1
                    else:
                        wrong = load_json(WRONG_FILE)
                        wrong.append({
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "subject": orig['subject'],
                            "topic":   orig['topic'],
                            "question": q['question'],
                            "my_answer": user_ans,
                            "correct_answer": correct,
                            "explanation": q.get('explanation','')
                        })
                        save_json(WRONG_FILE, wrong)
                    st.rerun()
            else:
                if st.session_state.last_correct:
                    st.success("🎉 정답입니다!")
                else:
                    st.error(f"❌ 오답!  정답: **{st.session_state.last_answer}**")
                    st.markdown(f"📖 **풀이:** {st.session_state.last_explanation}")

                if idx + 1 < len(questions):
                    if st.button("➡️ 다음 문제", use_container_width=True):
                        st.session_state.current_index += 1
                        st.session_state.answered = False
                        st.rerun()
                else:
                    if st.button("🏁 결과 보기", use_container_width=True):
                        st.session_state.quiz_done = True
                        st.rerun()

        if st.session_state.quiz_done:
            questions = st.session_state.generated_questions
            score = st.session_state.score
            total = len(questions)
            pct   = score / total

            st.markdown("---")
            st.markdown("## 🏆 최종 결과")
            st.metric("점수", f"{score} / {total}",
                      delta="만점!" if pct==1.0 else f"{int(pct*100)}점")

            if pct == 1.0:
                st.balloons()
                st.success("🎉 완벽해요! 모두 맞혔어요!")
            elif pct >= 0.7:
                st.success("👍 잘 했어요! 조금만 더 복습하면 완벽해요.")
            else:
                st.warning("📚 오답 노트를 꼭 복습해 보세요!")

            if st.button("🔄 처음부터 다시 풀기", use_container_width=True):
                st.session_state.generated_questions = []
                st.session_state.quiz_done = False
                st.rerun()

# ═════════════════════════════════════════════
# TAB 3 : 오답 노트
# ═════════════════════════════════════════════
with tab3:
    wrong = load_json(WRONG_FILE)
    if not wrong:
        st.success("📒 오답 노트가 비어있어요. 아직 틀린 문제가 없어요! 🎉")
    else:
        st.subheader(f"총 {len(wrong)}개의 오답")
        subjects = list(set(w['subject'] for w in wrong))
        filt = st.selectbox("과목 필터", ["전체"] + subjects, key="wrong_filter")
        filtered = wrong if filt == "전체" else [w for w in wrong if w['subject'] == filt]

        for item in reversed(filtered):
            with st.expander(f"[{item['subject']}] {item['topic']} — {item['date']}"):
                st.write(f"**문제:** {item['question']}")
                st.write(f"**내 답:** {item['my_answer']}")
                st.write(f"**정답:** {item['correct_answer']}")
                st.write(f"**풀이:** {item['explanation']}")

        st.markdown("---")
        if st.button("🗑️ 오답 노트 전체 삭제", type="secondary"):
            save_json(WRONG_FILE, [])
            st.rerun()
