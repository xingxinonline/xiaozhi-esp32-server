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
from plugins_func.register import register_function,ToolType, ActionResponse, Action


TAG = __name__
logger = setup_logging()

play_music_function_desc = {
    "type": "function",
    "function": {
        "name": "MusicPlayer",
        "description": """歌曲查询Plugin，当用户需要搜索某个歌手或者歌曲时使用此plugin，给定歌手，歌名等特征返回相关音乐。\n 例子1：query=想听孙燕姿的遇见， 输出{"artist":"孙燕姿","song_name":"遇见","description":""}""",
        "parameters": {
            "properties": {
                "artist": {"description": "表示歌手名字", "type": "string"},
                "description": {
                    "description": "表示描述信息",
                    "type": "string",
                },
                "song_name": {
                    "description": "表示歌曲名字",
                    "type": "string",
                },
            },
            "required": [],
            "type": "object",
        },
    },
}

@register_function("MusicPlayer", play_music_function_desc, ToolType.WAIT)
def MusicPlayer(artist='', description='', song_name=''):
    result = "无法播放歌曲"
    response = "我没有办法直接帮您播放歌曲呢，您可以使用相关的音乐软件播放您喜欢的歌曲"
    return ActionResponse(Action.RESPONSE, result, response)
