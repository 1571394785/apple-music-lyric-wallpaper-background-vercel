# QQ音乐歌词API - Vercel部署版本

这是一个基于QQ音乐API的歌词获取服务，已适配Vercel部署。

## 部署到Vercel

1. 安装Vercel CLI（如果还没有安装）：
```bash
npm install -g vercel
```

2. 在项目目录中运行：
```bash
vercel
```

3. 按照提示完成部署

## API使用

## 歌词缓存（Vercel Blob）

服务已支持按歌曲 `mid` 做歌词缓存：

- 先读取 Blob 缓存
- 缓存未命中时再调用 QQ 音乐接口抓取
- 抓取成功后写回 Blob，供后续请求复用

### 必需环境变量

- `BLOB_READ_WRITE_TOKEN`: Vercel Blob 的读写 Token（在 Vercel 项目 Storage 中创建 Blob 后自动注入）

### 可选环境变量

- `BLOB_ACCESS`: Blob 访问模式，默认 `private`
- `LYRIC_CACHE_PREFIX`: 缓存路径前缀，默认 `lyrics`
- `LOG_LEVEL`: 日志级别，默认 `INFO`

如果未设置 `BLOB_READ_WRITE_TOKEN`，服务会自动降级为“仅实时抓取”，不影响接口可用性。

### Vercel 日志排查

服务会在 Vercel Logs 输出以下关键日志：

- `cache_read hit/miss/failed`
- `cache_write success/failed/give_up`
- `search selected/return_cache/return_remote`

如果一直是 `miss`，先看 `cache_write failed` 的 status 和 body，一般能直接定位为 token、access 或路径问题。

### 获取歌词

**接口**: `/api/lyric`

**方法**: `POST` 或 `GET`

**参数**:
- `key` (必需): 歌曲名称
- `artist` (可选): 歌手名称

**示例请求**:

```bash
# POST请求
curl -X POST https://your-domain.vercel.app/api/lyric \
  -H "Content-Type: application/json" \
  -d '{"key": "稻香", "artist": "周杰伦"}'

# GET请求
curl "https://your-domain.vercel.app/api/lyric?key=稻香&artist=周杰伦"
```

**响应示例**:
```json
{
  "lyric": "...",
  "trans": "...",
  "roma": "...",
  "mid": "0039MnYb0qxYhV",
  "cache": "hit"
}
```

## 本地开发

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 运行开发服务器：
```bash
vercel dev
```

## 项目结构

```
.
├── api/
│   └── index.py          # Vercel serverless function入口
├── qqmusic_api/          # QQ音乐API库
├── vercel.json           # Vercel配置
├── requirements.txt      # Python依赖
└── README.md            # 说明文档
```

## 注意事项

- 原IIS版本的`get_lyric.py`已被新的Flask应用替代
- API接口路径从根目录变更为`/api/lyric`
- 支持JSON和表单两种请求格式
