"""
Project 8 – Educational Content Generator
Lesson content generator
"""
import httpx

from app.core.config import settings


class ContentGenerator:
    async def generate_lesson(self, topic, difficulty, context_chunks) -> str:
        context_text = "\n\n".join(chunk.get("text", "") for chunk in context_chunks if chunk.get("text"))
        system_prompt = (
            "You are an expert educational content generator. Create a clear, accurate, well-structured lesson "
            "tailored to the learner difficulty level. Use the retrieved curriculum context when relevant, "
            "avoid hallucinations, and explain concepts with examples."
        )
        user_prompt = (
            f"Topic: {topic}\n"
            f"Difficulty: {difficulty}\n\n"
            f"Curriculum context:\n{context_text or 'No curriculum context provided.'}\n\n"
            "Generate a self-contained lesson with a short introduction, core explanation, practical example, "
            "and summary."
        )
        payload = {
            "model": settings.LLM_MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": settings.LLM_TEMPERATURE,
            "max_tokens": settings.LLM_MAX_TOKENS,
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
        return data["choices"][0]["message"]["content"].strip()


content_generator = ContentGenerator()
