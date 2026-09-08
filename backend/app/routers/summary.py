from fastapi import APIRouter
router = APIRouter()
@router.post("/stats")
def get_stats():
    return {"status": "scaffold_stub"}
