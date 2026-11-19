from dataclasses import dataclass
import os
from dotenv import load_dotenv
load_dotenv()
@dataclass
class Settings:
    mode: str = os.getenv('DATA_MODE', 'demo')
    llm_url: str = os.getenv('LLM_BASE_URL', 'http://127.0.0.1:8081/v1').rstrip('/')
    model: str = os.getenv('LLM_MODEL', 'qwen2.5-1.5b-instruct')
    timeout: float = float(os.getenv('LLM_TIMEOUT_SECONDS', '90'))
    token: str = os.getenv('SPTRANS_TOKEN', '')
    threshold: float = float(os.getenv('RETRIEVAL_THRESHOLD', '0.05'))
    max_age: int = int(os.getenv('MAX_DATA_AGE_SECONDS', '180'))
    version: str = os.getenv('APP_VERSION', '0.1.0')
    revision: str = os.getenv('APP_REVISION', 'local')
    metrics_token: str = os.getenv('METRICS_TOKEN', '')
    def __post_init__(self):
        if self.mode not in ('demo', 'live'):
            raise ValueError('DATA_MODE deve ser demo ou live')
