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
from core.handle.sendAudioHandle import send_stt_message
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.utils.dialogue import Message

TAG = __name__

MUSIC_CACHE = {}

play_music_function_desc = {
        "type": "function",
        "function": {
            "name": "play_music",
            "description": "当你想播放歌曲时非常有用，当用户明确要求播放音乐时使用",
            "parameters": {
                "type": "object",
                "properties": {}  # 无需参数
            }
        }
    }


@register_function('play_music', play_music_function_desc, ToolType.SYSTEM_CTL)
def play_music(conn):
    try:
        conn.test_start = None
        # 检查事件循环状态
        if not conn.loop.is_running():
            logger.bind(tag=TAG).error("事件循环未运行，无法提交任务")
            return ActionResponse(action=Action.NONE, result="系统繁忙", response=None)

        # 提交异步任务
        future = asyncio.run_coroutine_threadsafe(
            play_local_music(conn),
            conn.loop
        )

        # 非阻塞回调处理
        def handle_done(f):
            try:
                f.result()  # 可在此处理成功逻辑
                conn.logger.bind(tag=TAG).info("播放完成")
            except Exception as e:
                conn.logger.bind(tag=TAG).error(f"播放失败: {e}")

        future.add_done_callback(handle_done)

        return ActionResponse(action=Action.NONE, result="指令已接收", response=None)
    except Exception as e:
        logger.bind(tag=TAG).error(f"处理音乐意图错误: {e}")
        return ActionResponse(action=Action.NONE, result=str(e), response=None)


async def play_local_music(conn):
    global MUSIC_CACHE
    """播放本地音乐文件"""
    try:
        # 1. 从音乐文件夹随机选择文件
        music_folder = "./music"  # 修改为实际音乐文件夹路径
        music_files = [f for f in os.listdir(music_folder) if f.endswith(".wav")]
        if not music_files:
            return "未找到可播放的音乐文件"
        # 2. 文件处理
        selected_music = random.choice(music_files)
        music_path = os.path.join(music_folder, selected_music)
        if music_path.endswith(".p3"):
            opus_packets, duration = p3.decode_opus_from_file(music_path)
        else:
            opus_packets, duration = conn.tts.audio_to_opus_data(music_path)
        conn.audio_play_queue.put((opus_packets, selected_music, 0))

    except Exception as e:
        logger.bind(tag=TAG).error(f"播放音乐失败: {str(e)}")
        logger.bind(tag=TAG).error(f"详细错误: {traceback.format_exc()}")

