"""
Project 8 – Educational Content Generator
Quiz generator
"""
import httpx

from app.core.config import settings


class QuizGenerator:
    async def generate_quiz(self, topic, difficulty, num_questions=5) -> list[dict]:
        system_prompt = (
            "You are an expert assessment generator. Return only valid JSON as an array of quiz questions. "
            "Each item must include question, options, correct_index, and explanation."
        )
        user_prompt = (
            f"Topic: {topic}\n"
            f"Difficulty: {difficulty}\n"
            f"Number of questions: {num_questions}\n\n"
            "Generate multiple-choice questions with four options each."
        )
        payload = {
            "model": settings.LLM_MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": settings.LLM_TEMPERATURE,
            "max_tokens": settings.LLM_MAX_TOKENS,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {settings.LLM_API_KEY}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = __import__("json").loads(content)
        if isinstance(parsed, dict) and "questions" in parsed:
            return parsed["questions"]
        if isinstance(parsed, list):
            return parsed
        raise ValueError("Quiz generator did not return a valid question list")


quiz_generator = QuizGenerator()
