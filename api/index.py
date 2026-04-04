from flask import Flask, request, jsonify
import sys
import os
import json
import logging
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
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("qqmusic_lyric_api")


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


def _blob_access_candidates() -> tuple[str, str]:
    """优先尝试配置 access，失败时尝试另一种 access。"""
    fallback = "public" if BLOB_ACCESS == "private" else "private"
    return BLOB_ACCESS, fallback


def _read_lyric_cache(mid: str) -> Optional[Dict[str, Any]]:
    """从Vercel Blob读取歌词缓存，未命中返回None。"""
    token = os.getenv(BLOB_TOKEN_ENV, "").strip()
    if not token:
        logger.info("cache_read skip: missing %s, mid=%s", BLOB_TOKEN_ENV, mid)
        return None

    store_id = _extract_store_id(token)
    if not store_id:
        logger.warning("cache_read skip: invalid blob token format, mid=%s", mid)
        return None

    pathname = _cache_path(mid)
    for access in _blob_access_candidates():
        blob_url = f"https://{store_id}.{access}.blob.vercel-storage.com/{pathname}"
        try:
            response = httpx.get(
                blob_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "x-vercel-blob-access": access,
                },
                timeout=HTTP_TIMEOUT,
            )
            if response.status_code == 404:
                logger.info(
                    "cache_read miss: mid=%s path=%s access=%s status=404",
                    mid,
                    pathname,
                    access,
                )
                continue
            if response.status_code != 200:
                logger.warning(
                    "cache_read failed: mid=%s path=%s access=%s status=%s body=%s",
                    mid,
                    pathname,
                    access,
                    response.status_code,
                    response.text[:200],
                )
                continue

            payload = response.json()
            if not isinstance(payload, dict):
                logger.warning(
                    "cache_read invalid_payload: mid=%s path=%s access=%s",
                    mid,
                    pathname,
                    access,
                )
                continue
            if payload.get("lyric", "") == "":
                logger.info(
                    "cache_read empty_lyric: mid=%s path=%s access=%s",
                    mid,
                    pathname,
                    access,
                )
                continue

            payload.setdefault("mid", mid)
            payload["cache"] = "hit"
            logger.info(
                "cache_read hit: mid=%s path=%s access=%s",
                mid,
                pathname,
                access,
            )
            return payload
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as err:
            logger.exception(
                "cache_read exception: mid=%s path=%s access=%s error=%s",
                mid,
                pathname,
                access,
                str(err),
            )
            continue

    return None


def _write_lyric_cache(mid: str, lyric_data: Dict[str, Any]) -> None:
    """把歌词写入Vercel Blob缓存。"""
    token = os.getenv(BLOB_TOKEN_ENV, "").strip()
    if not token:
        logger.info("cache_write skip: missing %s, mid=%s", BLOB_TOKEN_ENV, mid)
        return

    pathname = _cache_path(mid)
    try:
        body = json.dumps(lyric_data, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as err:
        logger.exception(
            "cache_write serialize_failed: mid=%s path=%s error=%s",
            mid,
            pathname,
            str(err),
        )
        return

    for access in _blob_access_candidates():
        headers = {
            "Authorization": f"Bearer {token}",
            "x-allow-overwrite": "true",
            "x-content-type": "application/json; charset=utf-8",
        }

        try:
            response = httpx.put(
                BLOB_API_URL,
                params={"pathname": pathname, "access": access},
                headers=headers,
                content=body,
                timeout=HTTP_TIMEOUT,
            )

            if response.status_code in (200, 201):
                logger.info(
                    "cache_write success: mid=%s path=%s access=%s status=%s",
                    mid,
                    pathname,
                    access,
                    response.status_code,
                )
                return

            logger.warning(
                "cache_write failed: mid=%s path=%s access=%s status=%s body=%s",
                mid,
                pathname,
                access,
                response.status_code,
                response.text[:300],
            )
        except httpx.HTTPError as err:
            logger.exception(
                "cache_write exception: mid=%s path=%s access=%s error=%s",
                mid,
                pathname,
                access,
                str(err),
            )

    logger.error("cache_write give_up: mid=%s path=%s", mid, pathname)


def _search_first_song(song_name: str) -> Optional[Dict[str, Any]]:
    """搜索歌曲，返回第一条结果。"""
    data = sync(search.search_by_type(song_name, search.SearchType.SONG, 1))
    if not data:
        return None
    return data[0]

def search_song(song_name: str):
    """搜索歌曲并获取歌词"""
    try:
        logger.info("search start: query=%s", song_name)
        song = _search_first_song(song_name)
        if not song:
            logger.info("search no_song: query=%s", song_name)
            return {"code": 404, "msg": "未找到歌曲"}

        mid = song.get("mid", "")
        if not mid:
            logger.warning("search missing_mid: query=%s", song_name)
            return {"code": 404, "msg": "歌曲缺少MID"}

        logger.info("search selected: query=%s mid=%s", song_name, mid)

        cached_lyric = _read_lyric_cache(mid)
        if cached_lyric is not None:
            logger.info("search return_cache: query=%s mid=%s", song_name, mid)
            return cached_lyric

        logger.info("search cache_miss_fetch_remote: query=%s mid=%s", song_name, mid)
        lyric_data = sync(lyric.get_lyric(mid=mid, qrc=True, trans=True, roma=True))

        if lyric_data.get("lyric", "") == "":
            logger.info("search no_lyric_remote: query=%s mid=%s", song_name, mid)
            return {"code": 404, "msg": "未找到歌词"}

        lyric_data["mid"] = mid
        lyric_data["cache"] = "miss"
        _write_lyric_cache(mid, lyric_data)

        logger.info("search return_remote: query=%s mid=%s", song_name, mid)

        return lyric_data
    except Exception as e:
        logger.exception("search exception: query=%s error=%s", song_name, str(e))
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
    logger.info("request /api/lyric: method=%s key=%s artist=%s", request.method, song_name, song_artist)
    
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
