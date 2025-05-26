from ..base import MemoryProviderBase, logger
import time
import json
import os
import yaml
from config.config_loader import get_project_dir

def get_date():
    return time.strftime("%Y-%m-%d", time.localtime())

TAG = __name__

class MemoryProvider(MemoryProviderBase):
    def __init__(self, config):
        super().__init__(config)
        self.momery = ""

    def init_memory(self, role_id, llm):
        super().init_memory(role_id, llm)
        self.memory_path = get_project_dir() + f"data/{role_id}/{get_date()}"
        self.memory_file = os.path.join(self.memory_path, "mem.txt")
        self.memory_token_file = os.path.join(self.memory_path, "token.txt")

    # def load_memory(self):
    #     all_memory = {}
    #     if os.path.exists(self.memory_path):
    #         with open(self.memory_path, "r", encoding="utf-8") as f:
    #             all_memory = yaml.safe_load(f) or {}
    #     if self.role_id in all_memory:
    #         self.short_momery = all_memory[self.role_id]

    def save_memory_to_file(self, file_path, msgs):
        if not os.path.exists(self.memory_path):
            os.makedirs(self.memory_path)
        with open(file_path, "a") as f:
            f.write(msgs)
            f.write('\n')

    async def save_memory(self, role_id, msgs):
        if self.llm is None:
            logger.bind(tag=TAG).error("LLM is not set for memory provider")
            return None

        if len(msgs) < 2:
            return None

        # 当前时间
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        # message
        msg_str = ""
        msg_str += f"时间：{time_str}\n"
        # token_usage
        token_str = ""
        token_str += f"时间：{time_str}\n"
        tmp_total = [0] * 4
        round_num = 1
        info_list = ["prompt", "completion", "total", "reasoning"]
        for msg in msgs:
            content = msg.content
            if not content: continue
            content = content.replace('\n', '')
            if msg.role == "user":
                msg_str += f"User: {content}\n"
            elif msg.role == "assistant":
                msg_str += f"Assistant: {content}\n"
                if msg.token_usage:
                    token_usage = msg.token_usage
                    tmp_info_list= []
                    for idx, info in enumerate(info_list):
                        tmp_ct = eval(f"token_usage['{info}']")
                        tmp_info_list.append(f"{info}:{tmp_ct}")
                        tmp_total[idx] += tmp_ct
                    tmp_token_str = '\t'.join(tmp_info_list)
                    token_str += f"Round{round_num}|\t{tmp_token_str}\t{content}\n"
                round_num += 1
        last_str = '\t'.join([f"{info}:{total}" for info, total in zip(info_list, tmp_total)])
        token_str += f"Total|\t{last_str}\tend\n"
        
        memory_path = get_project_dir() + f"data/{role_id}/{get_date()}"
        memory_file = os.path.join(self.memory_path, "mem.txt")
        memory_token_file = os.path.join(self.memory_path, "token.txt")
             
        self.save_memory_to_file(memory_file, msg_str)
        self.save_memory_to_file(memory_token_file, token_str)


        logger.bind(tag=TAG).info(f"Save memory successful - Role: {self.role_id}")

    async def query_memory(self, query: str) -> str:
        logger.bind(tag=TAG).debug("mem_local mode: No memory query is performed.")
        return ""
