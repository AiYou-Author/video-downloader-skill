# Supported Platforms Reference

yt-dlp supports 1000+ sites. Common ones grouped by region/category:

## Global

| Site | URL Pattern | Notes |
|------|-------------|-------|
| YouTube | `youtube.com/watch?v=`, `youtu.be/` | Playlists, Shorts, Music |
| Vimeo | `vimeo.com/` | |
| Dailymotion | `dailymotion.com/video/` | |
| Twitch | `twitch.tv/videos/` | VOD only |
| TikTok | `tiktok.com/@user/video/` | |
| Instagram | `instagram.com/reel/`, `instagram.com/p/` | |
| Facebook | `facebook.com/watch/` | |
| Twitter/X | `x.com/*/status/`, `twitter.com/*/status/` | |
| Reddit | `reddit.com/r/*/comments/` | |
| SoundCloud | `soundcloud.com/` | Audio |
| Mixcloud | `mixcloud.com/` | Audio |
| Pornhub | `pornhub.com/view_video.php` | Age-restricted |
| Xvideos | `xvideos.com/video` | |

## Chinese Platforms

| Site | URL Pattern | Notes |
|------|-------------|-------|
| Bilibili | `bilibili.com/video/BV`, `b23.tv/` | Episodes, live replays |
| 抖音 | `douyin.com/video/` | |
| 小红书 | `xiaohongshu.com/` | Limited support |
| 知乎 | `zhihu.com/` | |
| 微博 | `weibo.com/`, `weibo.cn/` | |
| 西瓜视频 | `ixigua.com/` | |
| 优酷 | `youku.com/` | Partial |
| 爱奇艺 | `iqiyi.com/` | Partial |
| 腾讯视频 | `v.qq.com/` | Partial |

## Japanese Platforms

| Site | URL Pattern | Notes |
|------|-------------|-------|
| NicoNico | `nicovideo.jp/watch/` | |
| FC2 Video | `video.fc2.com/` | |

## Format Notes

- **Bilibili**: Some premium content requires login cookies. High-quality audio may need `--format` selection.
- **YouTube**: age-restricted videos require cookies. Region-locked videos may need proxy.
- **TikTok**: watermarked by default; watermark-free needs specific format ID.
- **Instagram**: requires cookies for most content.
