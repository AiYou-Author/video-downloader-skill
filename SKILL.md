---
name: video-downloader
description: >
  视频资源搜索与下载工具。集成 OmniBox 爬虫源知识 + yt-dlp 下载引擎，
  支持从 YouTube、Bilibili、TikTok 等数百个平台搜索和下载视频、音频、字幕。
  当用户输入一个剧名/电影名/关键词时，自动搜索多个平台资源并下载。

  触发关键词：
  下载视频、下视频、视频下载、download video、
  下载B站、下载bilibili、下载YouTube、下载TikTok、下载抖音、
  下个视频、视频扒下来、扒视频、提取视频、下载播放列表、
  下载字幕、提取字幕、下载音频、提取音频、视频转MP3、
  视频链接下载、m3u8下载、流媒体下载、
  搜视频、找资源、帮我下载、帮我找、有没有XX资源、
  yt-dlp、youtube-dl、搜索下载。

  当用户说"下载流浪地球2"、"帮我找XX资源并下载"、"搜一下XX并下下来"
  这类搜+下意图时，应触发此技能的 search → select → download 管道。
description_zh: "视频资源搜索下载，输入名称自动搜索多平台并下载"
description_en: "Search and download videos from YouTube, Bilibili, TikTok and hundreds of platforms"
metadata:
  {
    "openclaw":
      {
        "emoji": "🎬",
        "requires":
          {
            "optionalSecrets": ["CookiesFile"],
            "optionalConfig": ["OutputDir", "DefaultFormat", "Proxy", "PreferredSources"],
            "envMapping":
              {
                "CookiesFile": "VIDEO_DL_COOKIES_FILE",
                "OutputDir": "VIDEO_DL_OUTPUT_DIR",
                "DefaultFormat": "VIDEO_DL_DEFAULT_FORMAT",
                "Proxy": "VIDEO_DL_PROXY",
                "PreferredSources": "VIDEO_DL_SOURCES"
              }
          },
        "install":
          [
            { "id": "yt-dlp", "kind": "pip", "package": "yt-dlp", "label": "Install yt-dlp" },
            { "id": "ffmpeg", "kind": "system", "package": "ffmpeg", "label": "Install ffmpeg" }
          ]
      }
  }
---

# 视频资源搜索与下载技能

基于 yt-dlp + OmniBox Spider 知识，提供从搜索到下载的完整管道。

## 架构总览

```
用户输入名称 → search.py → 多平台搜索 → 结果聚合 → 自动/手动选择 → downloader.py → 下载完成
                                    ↑
            OmniBox Spider 知识（references/omnibox-spider/）
            用于后续扩展中国视频资源站爬虫源
```

## 首次使用

```bash
# 检查环境
bash {baseDir}/scripts/setup.sh --check-only

# 安装依赖
pip install yt-dlp --break-system-packages
apt install ffmpeg
```

## 核心用法

### 方式 1：直接搜+下载（用户最常用）

当用户说"下载流浪地球2"或"帮我下个月光骑士"时：

```bash
# 自动搜索 + 自动选择最优结果 + 下载
python3 {baseDir}/scripts/media_tool.py download "流浪地球2"

# 指定来源
python3 {baseDir}/scripts/media_tool.py download "流浪地球2" --source youtube

# 手动选择第2个结果下载
python3 {baseDir}/scripts/media_tool.py download "流浪地球2" --index 1

# 仅音频
python3 {baseDir}/scripts/media_tool.py download "演员 主题曲" --audio-only
```

### 方式 2：先搜后下

```bash
# 第一步：搜索
python3 {baseDir}/scripts/search.py "流浪地球2" --count 5

# 第二步：用户看了结果后，选择下载
python3 {baseDir}/scripts/downloader.py download "<URL>"
```

### 方式 3：已知链接直接下

```bash
python3 {baseDir}/scripts/downloader.py download "https://www.youtube.com/watch?v=xxxxx"
python3 {baseDir}/scripts/media_tool.py download "https://www.youtube.com/watch?v=xxxxx" --url
```

## 搜索模块 (search.py)

```
python3 {baseDir}/scripts/search.py <关键词> [--count N] [--sources youtube,bilibili]
```

支持的搜索源：
| 源 | 说明 |
|----|------|
| `youtube` | YouTube 搜索（默认开启） |
| `bilibili` | Bilibili/B站 搜索 |
| 更多 | 可通过 `--sources` 组合 |

输出 JSON 格式，包含标题、链接、时长、播放量、上传者。

## 统一下载工具 (media_tool.py)

```
搜索:  python3 {baseDir}/scripts/media_tool.py search "关键词"
信息:  python3 {baseDir}/scripts/media_tool.py info "关键词"
下载:  python3 {baseDir}/scripts/media_tool.py download "关键词" [选项]
```

download 子命令参数：
| 参数 | 说明 |
|------|------|
| `--url` | 把关键词当直接下载链接 |
| `--source youtube/bilibili` | 限定搜索来源 |
| `--index N` | 手动指定下载第 N 个结果 |
| `--output-dir /path/` | 输出目录 |
| `--format "best[height<=1080]"` | 格式/质量限制 |
| `--audio-only` | 仅下载音频 |
| `--subtitles` | 下载字幕 |
| `--proxy http://x:x` | 代理 |
| `--cookies /path/cookies.txt` | Cookie 文件 |
| `--quiet` | 静默模式 |

## 底层下载器 (downloader.py)

```
python3 {baseDir}/scripts/downloader.py <action> [options]
```

Action: `info` | `download` | `formats` | `check`

详细参数见下方。

## 下载选项详解

```bash
# 基础下载
python3 {baseDir}/scripts/downloader.py download "<URL>"

# 限制分辨率
python3 {baseDir}/scripts/downloader.py download "<URL>" --format "bestvideo[height<=1080]+bestaudio/best"

# 仅音频 (MP3)
python3 {baseDir}/scripts/downloader.py download "<URL>" --audio-only --audio-format mp3 --audio-quality 320

# 下载字幕并嵌入
python3 {baseDir}/scripts/downloader.py download "<URL>" --subtitles --sub-langs "zh-Hans,en" --embed-subs

# 下载播放列表
python3 {baseDir}/scripts/downloader.py download "<URL>" --playlist --playlist-start 1 --playlist-end 10

# 使用代理
python3 {baseDir}/scripts/downloader.py download "<URL>" --proxy socks5://127.0.0.1:1080

# 使用 Cookie（会员/年龄限制内容）
python3 {baseDir}/scripts/downloader.py download "<URL>" --cookies /path/to/cookies.txt

# 限速 5MB/s
python3 {baseDir}/scripts/downloader.py download "<URL>" --limit-rate 5
```

## 查看视频信息与格式

```bash
# 查看视频信息
python3 {baseDir}/scripts/downloader.py info "<URL>"

# 列出所有可用格式
python3 {baseDir}/scripts/downloader.py formats "<URL>"
```

## 用户意图识别

当用户发来文字时，按以下优先级判断：

| 用户说法 | 对应操作 |
|----------|----------|
| "下载流浪地球2" "帮我下个月光骑士" | → `media_tool.py download "剧名"` |
| "搜一下流浪地球" "有没有XX资源" | → `search.py "关键词"` |
| "把这个链接下了" + URL | → `downloader.py download "<URL>"` |
| "这首歌转MP3" + URL | → `downloader.py download "<URL>" --audio-only` |
| "这个播放列表全下了" + URL | → `downloader.py download "<URL>" --playlist` |
| "我要1080p" / "不要4K" | → 加 `--format "best[height<=1080]"` |

## 格式选择器参考

| 选择器 | 效果 |
|--------|------|
| `best` | 最佳单一文件 |
| `bestvideo+bestaudio` | 最佳视频+音频合并（默认） |
| `best[height<=1080]` | 不超过1080p |
| `bestvideo[height<=720]+bestaudio` | 720p视频+最佳音频 |
| `worst` | 最低质量 |
| `bestaudio` | 仅最佳音频 |

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VIDEO_DL_OUTPUT_DIR` | 下载目录 | `./downloads` |
| `VIDEO_DL_PROXY` | 代理地址 | 无 |
| `VIDEO_DL_COOKIES_FILE` | Cookie文件路径 | 无 |
| `VIDEO_DL_DEFAULT_FORMAT` | 默认格式选择器 | `bestvideo+bestaudio/best` |
| `VIDEO_DL_SOURCES` | 默认搜索源 | `youtube,bilibili` |

## 支持的平台

yt-dlp 支持 1000+ 网站，包括：
YouTube, Bilibili, TikTok, Twitter/X, Instagram, Facebook, Vimeo, Twitch,
Dailymotion, NicoNico, SoundCloud, 抖音, 小红书, 微博, 西瓜视频等。

完整列表：`yt-dlp --list-extractors`

## OmniBox Spider 知识库

项目中集成了 [OmniBox-Spider-Skills](https://github.com/Silent1566/OmniBox-Spider-Skills) 的参考文档
（`references/omnibox-spider/`），用于后续扩展中国视频资源站的爬虫能力：

- `getting-started.md` — 爬虫快速入门
- `api-reference.md` — OmniBox API 规范
- `js-template.md` / `py-template.md` — 爬虫脚本模板
- `javascript-sdk.md` / `python-sdk.md` — SDK 能力说明
- `lessons-learned.md` — 实战踩坑经验

### 后续扩展方向

当需要对接中国视频资源站（如 MacCMS 站、WordPress 资源站等）时：

1. 参考 `references/omnibox-spider/` 中的模板编写采集脚本
2. 在 `search.py` 中新增搜索源
3. 在 `downloader.py` 中对接 m3u8/mp4/磁力下载

---
* 参考仓库: https://github.com/Silent1566/OmniBox-Spider-Skills
