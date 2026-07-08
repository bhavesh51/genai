"""
Project 10 – Creative Content Generation Platform
Translator: calls the RHOAI ModelMesh NLLB-200 endpoint via httpx.
Falls back to returning the original text with an error log on any failure.
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# NLLB-200 language code mapping (FLORES-200 BCP-47 tags)
_LANGUAGE_CODE_MAP: dict = {
    "french": "fra_Latn",
    "spanish": "spa_Latn",
    "german": "deu_Latn",
    "portuguese": "por_Latn",
    "italian": "ita_Latn",
    "dutch": "nld_Latn",
    "polish": "pol_Latn",
    "russian": "rus_Cyrl",
    "chinese": "zho_Hans",
    "japanese": "jpn_Jpan",
    "korean": "kor_Hang",
    "arabic": "arb_Arab",
    "hindi": "hin_Deva",
    "turkish": "tur_Latn",
    "swedish": "swe_Latn",
}

_SOURCE_LANGUAGE = "eng_Latn"


class Translator:
    """
    Translates text from English to a target language using NLLB-200 served
    via RHOAI ModelMesh (OpenAI-compatible text generation endpoint).
    Falls back to the original text on any network or parsing error.
    """

    async def translate(self, text: str, target_language: str) -> str:
        """
        Translate text to the specified target language.

        Args:
            text:             The English source text to translate.
            target_language:  A human-readable language name (e.g. "french") or
                              a FLORES-200 tag (e.g. "fra_Latn").

        Returns:
            Translated text string, or the original text if translation fails.
        """
        # Resolve FLORES-200 tag
        lang_lower = target_language.lower().strip()
        flores_code = _LANGUAGE_CODE_MAP.get(lang_lower, target_language)

        payload = {
            "model": settings.TRANSLATION_MODEL_NAME,
            "inputs": text,
            "parameters": {
                "src_lang": _SOURCE_LANGUAGE,
                "tgt_lang": flores_code,
                "max_new_tokens": 1024,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{settings.TRANSLATION_BASE_URL}/generate",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                # ModelMesh NLLB endpoint returns a list of generation results
                if isinstance(data, list) and data:
                    return data[0].get("generated_text", text).strip()
                # Fallback for single-dict response shapes
                if isinstance(data, dict):
                    return data.get("generated_text", text).strip()
                return text

        except Exception as exc:
            logger.error(
                "Translation failed for target_language=%s: %s", target_language, exc
            )
            return text


translator = Translator()
