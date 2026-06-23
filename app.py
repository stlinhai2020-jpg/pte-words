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
    """将图片字节流转换为 base64 编码"""
    return base64.b64encode(image_bytes).decode('utf-8')

def call_ai_to_extract_from_image(base64_image):
    """调用通义千问视觉接口：看图、识字、过滤熟词、返回牛津格式 JSON"""
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    
    prompt = """
    你是一个资深的PTE备考专家和高级英语词典编纂者。
    请仔细阅读这张PTE题目原文或AI评分的截图，识别出图片中的所有英文文本。
    接着，从这些文本中找出对于想考PTE四个65分（大约雅思6.5分）的学生来说，较难、较生僻或重要的学术词汇（过滤掉the, is, standard, read, score等过于简单的基础词和系统操作词）。
    
    对于挑选出来的每个生词，请严格按照牛津词典（Oxford Style）提供以下内容：
    1. 音标 (国际音标，如 /ˈæləkeɪt/)
    2. 纯英文释义 (精准、地道的英文解释)
    3. 中文释义 (简明扼要的中文翻译)
    4. 经典例句 (一句话，最好契合PTE或学术场景)
    
    必须且只能返回标准的 JSON 格式数据，不要包含任何 Markdown 标记（如 ```json），不要包含任何解释性文字。格式示例如下：
    {
        "word1": {
            "phonetic": "/.../",
            "def_en": "...",
            "def_zh": "...",
            "example": "..."
        }
    }
    """
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.1
        )
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        return json.loads(result_text.strip())
    except Exception as e:
        st.error(f"AI 图像识别出错啦: {e}")
        return None

# --- 2. 本地数据存储逻辑 ---
DB_FILE = "words_db.json"
if "words" not in st.session_state:
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            st.session_state.words = json.load(f)
    else:
        st.session_state.words = {}

def save_to_local():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state.words, f, ensure_ascii=False, indent=4)

# --- 3. 界面交互 ---
st.title("⚡ PTE 极简生词本")
st.caption("免登录 | 本地存储 | 截图无脑粘贴版")

st.markdown("### 📸 猩际截图无脑导入")

# 利用 Streamlit 的 paste 兼容性：拖拽、点击、或者直接聚焦到这里按 Ctrl+V 粘贴均可触发
uploaded_file = st.file_uploader(
    "💡 鼠标点一下这里，然后直接按 Ctrl+V 粘贴截图（或拖拽/选择文件）", 
    type=["png", "jpg", "jpeg"]
)

if uploaded_file is not None:
    # 读取图片字节流
    img_bytes = uploaded_file.read()
    st.image(img_bytes, caption='已捕获的 PTE 截图', use_container_width=True)
    
    if st.button("🚀 开始无脑提取生词", type="primary"):
        if not API_KEY:
            st.error("请先在 Streamlit 后台配置您的 DASHSCOPE_API_KEY！")
        else:
            with st.spinner("千问大模型正在努力阅读图片、过滤熟词并查询牛津释义..."):
                base64_img = encode_image(img_bytes)
                ai_result = call_ai_to_extract_from_image(base64_img)
                if ai_result:
                    new_count = 0
                    for w, info in ai_result.items():
                        word_lower = w.strip().lower()
                        if word_lower not in st.session_state.words:
                            st.session_state.words[word_lower] = info
                            new_count += 1
                    save_to_local()
                    st.success(f"🎉 成功识别截图，并自动导入 {new_count} 个重要 PTE 生词！")
                    st.rerun()

st.divider()

# 词本与复习模块（保持原样）
tab1, tab2 = st.tabs(["📚 生词本 (字母排序)", "🎲 随机复习模式"])

with tab1:
    if not st.session_state.words:
        st.info("词本空空如也，快去上面粘贴截图吧！")
    else:
        sorted_words = sorted(st.session_state.words.keys())
        for w in sorted_words:
            info = st.session_state.words[w]
            with st.expander(f"**{w}** |  {info.get('phonetic','')}  |  {info.get('def_zh','')}"):
                st.markdown(f"**💡 Oxford Style:**\n*{info.get('def_en','')}*")
                st.markdown(f"**📝 Example:**\n{info.get('example','')}")
                if st.button(f"🗑️ 斩了", key=f"del_{w}"):
                    del st.session_state.words[w]
                    save_to_local()
                    st.rerun()

with tab2:
    if not st.session_state.words:
        st.info("词本里还没有单词，无法开启复习。")
    else:
        if "current_review_word" not in st.session_state or st.session_state.current_review_word not in st.session_state.words:
            st.session_state.current_review_word = random.choice(list(st.session_state.words.keys()))
            st.session_state.show_answer = False
            
        review_w = st.session_state.current_review_word
        review_info = st.session_state.words[review_w]
        
        st.markdown(f"## ❓ **{review_w}**")
        st.caption("看着这个单词，尝试读出声，并回忆它的含义和牛津释义...")
        
        if not st.session_state.show_answer:
            if st.button("👀 查看释义与例句", type="primary"):
                st.session_state.show_answer = True
                st.rerun()
        else:
            st.markdown(f"**发音：** {review_info.get('phonetic','')}")
            st.markdown(f"**中文：** {review_info.get('def_zh','')}")
            st.markdown(f"**英文解释：** {review_info.get('def_en','')}")
            st.markdown(f"**例句熟读：** *{review_info.get('example','')}*")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ 记住了，下一个"):
                    st.session_state.current_review_word = random.choice(list(st.session_state.words.keys()))
                    st.session_state.show_answer = False
                    st.rerun()
            with col2:
                if st.button("❌ 没记住，再抽一次"):
                    st.session_state.current_review_word = random.choice(list(st.session_state.words.keys()))
                    st.session_state.show_answer = False
                    st.rerun()
