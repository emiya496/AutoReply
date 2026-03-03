import json
import time
import random
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, Response
from rich.console import Console
from rich.prompt import Confirm

from config import config

console = Console()


@dataclass
class Comment:
    comment_id: str
    author: str
    content: str
    like_count: int = 0
    is_replied: bool = False


class XHSBrowser:
    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._collected_comments: list[Comment] = []

    def start(self):
        self._playwright = sync_playwright().start()
        # 优先用系统已装的 Chrome，其次 Edge，无需额外下载 Chromium
        self._browser = self._playwright.chromium.launch(
            channel=config.BROWSER,    # "chrome" 或 "msedge"，在 .env 里配置
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
        )
        # 隐藏 webdriver 标记
        self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        self.page = self._context.new_page()
        self._load_cookies()

    def stop(self):
        if self._playwright:
            self._playwright.stop()

    # ── Cookie 持久化 ──────────────────────────────────────────
    def _load_cookies(self):
        cookies_path = Path(config.COOKIES_FILE)
        if cookies_path.exists():
            with open(cookies_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            self._context.add_cookies(cookies)
            console.print("[dim]已加载保存的登录状态[/dim]")

    def _save_cookies(self):
        cookies = self._context.cookies()
        with open(config.COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        console.print("[dim]登录状态已保存，下次运行无需重新登录[/dim]")

    # ── 登录 ──────────────────────────────────────────────────
    def ensure_logged_in(self) -> bool:
        self.page.goto(config.XHS_URL, wait_until="domcontentloaded")
        time.sleep(2)

        # 检查是否已登录（已登录时右上角有头像/用户名）
        if self._is_logged_in():
            console.print("[green]✓ 检测到已登录状态[/green]")
            return True

        console.print("[yellow]请在弹出的浏览器窗口中扫码登录小红书...[/yellow]")
        console.print("[dim]登录成功后请按回车继续[/dim]")

        # 等待用户手动登录
        input()

        if self._is_logged_in():
            self._save_cookies()
            console.print("[green]✓ 登录成功！[/green]")
            return True

        console.print("[red]登录失败，请重试[/red]")
        return False

    def _is_logged_in(self) -> bool:
        try:
            # 检查是否存在登录后才有的元素（头像或用户名区域）
            avatar = self.page.locator("//div[contains(@class,'user-info') or contains(@class,'avatar')]")
            return avatar.count() > 0
        except Exception:
            return False

    # ── 抓取评论 ──────────────────────────────────────────────
    def get_post_comments(self, post_url: str) -> list[Comment]:
        self._collected_comments = []

        # 监听网络响应，拦截评论API
        self.page.on("response", self._on_response)

        console.print(f"[dim]正在打开帖子: {post_url}[/dim]")
        self.page.goto(post_url, wait_until="domcontentloaded")
        time.sleep(3)

        # 滚动评论区，触发加载
        self._scroll_to_load_comments()

        # 停止监听
        self.page.remove_listener("response", self._on_response)

        # 如果API拦截未抓到，尝试页面解析兜底
        if not self._collected_comments:
            self._collected_comments = self._parse_comments_from_dom()

        console.print(f"[green]共找到 {len(self._collected_comments)} 条评论[/green]")
        return self._collected_comments

    def _on_response(self, response: Response):
        """拦截小红书评论API响应"""
        url = response.url
        if "comment" in url and ("page" in url or "list" in url):
            try:
                data = response.json()
                self._extract_comments_from_api(data)
            except Exception:
                pass

    def _extract_comments_from_api(self, data: dict):
        """从API响应JSON中提取评论数据"""
        try:
            comments_raw = (
                data.get("data", {}).get("comments", [])
                or data.get("data", {}).get("items", [])
                or data.get("comments", [])
            )
            for item in comments_raw:
                cmt = self._parse_comment_item(item)
                if cmt:
                    self._collected_comments.append(cmt)
        except Exception:
            pass

    def _parse_comment_item(self, item: dict) -> Optional[Comment]:
        try:
            comment_id = item.get("id", "") or item.get("comment_id", "")
            content = item.get("content", "") or item.get("note_content", "")
            author_info = item.get("user_info", {}) or item.get("author", {})
            author = author_info.get("nickname", "") or author_info.get("name", "用户")
            like_count = item.get("like_count", 0) or 0
            status = item.get("status", {})
            is_replied = status.get("is_author_liked", False) if isinstance(status, dict) else False

            if content and comment_id:
                return Comment(
                    comment_id=str(comment_id),
                    author=str(author),
                    content=str(content),
                    like_count=int(like_count),
                    is_replied=bool(is_replied),
                )
        except Exception:
            pass
        return None

    def _scroll_to_load_comments(self):
        """滚动页面触发评论懒加载"""
        for _ in range(5):
            self.page.evaluate("window.scrollBy(0, 600)")
            time.sleep(random.uniform(0.8, 1.5))

    def _parse_comments_from_dom(self) -> list[Comment]:
        """兜底：直接从DOM解析评论"""
        comments = []
        try:
            comment_items = self.page.locator(
                "//div[contains(@class,'comment-item')]"
            ).all()
            for i, item in enumerate(comment_items):
                content = item.inner_text().strip()
                if content:
                    comments.append(
                        Comment(
                            comment_id=f"dom_{i}",
                            author="用户",
                            content=content[:200],
                        )
                    )
        except Exception:
            pass
        return comments

    # ── 发布回复 ──────────────────────────────────────────────
    def post_reply(self, comment: Comment, reply_text: str) -> bool:
        """点击评论的回复按钮，输入回复内容并提交"""
        try:
            # ── 1. 点击回复按钮 ──────────────────────────────────
            if not self._click_reply_btn(comment):
                console.print("[yellow]  未找到回复按钮，跳过[/yellow]")
                return False
            time.sleep(1.0)

            # ── 2. 定位输入框（依次尝试多个选择器）──────────────
            input_box = None
            for sel in [
                "textarea[placeholder*='回复']",
                "textarea[placeholder*='评论']",
                "textarea",
                "[contenteditable='true']",
            ]:
                try:
                    loc = self.page.locator(sel).last
                    loc.wait_for(state="visible", timeout=3000)
                    input_box = loc
                    break
                except Exception:
                    continue

            if input_box is None:
                console.print("[red]  未找到回复输入框[/red]")
                return False

            # ── 3. 输入内容（keyboard.type 兼容 contenteditable）─
            input_box.click()
            time.sleep(0.2)
            self.page.keyboard.press("Control+a")
            self.page.keyboard.press("Delete")
            self.page.keyboard.type(reply_text, delay=30)
            time.sleep(random.uniform(0.3, 0.8))

            # ── 4. 点击发送（依次尝试多个选择器）────────────────
            sent = False
            for sel in [
                "button:has-text('发送')",
                "span:has-text('发送')",
                "[class*='submit']",
                "[class*='send']",
            ]:
                try:
                    btn = self.page.locator(sel).last
                    btn.wait_for(state="visible", timeout=3000)
                    btn.click()
                    sent = True
                    break
                except Exception:
                    continue

            if not sent:
                # 最后兜底：按 Enter 提交
                self.page.keyboard.press("Enter")

            # ── 5. 发完后模拟真人浏览行为，降低连续操作风险 ───
            wait = random.uniform(config.DELAY_MIN, config.DELAY_MAX)
            console.print(f"  [dim]等待 {wait:.0f}s 后继续...[/dim]")
            self._human_browsing_pause(wait)
            return True

        except Exception as e:
            console.print(f"[red]回复失败: {e}[/red]")
            return False

    def _human_browsing_pause(self, total_seconds: float):
        """模拟真人发完评论后的自然浏览行为，避免机器人特征"""
        elapsed = 0.0

        # 第一段：发完后短暂停顿（像在看自己刚发的回复）
        pause = random.uniform(1.5, 3.0)
        time.sleep(pause)
        elapsed += pause

        # 随机向上/向下滚动几次，模拟在看其他评论
        scroll_count = random.randint(2, 5)
        for _ in range(scroll_count):
            direction = random.choice([1, -1])
            distance = random.randint(150, 400)
            self.page.evaluate(f"window.scrollBy(0, {direction * distance})")
            time.sleep(random.uniform(0.5, 1.5))
            elapsed += 1.0

        # 剩余时间随机分段等待（模拟在读内容）
        remaining = total_seconds - elapsed
        while remaining > 0:
            chunk = min(random.uniform(2.0, 5.0), remaining)
            time.sleep(chunk)
            remaining -= chunk

    def _click_reply_btn(self, comment: Comment) -> bool:
        """找到并点击对应评论的回复按钮。
        用 JS 从文字节点向上爬 DOM，精准找到该评论容器内的"回复"按钮，
        避免 XPath contains() 匹配到最外层容器导致总点第一条的问题。
        """
        # 取前20字作为锚点，转义单引号防止JS语法错误
        snippet = comment.content[:20].replace("\\", "\\\\").replace("'", "\\'")

        clicked = self.page.evaluate(f"""
            () => {{
                const walker = document.createTreeWalker(
                    document.body, NodeFilter.SHOW_TEXT, null, false
                );
                let node;
                while ((node = walker.nextNode())) {{
                    if (!node.textContent.includes('{snippet}')) continue;
                    // 从匹配的文字节点向上最多爬10层，找最近的"回复"按钮
                    let el = node.parentElement;
                    for (let i = 0; i < 10; i++) {{
                        if (!el || el === document.body) break;
                        const btns = el.querySelectorAll('span, button');
                        for (const btn of btns) {{
                            if (btn.textContent.trim() === '回复') {{
                                btn.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                                btn.click();
                                return true;
                            }}
                        }}
                        el = el.parentElement;
                    }}
                }}
                return false;
            }}
        """)

        if clicked:
            return True

        # 兜底：找所有"回复"按钮，点第一个可见的（至少不报错）
        for sel in ["span:text-is('回复')", "button:text-is('回复')"]:
            try:
                btn = self.page.locator(sel).first
                btn.wait_for(state="visible", timeout=5000)
                btn.click()
                return True
            except Exception:
                continue

        return False
