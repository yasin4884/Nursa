from openai import OpenAI
import gradio as gr
import logging
import sqlite3
import easyocr
from datetime import datetime
import hashlib
import io
import base64
from PIL import Image
import os
import secrets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("Loading API key...")
KEY = os.getenv("KEY")
if not KEY:
    logger.error("Error in token")
    print("Error in token - Please set KEY environment variable")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=KEY,
)

def extract_text_easyocr(image_path):
    try:
        reader = easyocr.Reader(["en", "fa"])
        result = reader.readtext(image_path)
        text = ""
        for ocr in result:
            text += ocr[1] + " "
        return text.strip()
    except Exception as e:
        logger.error(f"Error in EasyOCR: {e}")
        return ""

def init_database():
    try:
        conn = sqlite3.connect("nurca.db")
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS chat_history(
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         session_id TEXT,
                         input_text TEXT,
                         input_image TEXT,
                         response TEXT,
                         timestamp TEXT,
                         query_type TEXT
                         )''')
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error in creating database: {e}")

def create_session():
    try:
        x=datetime.utcnow().isoformat()
        n=secrets.token_hex(8)
        s=hashlib.sha256((str(x+n)).encode()).hexdigest()
        return s[:15]
    except Exception as e:
        print("error session") 
        logger.error(f"error session:{e}")
        return "default_session"

def save_to_database(session_id, input_text, input_image, response, query_type):
    try:
        conn = sqlite3.connect("nurca.db")
        cursor = conn.cursor()
        
        image_data = None
        if input_image is not None:
            buffered = io.BytesIO()
            input_image.save(buffered, format="PNG")
            image_data = base64.b64encode(buffered.getvalue()).decode()
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute('''INSERT INTO chat_history(session_id, input_text, input_image, response, timestamp, query_type)
                         VALUES(?, ?, ?, ?, ?, ?)''',
                      (session_id, input_text, image_data, response, timestamp, query_type))
        conn.commit()
        conn.close()
        logger.info("Data saved successfully")
    except Exception as e:
        logger.error(f"Error saving to database: {e}")

def get_user_history(session_id):
    """دریافت تاریخچه کاربر"""
    try:
        conn = sqlite3.connect("nurca.db")
        cursor = conn.cursor()
        cursor.execute('''SELECT timestamp, query_type, input_text, response 
                         FROM chat_history WHERE session_id = ? 
                         ORDER BY timestamp DESC LIMIT 10''', (session_id,))
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return "📝 هنوز تاریخچه‌ای ندارید"
        
        history_text = "# 📊 تاریخچه شما\n\n"
        for i, (timestamp, query_type, input_text, response) in enumerate(results, 1):
            emoji = "💊" if query_type == "drug_interaction" else "🔬" if query_type == "lab_analysis" else "💬"
            history_text += f"## {emoji} مورد {i} - {timestamp}\n\n"
            history_text += f"**ورودی:** {input_text[:100]}...\n\n"
            history_text += f"**پاسخ:** {response[:200]}...\n\n---\n\n"
        
        return history_text
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return "❌ خطا در دریافت تاریخچه"

def clear_user_history(session_id):
    """پاک کردن تاریخچه"""
    try:
        conn = sqlite3.connect("nurca.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
        return "✅ تاریخچه شما پاک شد!"
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        return "❌ خطا در پاک کردن تاریخچه"

def get_chat_history(session_id):
    """دریافت تاریخچه چت برای حافظه مکالمه"""
    try:
        conn = sqlite3.connect("nurca.db")
        cursor = conn.cursor()
        cursor.execute('''SELECT input_text, response 
                         FROM chat_history WHERE session_id = ? AND query_type = 'symptom_chat'
                         ORDER BY timestamp ASC LIMIT 10''', (session_id,))
        results = cursor.fetchall()
        conn.close()
        
        chat_messages = []
        for input_text, response in results:
            chat_messages.append({"role": "user", "content": input_text})
            chat_messages.append({"role": "assistant", "content": response})
        
        return chat_messages
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        return []

def analyze_drug_interaction(drug1, drug2, session_id):
    """تحلیل تداخل دارویی"""
    if not drug1.strip() or not drug2.strip():
        return "⚠️ لطفاً نام هر دو دارو را وارد کنید"
    
    try:
        prompt = f"""شما یک متخصص داروسازی و فارماکولوژی هستید. لطفاً تداخل بین این دو دارو را به صورت کامل تحلیل کنید:

دارو اول: {drug1}
دارو دوم: {drug2}

لطفاً موارد زیر را بررسی کنید:
1. آیا این دو دارو تداخل دارند؟
2. نوع تداخل (فارماکوکینتیک یا فارماکودینامیک)
3. شدت تداخل (خفیف، متوسط، شدید)
4. مکانیسم تداخل
5. عوارض جانبی احتمالی
6. توصیه‌های عملی برای بیمار
7. نیاز به تغییر دوز یا زمان‌بندی

پاسخ را به فارسی و با جزئیات کامل ارائه دهید."""

        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://medical-ai.com",
                "X-Title": "Medical Drug Interaction Checker",
            },
            extra_body={},
            model="openai/gpt-oss-20b:free",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        result = completion.choices[0].message.content
        
        # ذخیره در دیتابیس
        save_to_database(session_id, f"تداخل دارویی: {drug1} + {drug2}", None, result, "drug_interaction")
        
        return f"# 💊 تحلیل تداخل دارویی\n\n## داروهای بررسی شده:\n- **{drug1}**\n- **{drug2}**\n\n## نتیجه تحلیل:\n\n{result}"
        
    except Exception as e:
        error_msg = f"❌ خطا در تحلیل: {str(e)}"
        logger.error(error_msg)
        return error_msg

def analyze_lab_image(image, session_id):
    """تحلیل تصویر آزمایش"""
    if image is None:
        return "⚠️ لطفاً تصویر آزمایش را آپلود کنید"
    
    try:
        # ذخیره موقت تصویر برای OCR
        temp_path = "temp_image.png"
        image.save(temp_path)
        
        # استخراج متن از تصویر
        extracted_text = extract_text_easyocr(temp_path)
        
        # حذف فایل موقت
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        prompt = f"""شما یک متخصص آزمایشگاه و پاتولوژیست هستید. این متن از یک نتیجه آزمایش استخراج شده:

{extracted_text}

لطفاً این نتیجه آزمایش را تحلیل کنید:

1. نوع آزمایش را شناسایی کنید
2. مقادیر غیرطبیعی را مشخص کنید
3. تفسیر بالینی نتایج
4. نکات مهم برای بیمار
5. نیاز به آزمایش‌های تکمیلی
6. توصیه‌های اولیه

⚠️ تأکید: این تحلیل صرفاً جهت اطلاع اولیه است و جایگزین مشاوره پزشک نیست.

پاسخ را به فارسی و با جزئیات کامل بدهید."""

        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://medical-ai.com",
                "X-Title": "Medical Lab Analysis",
            },
            extra_body={},
            model="openai/gpt-oss-20b:free",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        result = completion.choices[0].message.content
        
        # ذخیره در دیتابیس
        save_to_database(session_id, "تحلیل تصویر آزمایش", image, result, "lab_analysis")
        
        return f"# 🔬 تحلیل نتیجه آزمایش\n\n## متن استخراج شده:\n```\n{extracted_text}\n```\n\n## تحلیل:\n\n{result}"
        
    except Exception as e:
        error_msg = f"❌ خطا در تحلیل تصویر: {str(e)}"
        logger.error(error_msg)
        return error_msg

def symptom_diagnosis(symptoms, session_id):
    """تشخیص بیماری بر اساس علائم"""
    if not symptoms.strip():
        return "⚠️ لطفاً علائم خود را توضیح دهید"
    
    try:
        prompt = f"""شما یک پزشک عمومی مهربان و با تجربه هستید. بیمار این علائم را دارد:

علائم: {symptoms}

لطفاً به شکل مهربان و دلگرم کننده موارد زیر را بررسی کنید:
1. احتمالی‌ترین تشخیص‌ها (با ذکر احتمال)
2. علائم تکمیلی که باید سؤال شود
3. راهنمایی‌های خانگی و خودمراقبتی
4. داروهای بدون نسخه که ممکن است کمک کند
5. چه زمانی حتماً باید به پزشک مراجعه کند
6. کلمات آرامش‌بخش و امیدوارانه

⚠️ تأکید کنید که این تشخیص اولیه است و باید با پزشک مشورت شود.

پاسخ را به زبان فارسی، مهربان و کامل بدهید. از کلمات دلگرم کننده استفاده کنید."""

        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://medical-ai.com",
                "X-Title": "Medical Symptom Analysis",
            },
            extra_body={},
            model="openai/gpt-oss-20b:free",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        result = completion.choices[0].message.content
        
        # ذخیره در دیتابیس
        save_to_database(session_id, f"تشخیص علائم: {symptoms}", None, result, "symptom_diagnosis")
        
        return f"# 🩺 تشخیص بر اساس علائم\n\n## علائم شما:\n{symptoms}\n\n## نظر پزشک:\n\n{result}"
        
    except Exception as e:
        error_msg = f"❌ خطا در تشخیص: {str(e)}"
        logger.error(error_msg)
        return error_msg

def symptom_chat(message, chat_history, session_id):
    """چت تعاملی برای تشخیص علائم"""
    if not message.strip():
        return chat_history, ""
    
    try:
        # دریافت تاریخچه از دیتابیس
        db_history = get_chat_history(session_id)
        
        # ساخت context از تاریخچه
        context = "تاریخچه مکالمه قبلی:\n"
        for msg in db_history[-6:]:  # آخرین 6 پیام
            if msg["role"] == "user":
                context += f"بیمار: {msg['content']}\n"
            else:
                context += f"پزشک: {msg['content']}\n"
        
        prompt = f"""شما یک پزشک مهربان هستید که با بیمار چت می‌کنید.

{context}

پیام جدید بیمار: {message}

لطفاً:
1. به پیام بیمار پاسخ مهربانانه دهید
2. سؤالات تکمیلی مناسب بپرسید
3. اگر اطلاعات کافی دارید، تشخیص احتمالی ارائه دهید
4. همیشه تأکید کنید که باید با پزشک مشورت شود

پاسخ کوتاه و مفید باشد."""

        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://medical-ai.com",
                "X-Title": "Medical Chat",
            },
            extra_body={},
            model="openai/gpt-oss-20b:free",
            messages=[
                {
                    "role": "user", 
                    "content": prompt
                }
            ]
        )

        response = completion.choices[0].message.content
        
        # ذخیره در دیتابیس
        save_to_database(session_id, message, None, response, "symptom_chat")
        
        # بروزرسانی چت
        chat_history.append([message, response])
        
        return chat_history, ""
        
    except Exception as e:
        error_msg = f"❌ خطا: {str(e)}"
        logger.error(error_msg)
        chat_history.append([message, error_msg])
        return chat_history, ""

# راه‌اندازی دیتابیس
init_database()

def create_app():
    with gr.Blocks(
        theme=gr.themes.Soft(),
        css="""
        .main-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 20px;
            text-align: center;
            color: white;
        }
        .feature-box {
            background: #d97dfc;
            border-radius: 10px;
            padding: 20px;
            margin: 10px 0;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .warning-box {
            background: #ffa07a;
            border: 1px solid #ffeaa7;
            border-radius: 8px;
            padding: 15px;
            margin: 15px 0;
        }
        """,
        title="🏥 دستیار هوشمند پزشکی"
    ) as app:
        
        # session state برای ذخیره session id - هر بار رفرش جدید میشه
        session_state = gr.State()
        
        # هدر اصلی
        gr.HTML("""
        <div class="main-header">
            <h1>🏥Nursa دستیار هوشمند پزشکی</h1>
            <p>سیستم هوشمند تحلیل تداخلات دارویی و نتایج آزمایش</p>
        </div>
        """)
        
        # هشدار مهم
        gr.HTML("""
        <div class="warning-box">
            <h3>⚠️ هشدار مهم</h3>
            <p>این سیستم صرفاً جهت اطلاع‌رسانی اولیه است و هیچ‌گاه جایگزین مشاوره پزشک نمی‌شود. 
            برای تصمیم‌گیری‌های درمانی حتماً با پزشک متخصص مشورت کنید.</p>
        </div>
        """)
        
        with gr.Tabs():
            # تب تداخل دارویی
            with gr.Tab("💊 بررسی تداخل دارویی"):
                with gr.Row():
                    with gr.Column(scale=2):
                        gr.HTML('<div class="feature-box"><h3>🔍 بررسی تداخل بین داروها</h3></div>')
                        
                        drug1_input = gr.Textbox(
                            label="نام دارو اول",
                            placeholder="مثال: آسپرین، پاراستامول، ...",
                            lines=1
                        )
                        
                        drug2_input = gr.Textbox(
                            label="نام دارو دوم", 
                            placeholder="مثال: وارفارین، دیکلوفناک، ...",
                            lines=1
                        )
                        
                        analyze_btn = gr.Button("🔬 تحلیل تداخل", variant="primary", size="lg")
                    
                    with gr.Column(scale=3):
                        drug_result = gr.Markdown(
                            value="نتیجه تحلیل اینجا نمایش داده می‌شود...",
                            label="نتیجه تحلیل"
                        )
            
            # تب تحلیل آزمایش
            with gr.Tab("🔬 تحلیل نتایج آزمایش"):
                with gr.Row():
                    with gr.Column(scale=2):
                        gr.HTML('<div class="feature-box"><h3>📋 آپلود و تحلیل نتایج آزمایش</h3></div>')
                        
                        image_input = gr.Image(
                            label="تصویر نتیجه آزمایش",
                            type="pil",
                            height=300
                        )
                        
                        analyze_lab_btn = gr.Button("🧪 تحلیل آزمایش", variant="primary", size="lg")
                    
                    with gr.Column(scale=3):
                        lab_result = gr.Markdown(
                            value="نتیجه تحلیل آزمایش اینجا نمایش داده می‌شود...",
                            label="نتیجه تحلیل"
                        )
            
            # تب تشخیص علائم
            with gr.Tab("🩺 تشخیص بر اساس علائم"):
                with gr.Row():
                    with gr.Column(scale=2):
                        gr.HTML('<div class="feature-box"><h3>💬 توضیح علائم شما</h3></div>')
                        
                        symptoms_input = gr.Textbox(
                            label="علائم و نشانه‌های شما",
                            placeholder="مثال: سردرد شدید، تب، گلودرد، سرفه خشک، ضعف عمومی...",
                            lines=4
                        )
                        
                        diagnose_btn = gr.Button("🔍 تشخیص علائم", variant="primary", size="lg")
                    
                    with gr.Column(scale=3):
                        symptom_result = gr.Markdown(
                            value="نتیجه تشخیص اینجا نمایش داده می‌شود...",
                            label="نتیجه تشخیص"
                        )
            
            # تب چت تشخیص علائم
            with gr.Tab("💬 چت تشخیص علائم"):
                with gr.Column():
                    gr.HTML('<div class="feature-box"><h3>🩺 چت با دستیار پزشکی</h3></div>')
                    
                    chatbot = gr.Chatbot(
                        label="مکالمه با دستیار پزشکی",
                        height=400
                    )
                    
                    msg_input = gr.Textbox(
                        label="پیام شما",
                        placeholder="علائم خود را توضیح دهید یا سؤالات بپرسید...",
                        lines=2
                    )
                    
                    with gr.Row():
                        send_btn = gr.Button("📤 ارسال", variant="primary")
                        clear_chat_btn = gr.Button("🗑️ پاک کردن چت", variant="secondary")
            
            # تب تاریخچه
            with gr.Tab("📊 تاریخچه و مدیریت"):
                with gr.Row():
                    with gr.Column():
                        gr.HTML('<div class="feature-box"><h3>📝 مدیریت تاریخچه</h3></div>')
                        
                        with gr.Row():
                            show_history_btn = gr.Button("📋 نمایش تاریخچه", variant="secondary")
                            clear_history_btn = gr.Button("🗑️ پاک کردن تاریخچه", variant="stop")
                            new_session_btn = gr.Button("🔄 جلسه جدید", variant="primary")
                        
                        history_display = gr.Markdown(
                            value="برای نمایش تاریخچه، روی دکمه مربوطه کلیک کنید.",
                            label="تاریخچه کاربر"
                        )
                        
                        session_info = gr.Textbox(
                            value="",
                            label="شناسه جلسه",
                            interactive=False
                        )
        
        def create_new_session():
            new_session_id = create_session()
            return new_session_id, f"Session ID: {new_session_id[:8].upper()}"
        
        # اتصال eventها
        analyze_btn.click(
            fn=analyze_drug_interaction,
            inputs=[drug1_input, drug2_input, session_state],
            outputs=drug_result
        )
        
        analyze_lab_btn.click(
            fn=analyze_lab_image,
            inputs=[image_input, session_state],
            outputs=lab_result
        )
        
        diagnose_btn.click(
            fn=symptom_diagnosis,
            inputs=[symptoms_input, session_state],
            outputs=symptom_result
        )
        
        send_btn.click(
            fn=symptom_chat,
            inputs=[msg_input, chatbot, session_state],
            outputs=[chatbot, msg_input]
        )

        msg_input.submit(
            fn=symptom_chat,
            inputs=[msg_input, chatbot, session_state], 
            outputs=[chatbot, msg_input]
        )

        clear_chat_btn.click(
            fn=lambda: ([], ""),
            outputs=[chatbot, msg_input]
        )
        
        show_history_btn.click(
            fn=get_user_history,
            inputs=session_state,
            outputs=history_display
        )
        
        clear_history_btn.click(
            fn=clear_user_history,
            inputs=session_state,
            outputs=history_display
        )
        
        new_session_btn.click(
            fn=create_new_session,
            outputs=[session_state, session_info]
        )
        
        # نمایش session id اولیه - هر بار رفرش جدید میشه
        def initialize_new_session():
            new_session_id = create_session()
            return new_session_id, f"Session ID: {new_session_id[:8].upper()}"
        
        app.load(
            fn=initialize_new_session,
            outputs=[session_state, session_info]
        )
    
    return app

if __name__ == "__main__":
    app = create_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,
        show_api=False
    )
