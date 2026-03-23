import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

async def save_video(user_id: str, topic: str, format: str, type: str, video_url: str, title: str = ""):
    """Üretilen videoyu Supabase'e kaydeder"""
    try:
        db = get_supabase()
        db.table("videos").insert({
            "user_id": user_id,
            "topic": topic,
            "title": title,
            "format": format,
            "type": type,
            "video_url": video_url,
        }).execute()
        print(f"[DEBUG] Video saved to Supabase for user {user_id}")

        # Kullanıcının video sayısını artır
        db.rpc("increment_video_count", {"user_id_input": user_id}).execute()
    except Exception as e:
        print(f"[WARN] Could not save video to Supabase: {e}")

async def check_video_limit(user_id: str, use_video: bool = False) -> dict:
    """Kullanıcının video limitini kontrol eder"""
    try:
        db = get_supabase()
        result = db.table("user_profiles").select("plan, videos_used_this_month").eq("id", user_id).single().execute()
        profile = result.data

        plan = profile.get("plan", "free")
        used = profile.get("videos_used_this_month", 0)

        limits = {
            "free": {"image_slides": 1, "video_clips": 0},
            "starter": {"image_slides": 5, "video_clips": 0},
            "pro": {"image_slides": 8, "video_clips": 3},
        }

        plan_limits = limits.get(plan, limits["free"])

        if use_video:
            limit = plan_limits["video_clips"]
        else:
            limit = plan_limits["image_slides"]

        if limit == 0:
            return {"allowed": False, "reason": f"Video Clips not available on {plan} plan. Upgrade to Pro."}

        if used >= (plan_limits["image_slides"] + plan_limits["video_clips"]):
            return {"allowed": False, "reason": f"Monthly video limit reached. Upgrade your plan."}

        return {"allowed": True, "plan": plan, "used": used}
    except Exception as e:
        print(f"[WARN] Could not check limit: {e}")
        return {"allowed": True}
