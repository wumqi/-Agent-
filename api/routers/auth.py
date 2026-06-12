"""
认证路由
"""
from fastapi import APIRouter, HTTPException, status
from api.schemas.auth import TokenRequest, TokenResponse
from api.middleware.auth import create_access_token, verify_password
from utils.user_manager import UserManager

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/token", response_model=TokenResponse)
async def login(form_data: TokenRequest):
    """用户登录获取 Token"""
    # 验证用户
    user_manager = UserManager()
    user = user_manager.authenticate_user(form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 创建 Token
    access_token = create_access_token(
        data={"sub": user["id"], "username": user["username"]}
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=3600
    )
