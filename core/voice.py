import logging
import os

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class VoiceService:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")

        # Debug Key (print first 10 chars)
        if self.api_key:
            masked_key = f"{self.api_key[:4]}...{self.api_key[-4:]}" if len(self.api_key) > 8 else "***"
            logger.info(f"VoiceService loaded GROQ key: {masked_key}")
        else:
            logger.warning("GROQ_API_KEY not found. Voice transcription will fail.")

        # Check for Proxy
        proxy_url = os.getenv("PROXY_URL")  # e.g. http://127.0.0.1:8080
        http_client = None
        if proxy_url:
            try:
                import httpx
                logger.debug(f"VoiceService using proxy: {proxy_url}")
                http_client = httpx.Client(proxy=proxy_url)
            except ImportError:
                logger.warning("PROXY_URL defined but 'httpx' not installed. Ignoring proxy.")

        # FIX: Default to Groq URL if not set, otherwise it hits OpenAI
        base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        
        # Pass dummy key if None to avoid immediate validation error in some SDK versions
        self.client = AsyncOpenAI(base_url=base_url, api_key=self.api_key or "dummy", http_client=http_client)
        self.model = "whisper-large-v3"

    async def transcribe(self, audio_file_path: str) -> str:
        """
        Transcribes an audio file using Groq's Whisper model.
        Returns the text.
        """
        if not self.api_key:
            return "Error: No GROQ_API_KEY provided."

        try:
            if not os.path.exists(audio_file_path):
                return f"Error: Audio file not found at {audio_file_path}"

            with open(audio_file_path, "rb") as file:
                logger.debug(f"Sending audio to Whisper model ({self.client.base_url})...")
                # FIX: Pass file object directly to avoid loading large files into RAM
                transcription = await self.client.audio.transcriptions.create(
                    file=file,
                    model=self.model,
                    response_format="text",  # or json
                )

            # OpenAI client usually returns an object if format is json, or str if text
            # Groq implementation might vary, but 'text' format ensures string
            return str(transcription)

        except Exception as e:
            logger.error(f"Transcription Failed: {e}")
            return f"Transcription Failed: {str(e)}"
