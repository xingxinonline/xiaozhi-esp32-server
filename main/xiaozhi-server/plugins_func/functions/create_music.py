from config.logger import setup_logging
import os
import re
import time
import random
import asyncio
import difflib
import traceback
from pathlib import Path
from core.utils import p3
from core.handle.sendAudioHandle import send_stt_message, sendAudioMessage
from plugins_func.register import register_function,ToolType, ActionResponse, Action

import datetime
import hashlib
import hmac
import json
from urllib.parse import quote
import requests
import time


TAG = __name__
logger = setup_logging()

MUSIC_CACHE = {}

create_music_function_desc = {
        "type": "function",
        "function": {
            "name": "create_music",
            "description": "播放歌曲时随机生成，播放某首歌时生成类似提示词",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "minLength": 5,
                        "maxLength": 700,
                        "description": "文本提示词，，仅支持中文，5到700个字符，不能少于5个汉字，当未提供歌词时使用提示生成。"
                    },
                    "genre": {
                        "type": "string",
                        "enum": ["Folk", "Pop", "Rock", "Chinese Style", "Hip Hop/Rap", "R&B/Soul", "Punk", "Electronic", "Jazz", "Reggae", "DJ", "Pop Punk", "Disco", "Future Bass", "Pop Rap", "Trap Rap", "R&B Rap", "Chinoiserie Electronic", "GuFeng Music", "Pop Rock", "Jazz Pop", "Bossa Nova", "Contemporary R&B"],
                        "description": "曲风类型 - 选项说明：Folk(民谣), Pop(流行), Rock(摇滚), Chinese Style(国风), Hip Hop/Rap(嘻哈), R&B/Soul(R&B), Punk(朋克), Electronic(电子), Jazz(爵士), Reggae(雷鬼), DJ(DJ), Pop Punk(流行朋克), Disco(迪斯科舞曲), Future Bass(未来贝斯), Pop Rap(流行说唱), Trap Rap(陷阱说唱), R&B Rap(旋律说唱), Chinoiserie Electronic(国风电子), GuFeng Music(古风音乐), Pop Rock(流行摇滚), Jazz Pop(流行爵士), Bossa Nova(巴塞诺瓦), Contemporary R&B(当代节奏布鲁斯)"
                    },
                    "mood": {
                        "type": "string",
                        "enum": ["Happy", "Dynamic/Energetic", "Sentimental/Melancholic/Lonely", "Inspirational/Hopeful", "Nostalgic/Memory", "Excited", "Sorrow/Sad", "Chill", "Romantic", "Miss", "Groovy/Funky", "Dreamy/Ethereal", "Calm/Relaxing"],
                        "description": "情绪风格 - 选项说明：Happy(快乐), Dynamic/Energetic(活力), Sentimental/Melancholic/Lonely(EMO), Inspirational/Hopeful(鼓舞), Nostalgic/Memory(怀旧), Excited(兴奋), Sorrow/Sad(伤感), Chill(放松), Romantic(浪漫), Miss(思念), Groovy/Funky(律动), Dreamy/Ethereal(梦幻), Calm/Relaxing(平静)"
                    },
                    "gender": {
                        "type": "string",
                        "enum": ["Female", "Male"],
                        "description": "演唱者性别 - Female(女声), Male(男声)"
                    },
                    "timbre": {
                        "type": "string",
                        "enum": ["Warm", "Bright", "Husky", "Electrified voice", "Sweet_AUDIO_TIMBRE", "Cute_AUDIO_TIMBRE", "Loud and sonorous", "Powerful", "Sexy/Lazy"],
                        "description": "音色特征 - Warm(温暖), Bright(明亮), Husky(烟嗓), Electrified voice(电音), Sweet_AUDIO_TIMBRE(甜美), Cute_AUDIO_TIMBRE(可爱), Loud and sonorous(浑厚), Powerful(高亢), Sexy/Lazy(慵懒)"
                    },
                },
                "required": ["prompt", "genre", "mood", "gender", "timbre"],
            }
        }
}

async def play_local_music(conn, music_path=None):
    global MUSIC_CACHE
    ct = 3
    """播放本地音乐文件"""
    try:
        if not os.path.exists(music_path):
            logger.bind(tag=TAG).error(f"选定的音乐文件不存在: {music_path}")
            return
        text = f"正在播放创作完成的歌曲"
        await send_stt_message(conn, text)
        conn.tts_first_text_index = 0
        conn.tts_last_text_index = 0
        conn.llm_finish_task = True
        opus_datas, duration = conn.tts.audio_to_opus_data(music_path)
        
        # 3. 异步发送指令
        if not conn.client_abort:
            asyncio.run_coroutine_threadsafe(
                sendAudioMessage(conn, opus_datas, "歌曲播放中"), 
                conn.loop
            )
            return f"正在播放音乐：{music_path}"
        else:
            return "音乐播放失败"

    except Exception as e:
        logger.bind(tag=TAG).error(f"播放音乐失败: {str(e)}")
        logger.bind(tag=TAG).error(f"详细错误: {traceback.format_exc()}")


max_retries = 120
# 当使用临时凭证时，需要使用到SessionToken传入Header，并计算进SignedHeader中，请自行在header参数中添加X-Security-Token头
SessionToken = ""

# 以下参数视服务不同而不同，一个服务内通常是一致的
Service = "imagination"
Version = "2024-08-12"
Region = "cn-beijing"
Host = "open.volcengineapi.com"
ContentType = "application/json"

def norm_query(params):
    query = ""
    for key in sorted(params.keys()):
        if isinstance(params[key], list):
            for k in params[key]:
                query += f"{quote(key, safe='-_.~')}={quote(k, safe='-_.~')}&"
        else:
            query += f"{quote(key, safe='-_.~')}={quote(params[key], safe='-_.~')}&"
    return query.rstrip('&').replace("+", "%20")

# 第一步：准备辅助函数。
# sha256 非对称加密
def hmac_sha256(key: bytes, content: str):
    return hmac.new(key, content.encode("utf-8"), hashlib.sha256).digest()

# sha256 hash算法
def hash_sha256(content):
    if isinstance(content, dict):
        content = json.dumps(content)
    elif content is None:
        content = ""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

# 第二步：签名请求函数
def request(method, date, query, header, ak, sk, action, body):
    if body is None:
        body = ""
    elif isinstance(body, dict):
        body = json.dumps(body)

    # 第三步：创建身份证明。其中的 Service 和 Region 字段是固定的。ak 和 sk 分别代表
    # AccessKeyID 和 SecretAccessKey。同时需要初始化签名结构体。一些签名计算时需要的属性也在这里处理。
    # 初始化身份证明结构体
    credential = {
        "access_key_id": ak,
        "secret_access_key": sk,
        "service": Service,
        "region": Region,
    }
    # 初始化签名结构体
    request_param = {
        "body": body,
        "host": Host,
        "path": "/",
        "method": method,
        "content_type": ContentType,
        "date": date,
        "query": {"Action": action, "Version": Version, **query},
    }

    # 第四步：接下来开始计算签名。在计算签名前，先准备好用于接收签算结果的 signResult 变量，并设置一些参数。
    # 初始化签名结果的结构体
    x_date = request_param["date"].strftime("%Y%m%dT%H%M%SZ")
    short_x_date = x_date[:8]
    x_content_sha256 = hash_sha256(request_param["body"])

    # 第五步：计算 Signature 签名。
    sign_result = {
        "Host": request_param["host"],
        "X-Content-Sha256": x_content_sha256,
        "X-Date": x_date,
        "Content-Type": request_param["content_type"],
    }

    # signed_headers_str = signed_headers_str + ";x-security-token"
    signed_headers_str = ";".join(["content-type", "host", "x-content-sha256", "x-date"])
    canonical_request_str = "\n".join([
        request_param["method"].upper(),
        request_param["path"],
        norm_query(request_param["query"]),
        "\n".join([
            f"content-type:{request_param['content_type']}",
            f"host:{request_param['host']}",
            f"x-content-sha256:{x_content_sha256}",
            f"x-date:{x_date}",
        ]),
        "",
        signed_headers_str,
        x_content_sha256,
    ])
    # 打印正规化的请求用于调试比对
    # print(canonical_request_str)

    hashed_canonical_request = hash_sha256(canonical_request_str)
    # 打印hash值用于调试比对
    # print(hashed_canonical_request)

    credential_scope = "/".join([short_x_date, credential["region"], credential["service"], "request"])
    string_to_sign = "\n".join(["HMAC-SHA256", x_date, credential_scope, hashed_canonical_request])
    # 打印最终计算的签名字符串用于调试比对
    # print(string_to_sign)

    k_date = hmac_sha256(credential["secret_access_key"].encode("utf-8"), short_x_date)
    k_region = hmac_sha256(k_date, credential["region"])
    k_service = hmac_sha256(k_region, credential["service"])
    k_signing = hmac_sha256(k_service, "request")
    signature = hmac_sha256(k_signing, string_to_sign).hex()

    sign_result["Authorization"] = f"HMAC-SHA256 Credential={credential['access_key_id']}/{credential_scope}, SignedHeaders={signed_headers_str}, Signature={signature}"

    if SessionToken:
        sign_result["X-Security-Token"] = SessionToken

    header.update(sign_result)

    # header = {**header, **{"X-Security-Token": SessionToken}}
    # 第六步：将 Signature 签名写入 HTTP Header 中，并发送 HTTP 请求。
    r = requests.request(method=method,
                         url=f"https://{request_param['host']}{request_param['path']}",
                         headers=header,
                         params=request_param["query"],
                         data=request_param["body"])

    return r.json()

# 新增处理函数（添加在文件顶部）
def save_audio(audio_url, filename="song_audio.wav"):
    """保存音频文件"""
    try:
        response = requests.get(audio_url, stream=True, timeout=30)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"音频文件已保存至：{filename}")
    except Exception as e:
        print(f"音频下载失败：{str(e)}")


class ProgressState:
    """用于在不同任务间共享进度状态的类"""
    def __init__(self):
        self.progress = None
        self.completed = False
        self.lock = asyncio.Lock()

async def progress_monitor(state, conn):
    """独立的进度监控协程，在循环外运行"""
    last_reported_progress = None
    
    while not state.completed:
        async with state.lock:
            current_progress = state.progress
        
        # 只在进度变化时播报
        if current_progress is not None and current_progress != last_reported_progress:
            last_reported_progress = current_progress
            if current_progress > 0:
                progress_text = f"当前进度: {current_progress}%"

                await send_stt_message(conn, progress_text)
                conn.tts_first_text_index = 0
                conn.tts_last_text_index = 0
                conn.llm_finish_task = True
                future = conn.executor.submit(conn.speak_and_play, progress_text)
                conn.tts_queue.put(future)
            
        await asyncio.sleep(1)  # 定期检查进度变化

async def handle_music_command(conn, prompt, genre, mood, gender, timbre):
    now = datetime.datetime.utcnow()

    body = {
        "Prompt": prompt,
        "Genre":  genre,
        "Mood":   mood,
        "Gender": gender,
        "Timbre": timbre
    }
    AK = conn.config["plugins"]["create_music"]["AK"]
    SK = conn.config["plugins"]["create_music"]["SK"]
    response_body = request("POST", now, {}, {}, AK, SK, "GenSongV4", body)
    # print(response_body)
    # 提取TaskID
    task_id = response_body.get('Result', {}).get('TaskID')
    if not task_id:
        print("Failed to get TaskID")
        exit()
    # 查询任务状态
    now_query = datetime.datetime.utcnow()
    body_query = {"TaskID": task_id}
    response_query = request("POST", now_query, {}, {}, AK, SK, "QuerySong", body_query)
    # print("QuerySong Response:", response_query)
    retry_count = 0
    success = False
    
    # 创建共享状态对象
    progress_state = ProgressState()
    
    # 在循环外启动监控任务
    monitor_task = asyncio.create_task(progress_monitor(progress_state, conn))
    
    try: 
        while retry_count < max_retries:
            # 查询任务状态
            querysong_body = {"TaskID": task_id}
            querysong_response = await asyncio.to_thread(
                request, "POST", datetime.datetime.utcnow(), {}, {}, AK, SK, "QuerySong", querysong_body
            )
            
            # 检查API请求是否成功
            if querysong_response.get('Code') != 0:
                print(f"QuerySong failed: {querysong_response.get('Message')}")
                break
            
            result = querysong_response.get('Result', {})
            progress = result.get('Progress', 0)
            failure_reason = result.get('FailureReason')    

            # 任务成功完成
            if progress == 100:
                song_detail = result.get('SongDetail')
                if song_detail:
                    # print("\n歌曲生成成功！详情如下：")
                    # print(json.dumps(song_detail, indent=2, ensure_ascii=False))
                    # 保存音频文件
                    if audio_url := song_detail.get('AudioUrl'):
                        dirname = os.path.dirname(Path(__file__).resolve())
                        filepath = os.path.join(os.path.join('/'.join(dirname.split('/')[:-2]), 'tmp'), f"song_{task_id}.wav")
                        # print(Path(__file__).resolve())
                        save_audio(audio_url, filename=filepath)
                        await play_local_music(conn, music_path=filepath)
                    return True
                else:
                    print("任务完成但未返回歌曲详情。")
                    break
            
            # 任务失败
            if failure_reason:
                print(f"\n任务失败，原因：{failure_reason}")
                break
            
            # 更新进度状态
            async with progress_state.lock:
                progress_state.progress = progress
            
            # 任务进行中，等待后继续
            print(f"当前进度：{progress}%")
            await asyncio.sleep(5)
            retry_count += 1
    except Exception as e:
        print(e)
    finally:
        # 标记任务结束，停止监控
        async with progress_state.lock:
            progress_state.completed = True
        # 等待监控任务完成
        await monitor_task
        # 删除文件
        if os.path.exists(filepath):
            os.remove(filepath)
    
    if not success and retry_count >= max_retries:
        print("\n任务超时，未在10分钟内完成。")
        
@register_function('create_music', create_music_function_desc, ToolType.SYSTEM_CTL)
def create_music(
    conn, prompt, 
    genre='Pop', 
    mood='Happy', 
    gender='Male', 
    timbre='Warm'):
    try:

        # 检查事件循环状态
        if not conn.loop.is_running():
            logger.bind(tag=TAG).error("事件循环未运行，无法提交任务")
            return ActionResponse(action=Action.RESPONSE, result="系统繁忙", response="请稍后再试")

        # 提交异步任务
        future = asyncio.run_coroutine_threadsafe(
            handle_music_command(conn, prompt, genre, mood, gender, timbre),
            conn.loop
        )

        # 非阻塞回调处理
        def handle_done(f):
            try:
                f.result()  # 可在此处理成功逻辑
                logger.bind(tag=TAG).info("播放完成")
            except Exception as e:
                logger.bind(tag=TAG).error(f"播放失败: {e}")

        future.add_done_callback(handle_done)

        return ActionResponse(action=Action.RESPONSE, result="指令已接收", response="正在为您创作歌曲")
    except Exception as e:
        logger.bind(tag=TAG).error(f"处理音乐意图错误: {e}")
        return ActionResponse(action=Action.RESPONSE, result=str(e), response="播放音乐时出错了")

