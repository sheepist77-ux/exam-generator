import streamlit as st
import json
import os
from datetime import datetime
from generator import generate_questions

st.set_page_config(
    page_title="📖 숙명여중 3학년 문제 출제기",
    page_icon="📖",
    layout="centered"
)

BANK_FILE = "question_bank.json"
WRONG_FILE = "wrong_note.json"

def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 세션 초기화
for key, val in {
    "generated_questions": [],
    "current_index": 0,
    "score": 0,
    "quiz_done": False,
    "selected_original": None,
    "answered": False,
    "last_correct": None,
    "last_explanation": ""
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# 사이드바
with st.sidebar:
    st.title("⚙️ 설정")
    api_key = st.text_input("🔑 OpenAI API 키", type="password", placeholder="sk-...")
    st.markdown("---")
    st.markdown("**📌 사용 방법**")
    st.markdown("""
1. 왼쪽에 API 키 입력  
2. [기출문제 관리] 탭에서 문제 추가  
3. [문제 풀기] 탭에서 생성 & 풀기  
4. [오답 노트] 탭에서 복습  
""")

st.title("📖 숙명여중 3학년 맞춤 문제 출제기")
tab1, tab2, tab3 = st.tabs(["📥 기출문제 관리", "🧠 문제 풀기", "📒 오답 노트"])

# ───────────────────────────────────────────
# TAB 1 : 기출문제 관리
# ───────────────────────────────────────────
with tab1:
    st.subheader("기출문제 추가")
    col1, col2 = st.columns(2)
    with col1:
        subject  = st.selectbox("과목", ["수학","국어","영어","과학","사회","역사","기타"])
        topic    = st.text_input("단원/주제", placeholder="예: 이차방정식")
    with col2:
        difficulty = st.selectbox("난이도", ["하","중","상"])

    question = st.text_area("문제 내용", placeholder="기출문제를 입력하세요.")
    answer   = st.text_input("정답", placeholder="정답을 입력하세요.")

    if st.button("➕ 기출문제 저장", use_container_width=True):
        if topic and question and answer:
            bank = load_json(BANK_FILE)
            bank.append({"subject":subject,"topic":topic,
                         "question":question,"answer":answer,"difficulty":difficulty})
            save_json(BANK_FILE, bank)
            st.success("✅ 저장되었습니다!")
        else:
            st.warning("⚠️ 단원, 문제, 정답을 모두 입력해 주세요.")

    st.markdown("---")
    st.subheader("저장된 기출문제 목록")
    bank = load_json(BANK_FILE)
    if not bank:
        st.info("아직 저장된 기출문제가 없어요.")
    else:
        for i, q in enumerate(bank):
            with st.expander(f"[{q['subject']}] {q['topic']} — {q['question'][:40]}..."):
                st.write(f"**문제:** {q['question']}")
                st.write(f"**정답:** {q['answer']}")
                st.write(f"**난이도:** {q['difficulty']}")
                if st.button("🗑️ 삭제", key=f"del_{i}"):
                    bank.pop(i)
                    save_json(BANK_FILE, bank)
                    st.rerun()

# ───────────────────────────────────────────
# TAB 2 : 문제 풀기
# ───────────────────────────────────────────
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

        # 퀴즈 진행
        if st.session_state.generated_questions and not st.session_state.quiz_done:
            questions = st.session_state.generated_questions
            idx  = st.session_state.current_index
            orig = st.session_state.selected_original
            q    = questions[idx]

            st.markdown("---")
            st.progress((idx) / len(questions))
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

        # 결과 화면
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

# ───────────────────────────────────────────
# TAB 3 : 오답 노트
# ───────────────────────────────────────────
with tab3:
    wrong = load_json(WRONG_FILE)
    if not wrong:
        st.success("📒 오답 노트가 비어있어요. 아직 틀린 문제가 없어요! 🎉")
    else:
        st.subheader(f"총 {len(wrong)}개의 오답")
        subjects = list(set(w['subject'] for w in wrong))
        filt = st.selectbox("과목 필터", ["전체"] + subjects)
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
