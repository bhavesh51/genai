"""
Project 8 – Educational Content Generator
Socratic tutor engine
"""
import httpx

from app.core.config import settings
from app.db.redis_client import redis_client


class SocraticTutor:
    async def respond(self, session_id, user_message, topic, context_chunks) -> str:
        history_key = f"session:{session_id}"
        history = await redis_client.get_json(history_key) or []
        context_text = "\n\n".join(chunk.get("text", "") for chunk in context_chunks if chunk.get("text"))
        system_prompt = (
            "You are a Socratic tutor. Guide the learner with probing questions, short explanations, and hints. "
            "Do not simply give the answer immediately unless the learner is stuck. Use the provided curriculum context."
        )
        messages = [{"role": "system", "content": system_prompt}]
        if context_text:
            messages.append({"role": "system", "content": f"Curriculum context:\n{context_text}"})
        messages.extend(history[-20:])
        messages.append({"role": "user", "content": f"Topic: {topic}\nLearner message: {user_message}"})
        payload = {
            "model": settings.LLM_MODEL_NAME,
            "messages": messages,
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
        tutor_response = data["choices"][0]["message"]["content"].strip()
        updated_history = (history + [{"role": "user", "content": user_message}, {"role": "assistant", "content": tutor_response}])[-20:]
        await redis_client.set_json(history_key, updated_history, settings.REDIS_SESSION_TTL)
        return tutor_response


socratic_tutor = SocraticTutor()
