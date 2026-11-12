import os
import json
import httpx
import arabic_reshaper
from bidi.algorithm import get_display
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

# إعداد كابح الضغط لحماية باقة Render المجانية (512MB RAM)
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="VIDEO-LIKE Arabic Studio")

# مفتاح Groq المجاني لتوليد البرومبت الاحترافي (يُضاف في إعدادات Render)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

def fix_arabic_text(text: str) -> str:
    """تصحيح النصوص العربية وضبط اتجاهها من اليمين لليسار"""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)

async def generate_pro_prompt(user_idea: str, style: str, mood: str) -> dict:
    """مولد البرومبت الاحترافي السحابي (يعمل خارج السيرفر لتوفير الذاكرة)"""
    system_instruction = f"""
    أنت مخرج سينمائي ومهندس برومبت لأداة VIDEO-LIKE.
    حول فكرة المستخدم إلى 3 مشاهد قصيرة.
    النمط المطلوب: {style} | الإعداد المزاجي: {mood}.
    أخرج النتيجة بصيغة JSON فقط بهذا الهيكل الدقيق:
    {{
        "scenes": [
            {{
                "scene_number": 1,
                "arabic_narration": "النص العربي المشوق للمشهد",
                "visual_prompt_en": "Detailed cinematic prompt in English for VIDEO-LIKE engine",
                "transition": "smooth_zoom_in"
            }}
        ]
    }}
    """
    
    # إذا لم يتوفر مفتاح API، نرجع نموذجاً تجريبياً فوراً
    if not GROQ_API_KEY:
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

    url = "https://groq.com"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_idea}
        ],
        "response_format": {"type": "json_object"}
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        data = response.json()
        return json.loads(data["choices"][0]["message"]["content"])

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """عرض الواجهة الفخمة والسلسة مباشرة"""
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.websocket("/ws/studio")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            raw_data = await websocket.receive_text()
            request_data = json.loads(raw_data)
            
            idea = request_data.get("idea", "")
            style = request_data.get("style", "موشن جرافيك")
            mood = request_data.get("mood", "سينمائي")

            # 1. تحديث حي للواجهة
            await websocket.send_json({"step": 1, "msg": "🧠 جاري تحليل الفكرة وتوليد البرومبت الاحترافي..."})
            
            # 2. توليد البرومبت السحابي
            pro_script = await generate_pro_prompt(idea, style, mood)
            
            # 3. معالجة النصوص العربية وتجهيزها للمحرك
            for scene in pro_script.get("scenes", []):
                scene["fixed_arabic"] = fix_arabic_text(scene["arabic_narration"])

            await websocket.send_json({"step": 2, "msg": "🎨 تم بناء هندسة المشاهد والبرومبت بنجاح!"})

            # 4. إرسال النتيجة النهائية للواجهة لعرض البرومبت والفيديو
            await websocket.send_json({
                "step": 3,
                "msg": "✅ اكتمل التجهيز! البيانات جاهزة لأداة VIDEO-LIKE.",
                "generated_payload": pro_script
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"step": "error", "msg": f"حدث خطأ: {str(e)}"})
