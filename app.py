import streamlit as st
import json
import os
import random
from openai import OpenAI

# 页面基础配置（适配手机端和电脑端）
st.set_page_config(page_title="PTE极简生词本", layout="centered", initial_sidebar_state="collapsed")

# --- 1. 配置你的 AI API ---
# 提示：你可以直接把 Key 贴在这里，或者在 Streamlit 后台配置 Secrets
API_KEY = "sk-26f65a74296744a4a01d2a85c9aabedb" 
BASE_URL = "https://api.deepseek.com" # 如果用其他大模型，换成对应的URL即可

def call_ai_to_extract(text):
    """调用大模型：分析PTE文本，提取生词，并返回标准的牛津双解格式 JSON"""
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    
    prompt = f"""
    你是一个资深的PTE备考专家和高级英语词典编纂者。
    请分析以下PTE题目原文或评分文本，找出其中对于想考PTE四个65分（大约雅思6.5分）的学生来说，较难、较生僻或重要的学术词汇（过滤掉the, is, standard等过于简单的基础词）。
    
    对于挑选出来的每个生词，请严格按照牛津词典（Oxford Style）提供以下内容：
    1. 音标 (国际音标，如 /ˈæləkeɪt/)
    2. 纯英文释义 (精准、地道的英文解释)
    3. 中文释义 (简明扼要的中文翻译)
    4. 经典例句 (一句话，最好契合PTE或学术场景)
    
    待分析文本：
    \"\"\"{text}\"\"\"
    
    必须且只能返回标准的 JSON 格式数据，不要包含任何 Markdown 标记（如 ```json），不要包含任何解释性文字。格式示例如下：
    {{
        "word1": {{
            "phonetic": "/.../",
            "def_en": "...",
            "def_zh": "...",
            "example": "..."
        }}
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat", # 或者用你平台对应的模型名称
            messages=[
                {"role": "system", "content": "You are a precise JSON generator for English vocabulary."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1, # 低随机性，确保格式和翻译稳定
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"AI 查询出错啦: {e}")
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
st.caption("免登录 | 本地存储 | AI 智能自动提取")

# 录入区域
st.markdown("### 📥 PTE 文本/评分 无脑导入")
pte_text = st.text_area("直接把 APEUni 里的原文或 AI 评分内容整段贴进来：", placeholder="把整段文本、或者你复制的错题内容贴在这...", height=130)

if st.button("🚀 AI 自动过滤并提取生词", type="primary"):
    if not pte_text.strip():
        st.warning("请输入文本后再点击提取。")
    elif API_KEY == "你的_DEEPSEEK_API_KEY":
        st.error("请先在代码第 11 行配置你的真实 AI API Key！")
    else:
        with st.spinner("AI 正在深度解析文本，过滤熟词并查询牛津释义..."):
            ai_result = call_ai_to_extract(pte_text)
            if ai_result:
                new_count = 0
                for w, info in ai_result.items():
                    word_lower = w.strip().lower()
                    if word_lower not in st.session_state.words:
                        st.session_state.words[word_lower] = info
                        new_count += 1
                save_to_local()
                st.success(f"🎉 成功识别并自动导入 {new_count} 个重要 PTE 生词！")
                st.rerun()

st.divider()

# 导航栏切换：看词本、复习
tab1, tab2 = st.tabs(["📚 生词本 (字母排序)", "🎲 随机复习模式"])

# 功能 3：生词本展示
with tab1:
    if not st.session_state.words:
        st.info("词本空空如也，快去上面导入文本吧！")
    else:
        sorted_words = sorted(st.session_state.words.keys())
        for w in sorted_words:
            info = st.session_state.words[w]
            with st.expander(f"**{w}**  |  {info.get('phonetic','')}  |  {info.get('def_zh','')}结构"):
                st.markdown(f"**💡 Oxford Style:**\n*{info.get('def_en','')}\n\n**📝 Example:**\n{info.get('example','')}")
                if st.button(f"🗑️ 斩了", key=f"del_{w}"):
                    del st.session_state.words[w]
                    save_to_local()
                    st.rerun()

# 功能 4：复习模式
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
