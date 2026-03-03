# 小红书 AI 智能回复工具

自动抓取小红书帖子评论，使用 DeepSeek AI 分析评论意图并生成个性化回复，自动发布——专为个人博主粉丝互动场景设计。

---

## 功能特点

- 自动登录小红书（扫码一次，Cookie 持久化，下次无需重复登录）
- 拦截网络请求精准抓取评论数据
- DeepSeek AI 按评论类型智能生成回复：
  - 价格/链接/咨询类 → 引导私信
  - 情绪互动类 → 共情回应
  - 真诚提问类 → 直接解答
  - 负面/投诉类 → 温和化解
- 本地记录已回复评论 ID，重复运行自动跳过，不浪费 API 额度
- 模拟真人浏览行为（随机延时 + 滚动），降低被平台检测风险
- 每次最多发 N 条（可配置），防止触发灰评屏蔽

---

## 环境要求

| 依赖 | 版本要求 |
|------|---------|
| Python | 3.10 及以上 |
| Google Chrome 或 Microsoft Edge | 系统已安装即可，无需额外下载浏览器 |
| DeepSeek API Key | 在 [platform.deepseek.com](https://platform.deepseek.com) 注册获取 |

---

## 安装步骤

**1. 克隆项目**

```bash
git clone https://github.com/你的用户名/你的仓库名.git
cd 你的仓库名
```

**2. 创建虚拟环境并安装依赖**

```bash
# Windows
python -m venv venv
venv\Scripts\pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**3. 配置环境变量**

复制示例文件并填写配置：

```bash
copy .env.example .env
```

用记事本或任意编辑器打开 `.env`，填写以下内容：

```env
DEEPSEEK_API_KEY=你的DeepSeek密钥

BLOGGER_PERSONA=个人博主       # 你的博主定位，影响 AI 回复风格
REPLY_STYLE=友善热情            # 回复风格

AUTO_REPLY=false               # false=发布前人工确认；true=全自动发布
BROWSER=chrome                 # chrome 或 msedge

DELAY_MIN=15                   # 每条回复最短间隔（秒），建议不低于15
DELAY_MAX=45                   # 每条回复最长间隔（秒）
MAX_REPLIES_PER_SESSION=3      # 每次运行最多发几条（防灰评）
```

---

## 使用方法

**运行工具：**

```bash
venv\Scripts\python main.py
```

**首次使用流程：**

1. 程序自动打开 Chrome/Edge 浏览器
2. 在浏览器中手动扫码登录小红书
3. 登录成功后回到终端按回车
4. 粘贴帖子链接，程序自动抓取评论
5. AI 生成回复后展示预览表格
6. 确认后自动发布，每条发完随机等待

**后续运行：**

- Cookie 已保存，无需重复登录
- 已回复的评论自动跳过，从上次中断的地方继续
- 每次只调用 `MAX_REPLIES_PER_SESSION` 次 AI API，节省额度

---

## 项目结构

```
├── main.py               # 主入口，交互式 CLI
├── config.py             # 配置管理（读取 .env）
├── xhs_browser.py        # Playwright 浏览器自动化客户端
├── ai_reply.py           # DeepSeek AI 回复生成
├── requirements.txt      # Python 依赖
├── .env.example          # 环境变量模板
├── .env                  # 你的配置（本地，不上传）
├── cookies.json          # 登录状态缓存（自动生成，不上传）
└── replied_history.json  # 已回复记录（自动生成，不上传）
```

---

## 防灰评说明

小红书对短时间内连续相似操作有检测机制，触发后评论仅自己可见。本工具已内置以下策略：

- 每条回复间隔 15~45 秒随机延时
- 发完后模拟真人滚动、阅读页面
- 每次最多发 3 条，剩余留到下次运行
- AI 每条回复措辞不同，避免重复内容检测

建议：每批发完后间隔 1~2 小时再运行下一批。

---

## 常见问题

**Q：回复失败 / 未找到回复按钮**
A：小红书页面可能未完全加载，稍等几秒后重试；或检查是否已登录。

**Q：评论抓取为 0 条**
A：部分帖子评论区结构特殊，尝试手动滚动页面后再次粘贴链接。

**Q：想换 Edge 浏览器**
A：在 `.env` 中将 `BROWSER=chrome` 改为 `BROWSER=msedge`。

**Q：AI 回复质量不满意**
A：修改 `.env` 中的 `BLOGGER_PERSONA` 和 `REPLY_STYLE`，或直接编辑 `ai_reply.py` 中 `_build_system_prompt` 方法调整 Prompt。

---

## 注意事项

- 本工具仅供学习和个人账号运营使用，请遵守小红书平台使用规范
- API Key 和 Cookie 文件已加入 `.gitignore`，不会被上传到 GitHub
- DeepSeek API 按 Token 计费，`MAX_REPLIES_PER_SESSION=3` 时每次运行费用极低
