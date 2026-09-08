from fastapi import APIRouter
router = APIRouter()
@router.post("/custom")
def custom():
    return {"status": "scaffold_stub"}
