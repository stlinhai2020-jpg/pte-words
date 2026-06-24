import streamlit as st
import json
import os
import random
import base64
import re
from openai import OpenAI

# 页面基础配置
st.set_page_config(page_title="PTE极简生词本", layout="centered", initial_sidebar_state="collapsed")

# --- 1. 配置阿里通义千问模型 ---
API_KEY = st.secrets.get("DASHSCOPE_API_KEY", "") 
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL_NAME = "qwen-vl-max" 

def encode_image(image_bytes):
    return base64.b64encode(image_bytes).decode('utf-8')

def extract_json_from_text(text):
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        return match.group(0)
    return text

def call_ai_to_extract_from_image(base64_image):
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    prompt = """
    你是一个资深的PTE备考专家。请识别截图中的学术词汇，按牛津词典风格提供：音标、英文释义、中文释义、一句话经典例句。
    必须返回标准的 JSON 数据块，绝不包含 Markdown 标记或多余废话。
    """
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}],
            temperature=0.1
        )
        return json.loads(extract_json_from_text(response.choices[0].message.content))
    except Exception as e:
        st.error(f"AI 解析出错: {e}")
        return None

# --- 2. 云端数据库 (Supabase) 模块 ---
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

@st.cache_resource
def init_supabase():
    if SUPABASE_URL and SUPABASE_KEY:
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None

supabase = init_supabase()

# 加载数据
if "words" not in st.session_state:
    st.session_state.words = {}
    if supabase:
        try:
            response = supabase.table("words").select("*").execute()
            for row in response.data:
                st.session_state.words[row['word']] = row
        except: pass

def save_word(word_dict):
    st.session_state.words.update(word_dict)
    if supabase:
        supabase.table("words").upsert(list(word_dict.values())).execute()
    else:
        with open("words_db.json", "w", encoding="utf-8") as f: json.dump(st.session_state.words, f, ensure_ascii=False)

# --- 3. 页面交互 ---
st.title("⚡ PTE 智能生词本")
uploaded_file = st.file_uploader("粘贴截图或上传图片", type=["png", "jpg", "jpeg"])

if uploaded_file:
    if st.button("🚀 提取生词"):
        img_bytes = uploaded_file.read()
        res = call_ai_to_extract_from_image(encode_image(img_bytes))
        if res:
            for w, info in res.items():
                info['word'] = w
                save_word({w: info})
            st.success("导入成功！")
            st.rerun()

# 单词列表展示 (包含发音逻辑)
for w, info in st.session_state.words.items():
    col1, col2 = st.columns([4, 1])
    with col1:
        with st.expander(f"{w} | {info.get('def_zh', '')}"):
            st.write(f"**释义**: {info.get('def_en', '')}")
            st.write(f"**例句**: {info.get('example', '')}")
    with col2:
        # 使用网页原生发音 API
        btn_html = f'<button onclick="window.speechSynthesis.speak(new SpeechSynthesisUtterance(\'{w}\'))">🔊</button>'
        st.components.v1.html(btn_html)
