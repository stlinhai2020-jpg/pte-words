import streamlit as st
import json
import os
import random
import base64
from openai import OpenAI

# 页面基础配置
st.set_page_config(page_title="PTE极简生词本", layout="centered", initial_sidebar_state="collapsed")

# --- 1. 配置视觉大模型 ---
API_KEY = st.secrets.get("DASHSCOPE_API_KEY", "sk-ws-H.RPXDEER.ZfBh.MEUCIBgga-s1bmH7zVO5l1wX6DjUMgcSsCnfJAohmy0mpxT8AiEAtdVHUInYzuBaDW99BtGX0bnhnEKampjR1VgY4YS3Ofg") 
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL_NAME = "qwen-vl-max"

def encode_image(image_bytes):
    return base64.b64encode(image_bytes).decode('utf-8')

def call_ai_to_extract_from_image(base64_image):
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    prompt = """
    你是一个资深的PTE备考专家和高级英语词典编纂者。
    请仔细阅读这张PTE题目原文或AI评分的截图，识别出图片中的所有英文文本。
    接着，从这些文本中找出对于想考PTE四个65分（大约雅思6.5分）的学生来说，较难、较生僻或重要的学术词汇（过滤掉the, is, standard等过于简单的基础词）。
    
    对于挑选出来的每个生词，请严格按照牛津词典（Oxford Style）提供以下内容：
    1. 音标 (国际音标，如 /ˈæləkeɪt/)
    2. 纯英文释义 (精准、地道的英文解释)
    3. 中文释义 (简明扼要的中文翻译)
    4. 经典例句 (一句话，最好契合PTE或学术场景)
    
    必须且只能返回标准的 JSON 格式数据，不要包含任何 Markdown 标记。格式示例如下：
    {
        "word1": { "phonetic": "/.../", "def_en": "...", "def_zh": "...", "example": "..." }
    }
    """
    try:
        response = client.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}], temperature=0.1)
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("
http://googleusercontent.com/immersive_entry_chip/0
http://googleusercontent.com/immersive_entry_chip/1

---

### 🔥 升级后的两大核心高爽点：

1. **单个单词点喇叭 (🔊)**：
   在生词本列表中，每个单词右侧现在都有一个独立的 `🔊` 按钮。点击它，浏览器就会秒发出标准清爽的英文原声，用于平时的快速纠音和记忆反馈。
2. **磨耳朵连播控制台 (▶️ 连播 / ⏹️ 停止)**：
   在生词本的最上方，新增了一个控制区。点击 **▶️ 连播**，程序会按照字母顺序，自动一个接一个地大声朗读你词本里的所有核心词汇！
   * **语速可调**：如果你觉得标准语速太快，可以拉动滑块把语速调慢（比如 `0.8` 倍速），用来仔细揣摩发音细节；也可以调快（比如 `1.2` 倍速）模拟考场紧张感。
   * **间隔可调**：默认每隔 3 秒读下一个词，给你留出原地跟读（Shadowing）和脑内回忆中文释义的时间。

代码提交上去后，系统会自动更新部署。快去戴上耳机，截两张图传进去，体验一下这个为你量身定制的、带纯正发音的 PTE 智能磨耳朵神器吧！
