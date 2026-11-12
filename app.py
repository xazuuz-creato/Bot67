import os
import json
import httpx
import arabic_reshaper
from bidi.algorithm import get_display
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="VIDEO-LIKE Arabic Studio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

class VideoRequest(BaseModel):
    idea: str
    style: str
    mood: str

def fix_arabic_text(text: str) -> str:
    """تصحيح النصوص العربية وضبط اتجاهها من اليمين لليسار (RTL)"""
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception:
        return text

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """عرض الواجهة الفخمة مباشرة"""
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse("<h1>ملف index.html غير موجود</h1>")

@app.post("/api/generate")
async def generate_studio_content(req: VideoRequest):
    """نقطة الاتصال الحقيقية لتوليد السكربت والبرومبت الاحترافي عبر Gemini"""
    if not req.idea.strip():
        return JSONResponse(status_code=400, content={"error": "يرجى كتابة فكرة الفيديو أولاً."})

    if not GEMINI_API_KEY:
        return JSONResponse(status_code=500, content={"error": "مفتاح GEMINI_API_KEY غير مضاف في إعدادات Render."})

    system_instruction = f"""
    أنت مخرج سينمائي ومهندس برومبت محترف لأداة VIDEO-LIKE.
    حول فكرة المستخدم إلى 3 مشاهد متسلسلة وجذابة لفيديو قصير.
    النمط التصميمي المطلوب: {req.style}
    الإيقاع والمزاج: {req.mood}

    أخرج النتيجة بصيغة JSON فقط بدون أي نص إضافي خارج القوسين، وبنفس هذا الهيكل الدقيق:
    {{
        "scenes": [
            {{
                "scene_number": 1,
                "arabic_narration": "التعليق الصوتي العربي المشوق للمشهد الأول",
                "visual_prompt_en": "Detailed cinematic visual prompt in English describing the scene, camera angle, lighting, and motion for VIDEO-LIKE AI",
                "transition": "نوع الانتقال المقترح"
            }}
        ]
    }}
    """

    url = f"https://googleapis.com{GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": f"{system_instruction}\n\nفكرة الفيديو: {req.idea}"}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.7
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code != 200:
                return JSONResponse(status_code=response.status_code, content={"error": f"خطأ من خادم جوجل: {response.text}"})

            data = response.json()
            # المسار الصحيح لاستخراج النص من استجابة Gemini
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed_data = json.loads(raw_text)

            # معالجة النصوص العربية لكل مشهد
            for scene in parsed_data.get("scenes", []):
                scene["fixed_arabic"] = fix_arabic_text(scene.get("arabic_narration", ""))

            return {"status": "success", "data": parsed_data}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"حدث خطأ أثناء المعالجة: {str(e)}"})
