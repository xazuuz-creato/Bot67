import os
import json
import httpx
import arabic_reshaper
from bidi.algorithm import get_display
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address

# 1. إعداد كابح الضغط لحماية باقة Render المجانية (512MB RAM)
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="VIDEO-LIKE Arabic Studio")

# السماح بالاتصال من أي واجهة خارجية بأمان
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. جلب مفتاح جوجل المجاني من متغيرات البيئة في Render
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

def fix_arabic_text(text: str) -> str:
    """تصحيح النصوص العربية وضبط اتجاهها من اليمين لليسار (RTL) لتجنب تقطيع الحروف"""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)

async def generate_pro_prompt(user_idea: str, style: str, mood: str) -> dict:
    """مولد البرومبت الاحترافي السحابي عبر Google Gemini API المجاني"""
    system_instruction = f"""
    أنت المخرج السينمائي ومهندس البرومبت الأسطوري لأداة VIDEO-LIKE.
    مهمتك: تحويل فكرة المستخدم إلى 3 مشاهد قصيرة ومشوقة متسلسلة.
    النمط التصميمي المطلوب: {style}
    الإعداد المزاجي والإيقاع: {mood} (وثائقي = رصين وهادئ، سينمائي = عميق ودرامي، ديناميكي = سريع وحماسي).

    قواعد الإخراج الإلزامية:
    1. اكتب السرد العربي (arabic_narration) بلغة عربية فصحى جذابة ومختصرة تناسب الفيديوهات القصيرة.
    2. اكتب الوصف البصري (visual_prompt_en) باللغة الإنجليزية بدقة فائقة ليفهمه محرك الفيديو، مع تحديد حركة الكاميرا والإضاءة بما يتوافق مع النمط ({style}) والإيقاع ({mood}).
    3. أخرج النتيجة بصيغة JSON فقط بدون أي مقدمات أو نصوص إضافية، وبنفس هذا الهيكل تماماً:
    {{
        "scenes": [
            {{
                "scene_number": 1,
                "arabic_narration": "النص العربي المشوق للمشهد الأول",
                "visual_prompt_en": "Detailed cinematic prompt in English for VIDEO-LIKE engine",
                "transition": "smooth_zoom_in"
            }}
        ]
    }}
    """
    
    # وضع التشغيل التجريبي في حال نسيان إضافة المفتاح في Render
    if not GEMINI_API_KEY:
        return {
            "scenes": [
                {
                    "scene_number": 1,
                    "arabic_narration": f"اكتشف أسرار {user_idea} بأسلوب مذهل.",
                    "visual_prompt_en": f"Cinematic {style} scene about {user_idea}, {mood} lighting, 4k, ultra detailed",
                    "transition": "fade_in"
                }
            ]
        }

    # الاتصال السريع بسيرفرات Google Gemini السحابية مجاناً
    url = f"https://googleapis.com{GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": f"{system_instruction}\n\nفكرة المستخدم: {user_idea}"}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.7
        }
    }

    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        result_text = data["candidates"]["content"]["parts"]["text"]
        return json.loads(result_text)

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """عرض ملف الواجهة الفخمة السلسة (index.html) مباشرة"""
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse("<h1>يرجى التأكد من وجود ملف index.html في نفس مجلد المشروع</h1>")

@app.websocket("/ws/studio")
async def websocket_endpoint(websocket: WebSocket):
    """قناة الاتصال الحية (WebSocket) لتحديث الواجهة دون تجميد السيرفر"""
    await websocket.accept()
    try:
        while True:
            raw_data = await websocket.receive_text()
            request_data = json.loads(raw_data)
            
            idea = request_data.get("idea", "").strip()
            style = request_data.get("style", "موشن جرافيك حديث")
            mood = request_data.get("mood", "سينمائي")

            if not idea:
                await websocket.send_json({"step": "error", "msg": "⚠️ يرجى كتابة فكرة الفيديو أولاً."})
                continue

            # الخطوة 1: إرسال تحديث حي للواجهة
            await websocket.send_json({
                "step": 1, 
                "msg": f"🧠 جاري تحليل الفكرة وتوليد برومبت ({style} - {mood}) عبر Gemini..."
            })
            
            # الخطوة 2: توليد السكربت والبرومبت سحابياً (صفر استهلاك لـ RAM السيرفر)
            pro_script = await generate_pro_prompt(idea, style, mood)
            
            # الخطوة 3: معالجة النصوص العربية وتهيئتها للرندرة
            for scene in pro_script.get("scenes", []):
                scene["fixed_arabic"] = fix_arabic_text(scene.get("arabic_narration", ""))

            await websocket.send_json({
                "step": 2, 
                "msg": "🎨 تم ضبط الخطوط العربية وهندسة المشاهد بنجاح!"
            })

            # الخطوة 4: إرسال الحزمة النهائية الجاهزة للواجهة
            await websocket.send_json({
                "step": 3,
                "msg": "✅ اكتمل التجهيز! البيانات والبرومبت جاهزة لأداة VIDEO-LIKE.",
                "generated_payload": pro_script
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"step": "error", "msg": f"❌ حدث خطأ أثناء المعالجة: {str(e)}"})
