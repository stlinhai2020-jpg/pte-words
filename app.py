import streamlit as st
import json
import os
import random
import base64
from openai import OpenAI

# 页面基础配置（自适应移动端与PC端）
st.set_page_config(page_title="PTE极简生词本", layout="centered", initial_sidebar_state="collapsed")

# --- 1. 配置阿里通义千问视觉大模型 ---
# 提示：请去阿里云百炼平台申请 DASHSCOPE_API_KEY 并填入 Streamlit 的 Secrets 中
API_KEY = st.secrets.get("DASHSCOPE_API_KEY", "sk-ws-H.RPXDEER.ZfBh.MEUCIBgga-s1bmH7zVO5l1wX6DjUMgcSsCnfJAohmy0mpxT8AiEAtdVHUInYzuBaDW99BtGX0bnhnEKampjR1VgY4YS3Ofg") 
BASE_URL = "[https://dashscope.aliyuncs.com/compatible-mode/v1](https://dashscope.aliyuncs.com/compatible-mode/v1)"
MODEL_NAME = "qwen-vl-max"  # 阿里顶级视觉多模态大模型

def encode_image(image_bytes):
    """将图片字节流转换为 base64 编码，用于传给视觉大模型"""
    return base64.b64encode(image_bytes).decode('utf-8')

def call_ai_to_extract_from_image(base64_image):
    """调用千问视觉大模型：识别图片文本，智能过滤熟词，生成标准牛津释义 JSON"""
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
        
        # 兼容处理大模型可能附带的 Markdown 标记
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
            
        return json.loads(result_text.strip())
    except Exception as e:
        st.error(f"AI 图像识别出错啦: {e}")
        return None

# --- 2. 本地数据存储与 TTS 发音核心（JavaScript 注入） ---
DB_FILE = "words_db.json"
if "words" not in st.session_state:
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            st.session_state.words = json.load(f)
    else:
        st.session_state.words = {}

def save_to_local():
    """将生词本数据同步保存到本地 JSON"""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state.words, f, ensure_ascii=False, indent=4)

def js_speak(text, rate=1.0):
    """通过安全转义，安全调用浏览器原生 TTS 进行纯正发音"""
    # 使用 json.dumps 自动处理英文单词或句子中的双引号/单引号转义，避免 JS 语法中断
    text_json = json.dumps(text)
    js_code = f"""
    <script>
    (function() {{
        if ('speechSynthesis' in window) {{
            window.speechSynthesis.cancel(); // 停止当前正在播放的声音
            var msg = new SpeechSynthesisUtterance({text_json});
            msg.lang = 'en-US'; // 设为美音（PTE通用，流利度识别高）
            msg.rate = {rate};  // 控制播音速度
            window.speechSynthesis.speak(msg);
        }}
    }})();
    </script>
    """
    st.components.v1.html(js_code, height=0, width=0)

def js_loop_speak(words_list, rate=1.0, delay=3500):
    """注入 JavaScript 循环连续朗读整个生词本的单词"""
    words_json = json.dumps(words_list)
    js_code = f"""
    <script>
    (function() {{
        if ('speechSynthesis' in window) {{
            window.speechSynthesis.cancel();
            var words = {words_json};
            var index = 0;
            var rate = {rate};
            var delay = {delay};
            
            window.isLoopPlaying = true;
            
            function playNext() {{
                if (index < words.length && window.isLoopPlaying) {{
                    var msg = new SpeechSynthesisUtterance(words[index]);
                    msg.lang = 'en-US';
                    msg.rate = rate;
                    window.speechSynthesis.speak(msg);
                    index++;
                    setTimeout(playNext, delay);
                }} else {{
                    window.isLoopPlaying = false;
                }}
            }}
            playNext();
        }}
    }})();
    </script>
    """
    st.components.v1.html(js_code, height=0, width=0)

def js_stop_speak():
    """停止所有正在播放的连播语音"""
    js_code = """
    <script>
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
    }
    window.isLoopPlaying = false;
    </script>
    """
    st.components.v1.html(js_code, height=0, width=0)

# --- 3. 页面交互 UI 逻辑 ---
st.title("⚡ PTE 智能生词本")
st.caption("截图直接 Ctrl+V 粘贴 | 纯正美音纠音 | 列表循环朗读磨耳朵")

# 截图导入区
st.markdown("### 📸 猩际截图无脑导入")
uploaded_file = st.file_uploader(
    "💡 鼠标点一下这里，然后直接按 Ctrl+V 粘贴截图（或拖拽/选择文件）", 
    type=["png", "jpg", "jpeg"]
)

if uploaded_file is not None:
    img_bytes = uploaded_file.read()
    st.image(img_bytes, caption='已捕获的 PTE 截图', use_container_width=True)
    
    if st.button("🚀 开始无脑提取生词", type="primary"):
        if not API_KEY:
            st.error("请先在 Streamlit 后台配置您的 DASHSCOPE_API_KEY！")
        else:
            with st.spinner("视觉大模型正在努力提取生词、查询牛津释义中..."):
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

# 分栏标签页：生词本和复习模式
tab1, tab2 = st.tabs(["📚 生词本 (含发音功能)", "🎲 随机复习模式"])

with tab1:
    if not st.session_state.words:
        st.info("词本空空如也，快去上面粘贴截图吧！")
    else:
        sorted_words = sorted(st.session_state.words.keys())
        
        # --- 磨耳朵连播控制台 ---
        st.markdown("### 🎧 磨耳朵连播控制台")
        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1.5, 1, 1.5])
        with col_ctrl1:
            loop_rate = st.slider("朗读语速", min_value=0.6, max_value=1.5, value=1.0, step=0.1)
        with col_ctrl2:
            loop_interval = st.slider("单词间隔(秒)", min_value=2, max_value=6, value=3, step=1)
        
        with col_ctrl3:
            st.write("")  # 垂直对齐调整
            sub_col1, sub_col2 = st.columns(2)
            with sub_col1:
                if st.button("▶️ 连播", type="primary", key="btn_loop_play"):
                    js_loop_speak(sorted_words, rate=loop_rate, delay=loop_interval * 1000)
            with sub_col2:
                if st.button("⏹️ 停止", key="btn_loop_stop"):
                    js_stop_speak()
                    st.toast("已停止连播")
        
        st.divider()
        
        # --- 单词列表展示 ---
        for w in sorted_words:
            info = st.session_state.words[w]
            
            # 使用左右布局，左侧内容折叠，右侧独立发音
            col_word, col_btn = st.columns([5, 1])
            with col_word:
                expander_title = f"**{w}** |  {info.get('phonetic','')}  |  {info.get('def_zh','')}"
                with st.expander(expander_title):
                    st.markdown(f"**💡 Oxford Style:**\n*{info.get('def_en','')}*")
                    st.markdown(f"**📝 Example:**\n{info.get('example','')}")
                    if st.button(f"🗑️ 斩了", key=f"del_{w}"):
                        del st.session_state.words[w]
                        save_to_local()
                        st.rerun()
            with col_btn:
                if st.button("🔊", key=f"spk_{w}"):
                    js_speak(w, rate=1.0)

with tab2:
    if not st.session_state.words:
        st.info("词本空空如也，无法复习。")
    else:
        if "current_review_word" not in st.session_state or st.session_state.current_review_word not in st.session_state.words:
            st.session_state.current_review_word = random.choice(list(st.session_state.words.keys()))
            st.session_state.show_answer = False
            
        review_w = st.session_state.current_review_word
        review_info = st.session_state.words[review_w]
        
        st.markdown(f"## ❓ **{review_w}**")
        
        # 听音
        if st.button("🔊 听发音", key="review_spk"):
            js_speak(review_w, rate=1.0)
            
        if not st.session_state.show_answer:
            if st.button("👀 查看释义与例句", type="primary"):
                st.session_state.show_answer = True
                st.rerun()
        else:
            st.markdown(f"**发音：** {review_info.get('phonetic','')}")
            st.markdown(f"**中文：** {review_info.get('def_zh','')}")
            st.markdown(f"**英文解释：** {review_info.get('def_en','')}")
            st.markdown(f"**例句熟读：** *{review_info.get('example','')}*")
            
            # 听整句朗读，建立PTE语感
            if st.button("🔊 听例句朗读", key="review_ex_spk"):
                js_speak(review_info.get('example',''), rate=0.9)
                
            st.write("")
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
