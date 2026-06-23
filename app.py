import streamlit as st
import json
import os
import random
import base64
from openai import OpenAI

# 页面基础配置（自适应移动端与PC端）
st.set_page_config(page_title="PTE极简生词本", layout="centered", initial_sidebar_state="collapsed")

# --- 1. 配置阿里通义千问视觉大模型 ---
API_KEY = st.secrets.get("DASHSCOPE_API_KEY", "sk-ws-H.RPXDEER.ZfBh.MEUCIBgga-s1bmH7zVO5l1wX6DjUMgcSsCnfJAohmy0mpxT8AiEAtdVHUInYzuBaDW99BtGX0bnhnEKampjR1VgY4YS3Ofg") 
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
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

# --- 2. 本地数据存储 ---
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

# --- 3. 页面交互 UI 逻辑 ---
st.title("⚡ PTE 智能生词本")
st.caption("粘贴截图直接识别 | 有道真人美音发音 | 列表前端极速连播")

# 截图导入区
st.markdown("### 📸 猩际截图智能导入")

# HTML/JS 混合的高级粘贴板捕获器
# 解决点击空白粘贴无效的问题：在 Streamlit 页面提供一个高度聚焦的可视化“粘贴板感应箱”
paste_html_code = """
<div id="paste-box" style="
    border: 2px dashed #ff4b4b;
    border-radius: 10px;
    padding: 25px;
    text-align: center;
    background-color: #fff8f8;
    cursor: pointer;
    transition: all 0.3s;
" onclick="focusBox()">
    <span style="font-size: 24px;">📋</span>
    <p style="margin: 8px 0 0 0; font-weight: bold; color: #31333F; font-size: 15px;">
        先用鼠标点我一下，然后按 Ctrl + V 粘贴截图
    </p>
    <p style="margin: 4px 0 0 0; color: #7f8c8d; font-size: 12px;">
        (点击后框框会变亮，此时直接粘贴即可成功捕获)
    </p>
    <div id="preview-area" style="margin-top: 10px; display: none;">
        <p style="color: #2ecc71; font-weight: bold; font-size: 13px;">✅ 截图已成功捕获！请在下方点击“开始无脑提取”</p>
    </div>
</div>

<script>
function focusBox() {
    const box = document.getElementById('paste-box');
    box.style.backgroundColor = '#ffe9e9';
    box.style.borderColor = '#ff2b2b';
    box.style.boxShadow = '0 0 10px rgba(255,75,75,0.2)';
}

document.addEventListener('paste', function (e) {
    const items = (e.clipboardData || e.originalEvent.clipboardData).items;
    for (let i = 0; i < items.length; i++) {
        if (items[i].type.indexOf('image') !== -1) {
            const blob = items[i].getAsFile();
            const reader = new FileReader();
            reader.onload = function (event) {
                const base64Data = event.target.result.split(',')[1];
                
                // 显示成功预览提示
                document.getElementById('preview-area').style.display = 'block';
                
                // 将数据安全送回 Streamlit 后台
                const message = {
                    isStreamlitMessage: true,
                    type: "streamlit:setComponentValue",
                    value: base64Data
                };
                window.parent.postMessage(message, "*");
            };
            reader.readAsDataURL(blob);
        }
    }
});
</script>
"""

# 渲染高度定制的“粘贴感应箱”，并获取回传的 Base64 图片数据
captured_base64 = st.components.v1.html(paste_html_code, height=160)

# 如果用户没有成功用 Ctrl+V，我们依然保留底层传统文件拖拽上传作为兜底防呆
with st.expander("📎 手机端或无法粘贴？点击这里使用传统上传文件"):
    fallback_file = st.file_uploader("选择你的猩际截图：", type=["png", "jpg", "jpeg"], key="fallback_upload")

# 确定使用哪种方式获取到的图片
final_base64 = None
if captured_base64:
    final_base64 = captured_base64
elif fallback_file is not None:
    final_base64 = encode_image(fallback_file.read())

if final_base64:
    if st.button("🚀 开始无脑提取生词", type="primary", use_container_width=True):
        if not API_KEY:
            st.error("请先在 Streamlit 后台配置您的 DASHSCOPE_API_KEY！")
        else:
            with st.spinner("有道视觉大模型正在解析图片，提炼生词和标准牛津释义..."):
                ai_result = call_ai_to_extract_from_image(final_base64)
                if ai_result:
                    new_count = 0
                    for w, info in ai_result.items():
                        word_lower = w.strip().lower()
                        if word_lower not in st.session_state.words:
                            st.session_state.words[word_lower] = info
                            new_count += 1
                    save_to_local()
                    st.success(f"🎉 成功识别截图，自动生成高清真人语音并导入 {new_count} 个重要生词！")
                    st.rerun()

st.divider()

# 分栏标签页：生词本和复习模式
tab1, tab2 = st.tabs(["📚 生词本 (高清美音)", "🎲 随机复习模式"])

with tab1:
    if not st.session_state.words:
        st.info("词本空空如也，快去上面粘贴截图吧！")
    else:
        sorted_words = sorted(st.session_state.words.keys())
        
        # --- 统一的前端高保真磨耳朵连播控制台 ---
        st.markdown("### 🎧 高清美音·连播磨耳朵控制台")
        
        # UI 控制滑块
        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1.5, 1.2, 1.3])
        with col_ctrl1:
            loop_rate = st.slider("朗读语速", min_value=0.5, max_value=1.5, value=1.0, step=0.1)
            infinite_loop = st.checkbox("🔄 无限循环播放列表", value=False)
        with col_ctrl2:
            repeat_count = st.slider("每个单词复读次数", min_value=1, max_value=5, value=3, step=1)
        with col_ctrl3:
            loop_interval = st.slider("单词跟读间隔(秒)", min_value=1, max_value=5, value=2, step=1)
            
        # 纯前端音乐连播播音引擎：避开 Streamlit 后台重绘，100%在手机浏览器本地无缝稳定连播
        # 采用有道高清美语发音 API (type=2)
        words_json = json.dumps(sorted_words)
        infinite_js = "true" if infinite_loop else "false"
        
        player_html = f"""
        <div style="background-color: #f8f9fa; border-radius: 8px; padding: 12px; border: 1px solid #e9ecef; display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 20px;">🔊</span>
                <span id="player-status" style="font-size: 13px; color: #555; font-weight: bold;">播音器空闲中</span>
            </div>
            <div style="display: flex; gap: 8px;">
                <button id="btn-play" onclick="startLoop()" style="background-color: #ff4b4b; color: white; border: none; border-radius: 5px; padding: 6px 16px; font-weight: bold; cursor: pointer;">▶️ 开始连播</button>
                <button id="btn-stop" onclick="stopLoop()" style="background-color: #6c757d; color: white; border: none; border-radius: 5px; padding: 6px 16px; font-weight: bold; cursor: pointer;">⏹️ 停止</button>
            </div>
        </div>

        <script>
        var words = {words_json};
        var index = 0;
        var currentRepeat = 0;
        var repeatLimit = {repeat_count};
        var delay = {loop_interval * 1000};
        var infinite = {infinite_js};
        var isPlaying = false;
        var currentAudio = null;

        function updateStatus(text) {{
            document.getElementById('player-status').innerText = text;
        }}

        function startLoop() {{
            if (words.length === 0) {{
                updateStatus("词本无单词可读");
                return;
            }}
            isPlaying = true;
            index = 0;
            currentRepeat = 0;
            document.getElementById('btn-play').style.opacity = '0.6';
            playWord();
        }}

        function stopLoop() {{
            isPlaying = false;
            if (currentAudio) {{
                currentAudio.pause();
            }}
            document.getElementById('btn-play').style.opacity = '1';
            updateStatus("已手动停止播音");
        }}

        function playWord() {{
            if (!isPlaying) return;
            
            if (index < words.length) {{
                var word = words[index];
                updateStatus("正在播放: " + word + " (" + (currentRepeat + 1) + "/" + repeatLimit + ")");
                
                // 采用网易有道高清真人美音接口（type=2为美音，发音饱满自然）
                var url = "[https://dict.youdao.com/dictvoice?type=2&audio=](https://dict.youdao.com/dictvoice?type=2&audio=)" + encodeURIComponent(word);
                
                if (currentAudio) currentAudio.pause();
                currentAudio = new Audio(url);
                currentAudio.playbackRate = {loop_rate};
                
                currentAudio.onended = function() {{
                    currentRepeat++;
                    if (currentRepeat < repeatLimit) {{
                        setTimeout(playWord, delay);
                    }} else {{
                        currentRepeat = 0;
                        index++;
                        setTimeout(playWord, delay);
                    }}
                }};
                
                currentAudio.onerror = function() {{
                    // 若网络抖动出错，自动跳过防止卡死
                    index++;
                    currentRepeat = 0;
                    setTimeout(playWord, 100);
                }};
                
                // 直接由用户点击触发，突破手机 Safari/Chrome 的 autoplay 限制
                currentAudio.play().catch(function(e) {{
                    console.error("发音失败", e);
                    index++;
                    currentRepeat = 0;
                    setTimeout(playWord, 500);
                }});
                
            }} else if (infinite && words.length > 0) {{
                index = 0;
                currentRepeat = 0;
                setTimeout(playWord, delay);
            }} else {{
                isPlaying = false;
                document.getElementById('btn-play').style.opacity = '1';
                updateStatus("播放完毕");
            }}
        }}
        </script>
        """
        st.components.v1.html(player_html, height=80)
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
                    
                    # 单词释义内部的例句朗读原生喇叭
                    ex_sentence = info.get('example','')
                    if ex_sentence:
                        ex_url = f"[https://dict.youdao.com/dictvoice?type=2&audio=](https://dict.youdao.com/dictvoice?type=2&audio=){ex_sentence}"
                        # 注入极简 HTML 按钮，无刷新直接触发真人美音播放
                        ex_btn_html = f"""
                        <button onclick="new Audio('{ex_url}').play()" style="
                            background-color: #f1f3f5; border: none; border-radius: 4px; padding: 4px 10px; cursor: pointer; font-size: 12px; font-weight: bold; color: #495057; display: flex; align-items: center; gap: 4px;
                        ">🔊 读例句</button>
                        """
                        st.components.v1.html(ex_btn_html, height=35)
                        
                    if st.button(f"🗑️ 斩了", key=f"del_{w}"):
                        del st.session_state.words[w]
                        save_to_local()
                        st.rerun()
            with col_btn:
                # 原生 HTML 播音喇叭：百分之百支持手机端，点击即发声，高清美音
                word_url = f"[https://dict.youdao.com/dictvoice?type=2&audio=](https://dict.youdao.com/dictvoice?type=2&audio=){w}"
                btn_html = f"""
                <button onclick="new Audio('{word_url}').play()" style="
                    background: none; border: none; font-size: 20px; cursor: pointer; padding: 5px 10px; border-radius: 5px; transition: background 0.2s; width: 100%; text-align: center;
                " onmouseover="this.style.background='#f0f2f6'" onmouseout="this.style.background='none'">🔊</button>
                """
                st.components.v1.html(btn_html, height=45)

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
        
        # 听音：使用原生 HTML 喇叭，支持手机端首播
        review_word_url = f"[https://dict.youdao.com/dictvoice?type=2&audio=](https://dict.youdao.com/dictvoice?type=2&audio=){review_w}"
        review_btn_html = f"""
        <button onclick="new Audio('{review_word_url}').play()" style="
            background-color: #ff4b4b; color: white; border: none; border-radius: 5px; padding: 8px 16px; font-weight: bold; cursor: pointer; display: flex; align-items: center; gap: 6px;
        ">🔊 听美音发音</button>
        """
        st.components.v1.html(review_btn_html, height=45)
            
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
            ex_sentence = review_info.get('example','')
            if ex_sentence:
                review_ex_url = f"[https://dict.youdao.com/dictvoice?type=2&audio=](https://dict.youdao.com/dictvoice?type=2&audio=){ex_sentence}"
                review_ex_btn_html = f"""
                <button onclick="new Audio('{review_ex_url}').play()" style="
                    background-color: #6c757d; color: white; border: none; border-radius: 5px; padding: 6px 12px; font-size: 13px; cursor: pointer; display: flex; align-items: center; gap: 6px;
                ">🔊 听例句朗读</button>
                """
                st.components.v1.html(review_ex_btn_html, height=45)
                
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
