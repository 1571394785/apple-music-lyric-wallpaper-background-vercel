from qqmusic_api import sync,search,lyric
import asyncio,json,os,requests,sys,io,cgi,sqlite3,time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
缓存数据库路径 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lyric_cache.db")
缓存失效秒数 = 15 * 24 * 60 * 60
def 获取get参数():
    query = os.environ["QUERY_STRING"]
    query = query.split("&")
    query = [i.split("=") for i in query]
    query = {i[0]:i[1] for i in query}
    # url解码
    query = {i:requests.utils.unquote(query[i]) for i in query}
    return query
def 获取post参数():
    form = cgi.FieldStorage()
    query = {i:form.getvalue(i) for i in form}
    return query
def 初始化缓存():
    with sqlite3.connect(缓存数据库路径) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lyric_cache (
                cache_key TEXT PRIMARY KEY,
                lyric_json TEXT NOT NULL,
                last_used_at INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS request_ip_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_key TEXT NOT NULL,
                ip TEXT NOT NULL,
                requested_at INTEGER NOT NULL
            )
        """)
        字段列表 = [row[1] for row in conn.execute("PRAGMA table_info(lyric_cache)").fetchall()]
        if "cache_key" not in 字段列表:
            conn.execute("DROP TABLE lyric_cache")
            conn.execute("""
                CREATE TABLE lyric_cache (
                    cache_key TEXT PRIMARY KEY,
                    lyric_json TEXT NOT NULL,
                    last_used_at INTEGER NOT NULL
                )
            """)
        最早可保留时间 = int(time.time()) - 缓存失效秒数
        conn.execute("DELETE FROM lyric_cache WHERE last_used_at < ?", (最早可保留时间,))
def 获取请求IP():
    x_forwarded_for = os.environ.get("HTTP_X_FORWARDED_FOR", "")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    x_real_ip = os.environ.get("HTTP_X_REAL_IP", "")
    if x_real_ip:
        return x_real_ip.strip()
    remote_addr = os.environ.get("REMOTE_ADDR", "")
    if remote_addr:
        return remote_addr.strip()
    return "unknown"
def 记录请求IP(request_key: str, ip: str):
    with sqlite3.connect(缓存数据库路径) as conn:
        conn.execute(
            "INSERT INTO request_ip_log (request_key, ip, requested_at) VALUES (?, ?, ?)",
            (request_key, ip, int(time.time())),
        )
def 从缓存读取歌词(cache_key: str):
    with sqlite3.connect(缓存数据库路径) as conn:
        row = conn.execute(
            "SELECT lyric_json FROM lyric_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE lyric_cache SET last_used_at = ? WHERE cache_key = ?",
            (int(time.time()), cache_key),
        )
        try:
            data = json.loads(row[0])
            data["cache_hit"] = True
            return data
        except json.JSONDecodeError:
            conn.execute("DELETE FROM lyric_cache WHERE cache_key = ?", (cache_key,))
            return None
def 写入歌词缓存(cache_key: str, data: dict):
    with sqlite3.connect(缓存数据库路径) as conn:
        conn.execute(
            """
            INSERT INTO lyric_cache (cache_key, lyric_json, last_used_at)
            VALUES (?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                lyric_json = excluded.lyric_json,
                last_used_at = excluded.last_used_at
            """,
            (cache_key, json.dumps(data, ensure_ascii=False), int(time.time())),
        )
def search_song(cache_key: str, song_name: str):
    cache_data = 从缓存读取歌词(cache_key)
    if cache_data is not None:
        return cache_data
    results = sync(search.search_by_type(song_name,search.SearchType.SONG,1))
    if not results:
        return {"code":404,"msg":"未找到歌曲"}
    mid = results[0].get("mid")
    if not mid:
        return {"code":404,"msg":"未找到歌曲"}
    data = sync(lyric.get_lyric(mid=mid,qrc=True,trans=True,roma=True))
    if data.get("lyric","") == "":
        return {"code":404,"msg":"未找到歌曲"}
    写入歌词缓存(cache_key, data)
    return data
print("Content-type:text/json;charset=utf-8")
print()
初始化缓存()
query = 获取post参数()
if "key" not in query:
    print(json.dumps({"code":404,"msg":"没有传入song_name参数"}))
    exit()
song_name = query["key"]
请求IP = 获取请求IP()
记录请求IP(song_name, 请求IP)
song_artist = query.get("artist","")
if song_artist:
    cache_key = song_name + "|" + song_artist
    data = search_song(cache_key, song_name + " " + song_artist)
    if data.get("code","200") == 404:
        cache_key = song_name
        data = search_song(cache_key, song_name)
else:
    cache_key = song_name
    data = search_song(cache_key, song_name)
print(json.dumps(data))
