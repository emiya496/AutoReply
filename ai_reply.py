# -*- coding: utf-8 -*-
from openai import OpenAI
from rich.console import Console

from config import config

console = Console()


class AIReplyGenerator:
    def __init__(self):
        self._client = OpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
        )
        self._system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        # ── Prompt 位置：ai_reply.py → AIReplyGenerator._build_system_prompt ──
        lines = [
            f"你是一位{config.BLOGGER_PERSONA}，正在小红书评论区亲自回复每一条粉丝评论。",
            f"整体风格：{config.REPLY_STYLE}。",
            "",
            "【你所处的场景】",
            "小红书评论区。受众年轻、感性，重视真实互动。",
            "你的每一条回复都必须像是专门为这条评论量身写的，",
            "读起来像真人随手打字，绝不能像套模板或机器生成。",
            "",
            "【核心原则：每条回复必须独一无二】",
            "- 必须从评论内容本身出发，抓住对方说的具体词语或情绪来回应",
            "- 绝对禁止使用相同或相似的句式，即使是同类型的评论也要措辞不同",
            "- 不要套固定公式，不要重复自己说过的话",
            "",
            "【按评论类型处理】",
            "",
            "① 商业类（涉及价格、购买方式、链接、优惠、合作、咨询、代购等）",
            "   目的：引导对方私信，但每条都要结合对方问的具体内容来说，",
            "   让对方感觉你是专门回复他/她的，而不是群发。",
            "   措辞每次都要不同，可以从以下角度变化（每次只选一个角度，自由发挥）：",
            "   - 呼应对方问的具体问题（价格/链接/优惠等）再引导私信",
            "   - 表达迫不及待想帮对方解决",
            "   - 用轻松俏皮的语气邀请私信",
            "   - 暗示私信有额外惊喜",
            "",
            "② 情绪互动类（炫耀、吐槽、感慨、开玩笑、分享经历等）",
            "   顺着对方的情绪走，共情回应。",
            "   抓住对方说的关键词或情绪点，给出有温度、有趣的回应。",
            "   不要泛泛而谈，要让对方看到你真的读懂了她说的话。",
            "",
            "③ 真诚提问类（使用感受、怎么做、推荐什么等非商业问题）",
            "   直接简洁地回答，像朋友聊天，不超过两句。",
            "",
            "④ 负面/投诉/差评类",
            "   温和共情，不争辩，表示理解，积极化解，让对方感受到被重视。",
            "",
            "【格式】",
            "- 长度15~50字",
            "- 最多1~2个emoji，不堆砌",
            "- 只输出回复正文，不加任何解释或前缀",
        ]
        return "\n".join(lines)

    def generate_reply(self, comment_content: str) -> str:
        """为单条评论生成AI回复"""
        try:
            response = self._client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"粉丝评论：「{comment_content}」\n"
                            "请根据这条评论的具体内容，写一条自然的回复。"
                            "回复里要体现出你读懂了对方说的是什么，措辞不要和其他回复重复。"
                        ),
                    },
                ],
                max_tokens=150,
                temperature=1.0,  # 提高随机性，减少重复
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            console.print(f"[red]AI生成失败: {e}[/red]")
            return ""

    def batch_generate(self, comments: list[str]) -> list[str]:
        """批量为评论列表生成回复，携带已生成内容避免重复"""
        replies = []
        history: list[str] = []  # 记录已生成的回复，传给后续请求避免雷同

        for i, comment in enumerate(comments, 1):
            console.print(f"[dim]正在生成第 {i}/{len(comments)} 条回复...[/dim]")
            reply = self._generate_with_history(comment, history)
            replies.append(reply)
            if reply:
                history.append(reply)

        return replies

    def _generate_with_history(self, comment_content: str, history: list[str]) -> str:
        """生成回复，附带历史回复列表要求AI避免雷同"""
        avoid_note = ""
        if history:
            samples = "、".join(f"「{r[:15]}…」" for r in history[-4:])
            avoid_note = f"\n注意：本批次已有回复：{samples}，你的回复措辞必须与这些完全不同。"

        try:
            response = self._client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"粉丝评论：「{comment_content}」\n"
                            "请根据这条评论的具体内容，写一条自然的回复。"
                            "回复里要体现出你读懂了对方说的是什么，措辞不要和其他回复重复。"
                            + avoid_note
                        ),
                    },
                ],
                max_tokens=150,
                temperature=1.0,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            console.print(f"[red]AI生成失败: {e}[/red]")
            return ""
