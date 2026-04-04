from qqmusic_api import sync,search,lyric
import asyncio,json,os,requests,sys,io,cgi
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
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
def search_song(song_name:str):
    data =sync(search.search_by_type(song_name,search.SearchType.SONG,1))
    # print(data)
    try:
        mid=data[0]['mid']
        id=data[0]['id']
        title=data[0]['title']
        # print(id,title)
        data = sync(lyric.get_lyric(mid=mid,qrc=True,trans=True,roma=True))
        if data.get("lyric","") == "":
            raise Exception("未找到歌词")
    except:
        data = {"code":404,"msg":"未找到歌曲"}
    # print(data)
    return data
print("Content-type:text/json;charset=utf-8")
print()
query = 获取post参数()
if "key" not in query:
    print(json.dumps({"code":404,"msg":"没有传入song_name参数"}))
    exit()
song_name = query["key"]
song_artist = query.get("artist","")
data = search_song(song_name + " " + song_artist)
if data.get("code","200") == 404 and song_artist:
    data = search_song(song_name)
print(json.dumps(data))
