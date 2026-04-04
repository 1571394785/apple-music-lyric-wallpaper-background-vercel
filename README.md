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
  "roma": "..."
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
