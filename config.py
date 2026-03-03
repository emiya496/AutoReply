import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    BLOGGER_PERSONA: str = os.getenv("BLOGGER_PERSONA", "个人博主")
    REPLY_STYLE: str = os.getenv("REPLY_STYLE", "友善热情")
    AUTO_REPLY: bool = os.getenv("AUTO_REPLY", "false").lower() == "true"
    DELAY_MIN: float = float(os.getenv("DELAY_MIN", "15"))
    DELAY_MAX: float = float(os.getenv("DELAY_MAX", "45"))

    # 每次运行最多回复几条（防灰评，剩余的下次再发）
    MAX_REPLIES_PER_SESSION: int = int(os.getenv("MAX_REPLIES_PER_SESSION", "3"))

    # 浏览器选择：chrome（系统Chrome） | msedge（系统Edge）
    BROWSER: str = os.getenv("BROWSER", "chrome")

    COOKIES_FILE: str = "cookies.json"
    XHS_URL: str = "https://www.xiaohongshu.com"

    @classmethod
    def validate(cls) -> bool:
        if not cls.DEEPSEEK_API_KEY or cls.DEEPSEEK_API_KEY == "your_deepseek_api_key_here":
            return False
        return True


config = Config()
