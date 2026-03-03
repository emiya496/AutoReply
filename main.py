import sys
import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import box

from config import config
from xhs_browser import XHSBrowser, Comment
from ai_reply import AIReplyGenerator

console = Console()

BANNER = """
[bold red]╔══════════════════════════════════════════╗
║   小红书 AI 智能回复工具  v1.0           ║
║   DeepSeek 驱动 · Playwright 自动化     ║
╚══════════════════════════════════════════╝[/bold red]
"""

# ── 本地已回复记录（按帖子URL分组，跨次运行持久化）─────────────
HISTORY_FILE = Path("replied_history.json")


def load_history() -> dict[str, list[str]]:
    """加载本地回复历史，格式：{ post_url: [comment_id, ...] }"""
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_history(history: dict[str, list[str]]):
    HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def mark_replied(history: dict[str, list[str]], post_url: str, comment_id: str):
    """将某条评论标记为已回复并立即持久化"""
    history.setdefault(post_url, [])
    if comment_id not in history[post_url]:
        history[post_url].append(comment_id)
    save_history(history)


# ── UI ────────────────────────────────────────────────────────

def check_config():
    if not config.validate():
        console.print(Panel(
            "[red]未检测到有效的 DeepSeek API Key！[/red]\n\n"
            "请按以下步骤配置：\n"
            "1. 复制 [bold].env.example[/bold] 为 [bold].env[/bold]\n"
            "2. 在 [bold].env[/bold] 中填入你的 DEEPSEEK_API_KEY\n"
            "   （在 https://platform.deepseek.com 注册获取）",
            title="配置缺失",
            border_style="red"
        ))
        sys.exit(1)


def display_comments_table(comments: list[Comment], replies: list[str]):
    table = Table(
        title="评论 & AI 回复预览",
        box=box.ROUNDED,
        show_lines=True,
        expand=True
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("用户", style="cyan", width=12)
    table.add_column("评论内容", style="white")
    table.add_column("AI 回复", style="green")

    for i, (comment, reply) in enumerate(zip(comments, replies), 1):
        table.add_row(
            str(i),
            comment.author[:10],
            comment.content[:80] + ("..." if len(comment.content) > 80 else ""),
            reply[:80] + ("..." if len(reply) > 80 else ""),
        )

    console.print(table)


# ── 主流程 ────────────────────────────────────────────────────

def run():
    console.print(BANNER)
    check_config()

    console.print(Panel(
        f"博主定位：[cyan]{config.BLOGGER_PERSONA}[/cyan]  |  "
        f"回复风格：[cyan]{config.REPLY_STYLE}[/cyan]  |  "
        f"自动发布：[cyan]{'是' if config.AUTO_REPLY else '否（人工确认）'}[/cyan]",
        title="当前配置",
        border_style="blue"
    ))

    # 加载跨次运行的本地回复历史
    history = load_history()

    browser = XHSBrowser()
    ai = AIReplyGenerator()

    try:
        console.print("\n[bold]► 步骤 1：启动浏览器[/bold]")
        browser.start()

        console.print("\n[bold]► 步骤 2：检查登录状态[/bold]")
        if not browser.ensure_logged_in():
            console.print("[red]登录失败，程序退出[/red]")
            return

        while True:
            console.print("\n" + "─" * 50)
            post_url = Prompt.ask(
                "\n[bold]► 步骤 3：输入帖子URL[/bold]\n  [dim]（输入 q 退出）[/dim]\n  URL"
            )
            if post_url.lower() in ("q", "quit", "exit"):
                break
            if "xiaohongshu.com" not in post_url:
                console.print("[yellow]请输入有效的小红书帖子链接[/yellow]")
                continue

            # 该帖子本地已记录的已回复 ID 集合
            local_replied_ids: set[str] = set(history.get(post_url, []))

            console.print("\n[bold]► 步骤 4：抓取评论[/bold]")
            comments = browser.get_post_comments(post_url)
            if not comments:
                console.print("[yellow]未找到评论，请检查链接或稍后重试[/yellow]")
                continue

            # 过滤：API 已标记已回复 OR 本地历史已记录 → 都跳过
            unanswered = [
                c for c in comments
                if not c.is_replied and c.comment_id not in local_replied_ids
            ]
            console.print(
                f"[green]共 {len(comments)} 条评论，"
                f"其中 {len(unanswered)} 条待回复"
                f"（已跳过 {len(comments) - len(unanswered)} 条已回复）[/green]"
            )

            if not unanswered:
                console.print("[dim]所有评论已回复，跳过[/dim]")
                continue

            # 只取本次要发的条数，再去生成 AI 回复，避免浪费 API 额度
            batch = unanswered[:config.MAX_REPLIES_PER_SESSION]
            remaining_count = len(unanswered) - len(batch)

            console.print("\n[bold]► 步骤 5：AI 生成回复[/bold]")
            console.print(
                f"[dim]本次生成 {len(batch)} 条"
                + (f"，还有 {remaining_count} 条留待下次[/dim]" if remaining_count else "[/dim]")
            )
            replies = ai.batch_generate([c.content for c in batch])

            console.print()
            display_comments_table(batch, replies)

            if not config.AUTO_REPLY:
                if not Confirm.ask("\n是否开始发布以上回复？"):
                    console.print("[dim]已跳过发布[/dim]")
                    continue

            console.print("\n[bold]► 步骤 6：发布回复[/bold]")
            console.print(
                f"[yellow]共 {len(batch)} 条，每条间隔 {config.DELAY_MIN:.0f}~{config.DELAY_MAX:.0f}s[/yellow]"
            )
            success, fail = 0, 0
            for comment, reply in zip(batch, replies):

                if not reply:
                    console.print(f"[yellow]跳过（AI未生成回复）：{comment.content[:30]}...[/yellow]")
                    # 没有回复内容也标记，避免反复尝试空回复
                    mark_replied(history, post_url, comment.comment_id)
                    continue

                console.print(f"  [dim]→ 回复 [@{comment.author}]：{reply[:40]}...[/dim]")

                if browser.post_reply(comment, reply):
                    success += 1
                    # ★ 成功后立即写入本地历史，下次跑时自动跳过
                    mark_replied(history, post_url, comment.comment_id)
                    console.print(f"  [green]✓ 成功（已记录，下次不重复）[/green]")
                else:
                    fail += 1
                    console.print(f"  [red]✗ 失败[/red]")

            console.print(
                f"\n[bold green]完成！成功 {success} 条，失败 {fail} 条[/bold green]"
            )
            if remaining_count > 0:
                console.print(
                    f"[dim]还有 {remaining_count} 条待回复，稍后再次运行继续（已自动跳过本次已发的）[/dim]"
                )

    except KeyboardInterrupt:
        console.print("\n[yellow]用户中断，正在退出...[/yellow]")
    finally:
        browser.stop()
        console.print("[dim]浏览器已关闭[/dim]")


if __name__ == "__main__":
    run()
