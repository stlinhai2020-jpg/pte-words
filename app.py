import streamlit as st
import json
import os
import random
import base64
import re
from openai import OpenAI

# 页面基础配置（自适应移动端与PC端）
st.set_page_config(page_title="PTE极简生词本", layout="centered", initial_sidebar_state="collapsed")

# --- 1. 配置阿里通义千问模型 ---
API_KEY = st.secrets.get("DASHSCOPE_API_KEY", "") 
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL_NAME = "qwen-vl-max" 

def encode_image(image_bytes):
    return base64.b64encode(image_bytes).decode('utf-8')

def extract_json_from_text(text):
    """提取纯净JSON，防止大模型废话导致报错"""
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        return match.group(0)
    return text

def call_ai_to_extract_from_image(base64_image):
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    prompt = """
    你是一个资深的PTE备考专家。请识别截图中的学术词汇（过滤简单词），按牛津词典风格提供：音标、英文释义、中文释义、一句话经典例句。
    必须且只能返回标准的 JSON 数据块，绝不能包含任何 Markdown 标记和多余废话。
    """
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}],
            temperature=0.1
        )
        return json.loads(extract_json_from_text(response.choices[0].message.content))
    except Exception as e:
        st.error(f"AI 图像解析出错: {e}")
        return None

def call_ai_to_extract_from_text(raw_text):
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    prompt = f"""
    分析以下PTE文本，找出较难的学术词汇，并按牛津双解标准输出JSON。
    必须且只能返回标准的 JSON 数据块，绝不附加任何其他诸如“好的”的解释性文本！
    待分析文本：\n{raw_text}
    """
    try:
        response = client.chat.completions.create(
            model="qwen-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        return json.loads(extract_json_from_text(response.choices[0].message.content))
    except Exception as e:
        st.error(f"AI 文本解析出错啦: {e}")
        return None

# --- 2. 云端数据库 (Supabase) 模块 ---
raw_url = st.secrets.get("SUPABASE_URL", "").strip()
# 强力清洗 URL，防止用户误粘贴带有 /rest/v1 路径或结尾斜杠导致 PGRST125 Invalid path 报错
SUPABASE_URL = raw_url.split("/rest/v1")[0].rstrip("/") if raw_url else ""
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "").strip()

@st.cache_resource
def init_supabase():
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            from supabase import create_client
            return create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            print(f"Supabase Client 初始化失败: {e}")
    return None

supabase = init_supabase()

# 加载数据
if "words" not in st.session_state:
    st.session_state.words = {}
    is_cloud_synced = False
    if supabase:
        try:
            response = supabase.table("words").select("*").execute()
            for row in response.data:
                st.session_state.words[row['word']] = {
                    "phonetic": row.get('phonetic', ''),
                    "def_en": row.get('def_en', ''),
                    "def_zh": row.get('def_zh', ''),
                    "example": row.get('example', '')
                }
            is_cloud_synced = True
        except Exception as e:
            st.warning(f"⚠️ 云端连接异常，暂用本地。报错: {e}")
            
    if not is_cloud_synced and os.path.exists("words_db.json"):
        with open("words_db.json", "r", encoding="utf-8") as f:
            st.session_state.words = json.load(f)

def batch_upsert_to_db(new_words_dict):
    data_to_insert = []
    for w, info in new_words_dict.items():
        st.session_state.words[w] = info
        data_to_insert.append({
            "word": w,
            "phonetic": info.get("phonetic", ""),
            "def_en": info.get("def_en", ""),
            "def_zh": info.get("def_zh", ""),
            "example": info.get("example", "")
        })
    if supabase and data_to_insert:
        try:
            supabase.table("words").upsert(data_to_insert).execute()
            return True
        except: return False
    else:
        with open("words_db.json", "w", encoding="utf-8") as f:
            json.dump(st.session_state.words, f, ensure_ascii=False)
        return False

def delete_word_from_db(word):
    if word in st.session_state.words:
        del st.session_state.words[word]
    if supabase:
        try: supabase.table("words").delete().eq("word", word).execute()
        except: pass
    else:
        with open("words_db.json", "w", encoding="utf-8") as f:
            json.dump(st.session_state.words, f, ensure_ascii=False)

# --- 3. 页面交互 UI 逻辑 ---
st.title("⚡ PTE 智能生词本")
st.caption("截图/文本导入 | 有道真人美音 | 云端同步不丢失")

st.markdown("### 📥 生词智能导入")
st.info("💡 **提示**：点击下方带有「Upload」的虚线框使其高亮，然后直接按键盘 `Ctrl+V` 即可粘贴截图！")

uploaded_file = st.file_uploader("👉 粘贴截图、拖拽图片或点击选择", type=["png", "jpg", "jpeg"])

with st.expander("✍️ 无法截图？点击这里直接粘贴PTE评分或华尔街日报原文"):
    pasted_text = st.text_area("把大段文本贴在这里：", placeholder="Today, we are going to discuss subsequently allocated resources...")

# 处理截图逻辑
if uploaded_file is not None:
    img_bytes = uploaded_file.read()
    st.image(img_bytes, caption='已捕获的截图', use_container_width=True)
    
    if st.button("🚀 开始提取生词 (基于截图)", type="primary", use_container_width=True):
        if not API_KEY: st.error("请配置 DASHSCOPE_API_KEY")
        else:
            with st.spinner("大模型正在解析图片提炼生词..."):
                ai_result = call_ai_to_extract_from_image(encode_image(img_bytes))
                if ai_result:
                    new_words = {w.strip().lower(): info for w, info in ai_result.items() if w.strip().lower() not in st.session_state.words}
                    if new_words:
                        batch_upsert_to_db(new_words)
                        st.success(f"🎉 成功导入 {len(new_words)} 个新词！")
                    else: st.info("提取的单词均已在词库中。")
                    st.rerun()

# 处理文本粘贴逻辑
elif pasted_text.strip():
    if st.button("🚀 开始提取生词 (基于文本)", type="primary", use_container_width=True):
        if not API_KEY: st.error("请配置 DASHSCOPE_API_KEY")
        else:
            with st.spinner("大模型正在分析文本提炼生词..."):
                ai_result = call_ai_to_extract_from_text(pasted_text)
                if ai_result:
                    new_words = {w.strip().lower(): info for w, info in ai_result.items() if w.strip().lower() not in st.session_state.words}
                    if new_words:
                        batch_upsert_to_db(new_words)
                        st.success(f"🎉 成功导入 {len(new_words)} 个新词！")
                    else: st.info("提取的单词均已在词库中。")
                    st.rerun()

st.divider()

# 分栏标签页
tab1, tab2 = st.tabs(["📚 生词本 (高清美音)", "🎲 随机复习模式"])

with tab1:
    if not st.session_state.words:
        st.info("词库空空如也，快去上方导入吧！")
    else:
        sorted_words = sorted(st.session_state.words.keys())
        
        st.markdown("### 🎧 高清美音·连播磨耳朵控制台")
        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1.5, 1.2, 1.3])
        with col_ctrl1:
            loop_rate = st.slider("朗读语速", 0.5, 1.5, 1.0, 0.1)
            infinite_loop = st.checkbox("🔄 无限循环播放", value=False)
        with col_ctrl2:
            repeat_count = st.slider("单词复读次数", 1, 5, 3, 1)
        with col_ctrl3:
            loop_interval = st.slider("跟读间隔(秒)", 0.0, 5.0, 0.5, 0.1)
            
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
        var localAudio = null;
        function updateStatus(text) {{ document.getElementById('player-status').innerText = text; }}
        function startLoop() {{
            if (words.length === 0) {{ updateStatus("没有单词可读"); return; }}
            if (isPlaying) return;
            isPlaying = true; index = 0; currentRepeat = 0;
            document.getElementById('btn-play').style.opacity = '0.5';
            if (!localAudio) {{ localAudio = new Audio(); }}
            playNextWord();
        }}
        function stopLoop() {{
            isPlaying = false;
            if (localAudio) {{ localAudio.pause(); }}
            document.getElementById('btn-play').style.opacity = '1';
            updateStatus("已手动停止");
        }}
        function playNextWord() {{
            if (!isPlaying) return;
            if (index < words.length) {{
                var word = words[index];
                updateStatus("朗读中: " + word + " (" + (currentRepeat + 1) + "/" + repeatLimit + ")");
                var targetUrl = "https://dict.youdao.com/dictvoice?type=2&audio=" + encodeURIComponent(word);
                localAudio.src = targetUrl;
                localAudio.playbackRate = {loop_rate};
                localAudio.onended = function() {{
                    currentRepeat++;
                    if (currentRepeat < repeatLimit) {{ setTimeout(playNextWord, delay); }} 
                    else {{ currentRepeat = 0; index++; setTimeout(playNextWord, delay); }}
                }};
                localAudio.onerror = function() {{ index++; currentRepeat = 0; setTimeout(playNextWord, 200); }};
                localAudio.play().catch(function(err) {{ index++; currentRepeat = 0; setTimeout(playNextWord, 500); }});
            }} else if (infinite && words.length > 0) {{
                index = 0; currentRepeat = 0; setTimeout(playNextWord, delay);
            }} else {{
                isPlaying = false;
                document.getElementById('btn-play').style.opacity = '1';
                updateStatus("🎉 列表朗读完毕！");
            }}
        }}
        </script>
        """
        st.components.v1.html(player_html, height=90)
        st.divider()
        
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
                        ex_btn_html = f"""
                        <button onclick="new Audio('https://dict.youdao.com/dictvoice?type=2&audio=' + encodeURIComponent('{ex_sentence.replace("'", "\\'")}').replace(/"/g, '&quot;')).play()" style="
                            background-color: #f1f3f5; border: none; border-radius: 4px; padding: 4px 10px; cursor: pointer; font-size: 12px; font-weight: bold; color: #495057; display: flex; align-items: center; gap: 4px;
                        ">🔊 读例句</button>
                        """
                        st.components.v1.html(ex_btn_html, height=35)
                        
                    if st.button(f"🗑️ 斩了 (从云端删除)", key=f"del_{w}"):
                        delete_word_from_db(w)
                        st.rerun()
            with col_btn:
                word_url_encoded = w.replace("'", "\\'").replace('"', '&quot;')
                single_btn_html = f"""
                <button onclick="new Audio('https://dict.youdao.com/dictvoice?type=2&audio=' + encodeURIComponent('{word_url_encoded}')).play()" style="
                    background: none; border: none; font-size: 20px; cursor: pointer; padding: 5px 10px; border-radius: 5px; transition: background 0.2s; width: 100%; text-align: center;
                " onmouseover="this.style.background='#f0f2f6'" onmouseout="this.style.background='none'">🔊</button>
                """
                st.components.v1.html(single_btn_html, height=45)

with tab2:
    if not st.session_state.words:
        st.info("词库空空如也，无法复习。")
    else:
        if "current_review_word" not in st.session_state or st.session_state.current_review_word not in st.session_state.words:
            st.session_state.current_review_word = random.choice(list(st.session_state.words.keys()))
            st.session_state.show_answer = False
            
        review_w = st.session_state.current_review_word
        review_info = st.session_state.words[review_w]
        st.markdown(f"## ❓ **{review_w}**")
        
        review_w_js = review_w.replace("'", "\\'").replace('"', '&quot;')
        review_btn_html = f"""
        <button onclick="new Audio('https://dict.youdao.com/dictvoice?type=2&audio=' + encodeURIComponent('{review_w_js}')).play()" style="
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
                <button onclick="new Audio('https://dict.youdao.com/dictvoice?type=2&audio=' + encodeURIComponent('{ex_sentence.replace("'", "\\'")}').replace(/"/g, '&quot;')).play()" style="
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
