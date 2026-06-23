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
st.caption("Ctrl+V 直接粘贴识别 | 有道高清美音 | 移动端连播优化")

# 截图导入区
st.markdown("### 📸 猩际/猩际截图智能导入")

# 终极修复方案 1：全新的双向粘贴板组件（直接绕过 Streamlit 后台刷新）
# 它既是一个可视化的键盘事件焦点盒，又能完美将数据在前端缓存。
paste_and_upload_html = """
<div id="paste-zone" style="
    border: 2px dashed #ff4b4b;
    border-radius: 10px;
    padding: 30px;
    text-align: center;
    background-color: #fff8f8;
    cursor: pointer;
    transition: all 0.3s;
" onclick="activateFocus()">
    <span style="font-size: 32px;">📋</span>
    <p style="margin: 10px 0 0 0; font-weight: bold; color: #31333F; font-size: 16px;">
        【电脑端】先点我一下，然后直接按 Ctrl + V 粘贴截图
    </p>
    <p style="margin: 4px 0 0 0; color: #7f8c8d; font-size: 13px;">
        【手机端】直接点击本框，即可从相册选择最新截图
    </p>
    <input type="file" id="hidden-file-input" accept="image/*" style="display:none;" onchange="handleFileSelect(this)">
    <div id="success-prompt" style="margin-top: 12px; display: none;">
        <p style="color: #2ecc71; font-weight: bold; font-size: 14px; margin: 0;">✅ 截图捕获成功！正在预览...</p>
        <img id="img-preview" style="max-width: 100%; max-height: 150px; margin-top: 10px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
    </div>
</div>

<script>
// 点击大框时，如果是手机端则触发文件选择，如果是电脑端则准备聚焦接收粘贴
function activateFocus() {
    const box = document.getElementById('paste-zone');
    box.style.backgroundColor = '#ffe9e9';
    box.style.borderColor = '#ff2b2b';
    
    // 如果是移动端或点击，同时唤醒隐式上传以保障兼容性
    if (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) {
        document.getElementById('hidden-file-input').click();
    }
}

// 电脑端 Ctrl+V 粘贴事件监听
document.addEventListener('paste', function (e) {
    const items = (e.clipboardData || e.originalEvent.clipboardData).items;
    for (let i = 0; i < items.length; i++) {
        if (items[i].type.indexOf('image') !== -1) {
            const blob = items[i].getAsFile();
            processBlob(blob);
        }
    }
});

// 手机端文件选择处理
function handleFileSelect(input) {
    if (input.files && input.files[0]) {
        processBlob(input.files[0]);
    }
}

// 统一处理图片二进制并回传到后台
function processBlob(blob) {
    const reader = new FileReader();
    reader.onload = function (event) {
        const base64Data = event.target.result.split(',')[1];
        
        // 显示前端预览
        document.getElementById('success-prompt').style.display = 'block';
        document.getElementById('img-preview').src = event.target.result;
        
        // 核心：把 base64 数据安全发送给后台 Python 变量传递器
        const shareData = {
            isStreamlitMessage: true,
            type: "streamlit:setComponentValue",
            value: base64Data
        };
        window.parent.postMessage(shareData, "*");
    };
    reader.readAsDataURL(blob);
}
</script>
"""

# 渲染混合式导入盒，接收从前端捕获的 Base64 数据
captured_img_base64 = st.components.v1.html(paste_and_upload_html, height=270)

# 如果前端成功捕获到图片数据
if captured_img_base64:
    if st.button("🚀 开始无脑提取生词", type="primary", use_container_width=True):
        if not API_KEY:
            st.error("请先在 Streamlit 后台配置您的 DASHSCOPE_API_KEY！")
        else:
            with st.spinner("视觉大模型正在解析图片，提炼生词和标准牛津释义..."):
                ai_result = call_ai_to_extract_from_image(captured_img_base64)
                if ai_result:
                    new_count = 0
                    for w, info in ai_result.items():
                        word_lower = w.strip().lower()
                        if word_lower not in st.session_state.words:
                            st.session_state.words[word_lower] = info
                            new_count += 1
                    save_to_local()
                    st.success(f"🎉 成功识别截图！导入了 {new_count} 个未掌握生词。")
                    st.rerun()

st.divider()

# 分栏标签页
tab1, tab2 = st.tabs(["📚 生词本 (高清美音)", "🎲 随机复习模式"])

with tab1:
    if not st.session_state.words:
        st.info("词本空空如也，快去上面粘贴或选择截图吧！")
    else:
        sorted_words = sorted(st.session_state.words.keys())
        
        st.markdown("### 🎧 高清美音·连播磨耳朵控制台")
        
        # 控制参数的滑块
        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1.5, 1.2, 1.3])
        with col_ctrl1:
            loop_rate = st.slider("朗读语速", min_value=0.5, max_value=1.5, value=1.0, step=0.1)
            infinite_loop = st.checkbox("🔄 无限循环播放列表", value=False)
        with col_ctrl2:
            repeat_count = st.slider("每个单词复读次数", min_value=1, max_value=5, value=3, step=1)
        with col_ctrl3:
            loop_interval = st.slider("单词跟读间隔(秒)", min_value=1, max_value=5, value=2, step=1)
            
        # 终极修复方案 2：纯前端播放引擎
        # 将播放状态、音频对象生命周期完全保留在 HTML 组件内部，绝不受 Python 页面刷新的任何干扰！
        words_json = json.dumps(sorted_words)
        infinite_js = "true" if infinite_loop else "false"
        
        player_html = f"""
        <div style="background-color: #f8f9fa; border-radius: 8px; padding: 15px; border: 1px solid #e9ecef; display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 22px;">🔊</span>
                <span id="player-status" style="font-size: 14px; color: #2c3e50; font-weight: bold;">播音器已就绪</span>
            </div>
            <div style="display: flex; gap: 8px;">
                <button id="btn-play" onclick="startLoop()" style="background-color: #ff4b4b; color: white; border: none; border-radius: 5px; padding: 8px 18px; font-weight: bold; cursor: pointer; font-size: 14px;">▶️ 开始连播</button>
                <button id="btn-stop" onclick="stopLoop()" style="background-color: #6c757d; color: white; border: none; border-radius: 5px; padding: 8px 18px; font-weight: bold; cursor: pointer; font-size: 14px;">⏹️ 停止</button>
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
        
        // 使用前端独立的高级 HTML5 Audio 播放器环境
        var localAudio = null;

        function updateStatus(text) {{
            document.getElementById('player-status').innerText = text;
        }}

        function startLoop() {{
            if (words.length === 0) {{
                updateStatus("没有可播放的单词");
                return;
            }}
            if (isPlaying) return;
            
            isPlaying = true;
            index = 0;
            currentRepeat = 0;
            document.getElementById('btn-play').style.opacity = '0.5';
            
            // 初始化音频对象
            if (!localAudio) {{
                localAudio = new Audio();
            }}
            playNextWord();
        }}

        function stopLoop() {{
            isPlaying = false;
            if (localAudio) {{
                localAudio.pause();
            }}
            document.getElementById('btn-play').style.opacity = '1';
            updateStatus("已手动停止");
        }}

        function playNextWord() {{
            if (!isPlaying) return;
            
            if (index < words.length) {{
                var word = words[index];
                updateStatus("正在朗读: " + word + " (" + (currentRepeat + 1) + "/" + repeatLimit + ")");
                
                // 清洗并加载网易有道官方高清美音接口（绝对纯净的字符串拼接，无 Markdown 污染）
                var targetUrl = "[https://dict.youdao.com/dictvoice?type=2&audio=](https://dict.youdao.com/dictvoice?type=2&audio=)" + encodeURIComponent(word);
                
                localAudio.src = targetUrl;
                localAudio.playbackRate = {loop_rate};
                
                localAudio.onended = function() {{
                    currentRepeat++;
                    if (currentRepeat < repeatLimit) {{
                        setTimeout(playNextWord, delay);
                    }} else {{
                        currentRepeat = 0;
                        index++;
                        setTimeout(playNextWord, delay);
                    }}
                }};
                
                localAudio.onerror = function() {{
                    console.log("音频加载发生错误，跳过此词防止卡死");
                    index++;
                    currentRepeat = 0;
                    setTimeout(playNextWord, 200);
                }};
                
                localAudio.play().catch(function(err) {{
                    console.log("播放失败，尝试等待后继续", err);
                    index++;
                    currentRepeat = 0;
                    setTimeout(playNextWord, 500);
                }});
                
            }} else if (infinite && words.length > 0) {{
                index = 0;
                currentRepeat = 0;
                setTimeout(playNextWord, delay);
            }} else {{
                isPlaying = false;
                document.getElementById('btn-play').style.opacity = '1';
                updateStatus("🎉 整个列表已全盘朗读完毕！");
            }}
        }}
        </script>
        """
        st.components.v1.html(player_html, height=90)
        st.divider()
        
        # --- 单词列表展示 ---
        for w in sorted_words:
            info = st.session_state.words[w]
            col_word, col_btn = st.columns([5, 1])
            with col_word:
                expander_title = f"**{w}** |  {info.get('phonetic','')}  |  {info.get('def_zh','')}"
                with st.expander(expander_title):
                    st.markdown(f"**💡 Oxford Style:**\n*{info.get('def_en','')}*")
                    st.markdown(f"**📝 Example:**\n{info.get('example','')}")
                    
                    ex_sentence = info.get('example','')
                    if ex_sentence:
                        ex_url = f"[https://dict.youdao.com/dictvoice?type=2&audio=](https://dict.youdao.com/dictvoice?type=2&audio=){st.experimental_webbase_component.encode_url(ex_sentence) if hasattr(st, 'experimental_webbase_component') else ex_sentence}"
                        ex_btn_html = f"""
                        <button onclick="new Audio('[https://dict.youdao.com/dictvoice?type=2&audio=](https://dict.youdao.com/dictvoice?type=2&audio=)' + encodeURIComponent('{ex_sentence.replace("'", "\\'")}')).play()" style="
                            background-color: #f1f3f5; border: none; border-radius: 4px; padding: 4px 10px; cursor: pointer; font-size: 12px; font-weight: bold; color: #495057; display: flex; align-items: center; gap: 4px;
                        ">🔊 读例句</button>
                        """
                        st.components.v1.html(ex_btn_html, height=35)
                        
                    if st.button(f"🗑️ 斩了", key=f"del_{w}"):
                        del st.session_state.words[w]
                        save_to_local()
                        st.rerun()
            with col_btn:
                word_url_encoded = w.replace("'", "\\'")
                single_btn_html = f"""
                <button onclick="new Audio('[https://dict.youdao.com/dictvoice?type=2&audio=](https://dict.youdao.com/dictvoice?type=2&audio=)' + encodeURIComponent('{word_url_encoded}')).play()" style="
                    background: none; border: none; font-size: 20px; cursor: pointer; padding: 5px 10px; border-radius: 5px; transition: background 0.2s; width: 100%; text-align: center;
                " onmouseover="this.style.background='#f0f2f6'" onmouseout="this.style.background='none'">🔊</button>
                """
                st.components.v1.html(single_btn_html, height=45)

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
        review_w_js = review_w.replace("'", "\\'")
        review_btn_html = f"""
        <button onclick="new Audio('[https://dict.youdao.com/dictvoice?type=2&audio=](https://dict.youdao.com/dictvoice?type=2&audio=)' + encodeURIComponent('{review_w_js}')).play()" style="
            background-color: #ff4b4b; color: white; border: none; border-radius: 5px; padding: 8px 16px; font-weight: bold; cursor: pointer; display: flex; align-items: center; gap: 6px; font-size: 14px;
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
            
            ex_sentence = review_info.get('example','')
            if ex_sentence:
                review_ex_btn_html = f"""
                <button onclick="new Audio('[https://dict.youdao.com/dictvoice?type=2&audio=](https://dict.youdao.com/dictvoice?type=2&audio=)' + encodeURIComponent('{ex_sentence.replace("'", "\\'")}')).play()" style="
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
