from flask import Flask, request, jsonify
import sys
import os

# 添加父目录到路径以导入qqmusic_api
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qqmusic_api import sync, search, lyric

app = Flask(__name__)

def search_song(song_name: str):
    """搜索歌曲并获取歌词"""
    try:
        data = sync(search.search_by_type(song_name, search.SearchType.SONG, 1))
        
        if not data or len(data) == 0:
            return {"code": 404, "msg": "未找到歌曲"}
        
        mid = data[0]['mid']
        id = data[0]['id']
        title = data[0]['title']
        
        lyric_data = sync(lyric.get_lyric(mid=mid, qrc=True, trans=True, roma=True))
        
        if lyric_data.get("lyric", "") == "":
            return {"code": 404, "msg": "未找到歌词"}
        
        return lyric_data
    except Exception as e:
        return {"code": 404, "msg": f"未找到歌曲: {str(e)}"}

@app.route('/', methods=['GET'])
def home():
    """首页"""
    return jsonify({
        "status": "ok",
        "message": "QQ音乐歌词API",
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
