from flask import Flask, request, jsonify
import sys
import os
import json
from typing import Any, Dict, Optional

import httpx

# 添加父目录到路径以导入qqmusic_api
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qqmusic_api import sync, search, lyric

app = Flask(__name__)

BLOB_TOKEN_ENV = "BLOB_READ_WRITE_TOKEN"
BLOB_API_URL = "https://vercel.com/api/blob"
BLOB_ACCESS = os.getenv("BLOB_ACCESS", "private").strip().lower()
if BLOB_ACCESS not in ("private", "public"):
    BLOB_ACCESS = "private"
CACHE_PREFIX = os.getenv("LYRIC_CACHE_PREFIX", "lyrics").strip("/")
HTTP_TIMEOUT = 10.0


def _extract_store_id(token: str) -> str:
    """从Blob token中提取store id。"""
    parts = token.split("_", 4)
    if len(parts) < 4:
        return ""
    return parts[3]


def _cache_path(mid: str) -> str:
    """构建歌词缓存路径。"""
    if CACHE_PREFIX:
        return f"{CACHE_PREFIX}/{mid}.json"
    return f"{mid}.json"


def _read_lyric_cache(mid: str) -> Optional[Dict[str, Any]]:
    """从Vercel Blob读取歌词缓存，未命中返回None。"""
    token = os.getenv(BLOB_TOKEN_ENV, "").strip()
    if not token:
        return None

    store_id = _extract_store_id(token)
    if not store_id:
        return None

    pathname = _cache_path(mid)
    blob_url = f"https://{store_id}.{BLOB_ACCESS}.blob.vercel-storage.com/{pathname}"

    try:
        response = httpx.get(
            blob_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=HTTP_TIMEOUT,
        )
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            return None

        payload = response.json()
        if not isinstance(payload, dict):
            return None
        if payload.get("lyric", "") == "":
            return None

        payload.setdefault("mid", mid)
        payload["cache"] = "hit"
        return payload
    except (httpx.HTTPError, json.JSONDecodeError, ValueError):
        return None


def _write_lyric_cache(mid: str, lyric_data: Dict[str, Any]) -> None:
    """把歌词写入Vercel Blob缓存。"""
    token = os.getenv(BLOB_TOKEN_ENV, "").strip()
    if not token:
        return

    pathname = _cache_path(mid)
    body = json.dumps(lyric_data, ensure_ascii=False).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {token}",
        "x-vercel-blob-access": BLOB_ACCESS,
        "x-allow-overwrite": "true",
        "x-content-type": "application/json; charset=utf-8",
    }

    try:
        httpx.put(
            BLOB_API_URL,
            params={"pathname": pathname},
            headers=headers,
            content=body,
            timeout=HTTP_TIMEOUT,
        )
    except httpx.HTTPError:
        # 缓存失败不影响主流程
        return


def _search_first_song(song_name: str) -> Optional[Dict[str, Any]]:
    """搜索歌曲，返回第一条结果。"""
    data = sync(search.search_by_type(song_name, search.SearchType.SONG, 1))
    if not data:
        return None
    return data[0]

def search_song(song_name: str):
    """搜索歌曲并获取歌词"""
    try:
        song = _search_first_song(song_name)
        if not song:
            return {"code": 404, "msg": "未找到歌曲"}

        mid = song.get("mid", "")
        if not mid:
            return {"code": 404, "msg": "歌曲缺少MID"}

        cached_lyric = _read_lyric_cache(mid)
        if cached_lyric is not None:
            return cached_lyric

        lyric_data = sync(lyric.get_lyric(mid=mid, qrc=True, trans=True, roma=True))

        if lyric_data.get("lyric", "") == "":
            return {"code": 404, "msg": "未找到歌词"}

        lyric_data["mid"] = mid
        lyric_data["cache"] = "miss"
        _write_lyric_cache(mid, lyric_data)

        return lyric_data
    except Exception as e:
        return {"code": 404, "msg": f"未找到歌曲: {str(e)}"}

@app.route('/', methods=['GET'])
def home():
    """首页"""
    return jsonify({
        "status": "ok",
        "message": "QQ音乐歌词API（含Vercel Blob缓存）",
        "endpoints": {
            "/api/lyric": "POST - 获取歌词 (参数: key=歌曲名, artist=歌手名[可选])"
        }
    })

@app.route('/api/lyric', methods=['POST', 'GET'])
def get_lyric():
    """获取歌词接口"""
    # 支持POST和GET请求
    if request.method == 'POST':
        data = request.get_json() or request.form.to_dict()
    else:
        data = request.args.to_dict()
    
    # 获取参数
    song_name = data.get('key', '')
    song_artist = data.get('artist', '')
    
    if not song_name:
        return jsonify({"code": 404, "msg": "没有传入key参数（歌曲名）"})
    
    # 先尝试搜索 歌曲名+歌手名
    search_query = f"{song_name} {song_artist}".strip()
    result = search_song(search_query)
    
    # 如果失败且有歌手名，尝试只搜索歌曲名
    if result.get("code") == 404 and song_artist:
        result = search_song(song_name)
    
    return jsonify(result)

# Vercel需要的handler
def handler(request):
    with app.request_context(request.environ):
        return app.full_dispatch_request()
