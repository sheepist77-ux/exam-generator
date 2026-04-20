import json
from openai import OpenAI

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
