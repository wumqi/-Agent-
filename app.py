"""
企业级智能客服与知识管理系统
主应用入口
"""

import os
import uuid
import streamlit as st
import traceback
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 设置页面配置
st.set_page_config(
    page_title="企业级智能客服与知识管理",
    page_icon="🤖",
    layout="wide"
)

# ====================
# 全局异常处理
# ====================
def handle_exception(func):
    """装饰器：全局异常处理"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"异常发生: {str(e)}")
            logger.error(traceback.format_exc())
            st.error(f"系统发生错误: {str(e)}")
            st.error("请刷新页面重试，如果问题持续存在，请联系管理员")
            return None
    return wrapper

# ====================
# 用户认证页面
# ====================
def render_auth_page():
    """渲染用户认证页面（登录/注册）"""
    from utils.session_manager import SessionManager, ConnectionPool
    from utils.user_manager import UserManager
    from utils.audit_logger import audit_logger
    
    # 初始化会话管理器
    if "session_manager" not in st.session_state:
        st.session_state["session_manager"] = SessionManager()
    
    # 初始化用户管理器
    if "user_manager" not in st.session_state:
        st.session_state["user_manager"] = UserManager(ConnectionPool)
    
    # 设置审计日志器
    audit_logger.set_session_manager(st.session_state["session_manager"])
    
    # 切换登录/注册模式
    auth_mode = st.session_state.get("auth_mode", "login")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 用户登录")
        
        # 模式切换按钮
        col_login, col_register = st.columns(2)
        with col_login:
            if st.button("登录", use_container_width=True, disabled=auth_mode == "login", key="btn_login_mode"):
                st.session_state["auth_mode"] = "login"
                st.rerun()
        with col_register:
            if st.button("注册", use_container_width=True, disabled=auth_mode == "register", key="btn_register_mode"):
                st.session_state["auth_mode"] = "register"
                st.rerun()
        
        st.divider()
        
        if auth_mode == "login":
            # 登录表单
            username = st.text_input("用户名", placeholder="请输入用户名", key="login_username")
            password = st.text_input("密码", type="password", placeholder="请输入密码", key="login_password")
            
            if st.button("登录", use_container_width=True, key="btn_login_submit"):
                if not username or not password:
                    st.error("请输入用户名和密码")
                else:
                    success, user_info = st.session_state["user_manager"].authenticate_user(username, password)
                    if success and user_info:
                        # 登录成功
                        st.session_state["current_user"] = user_info
                        st.session_state["logged_in"] = True
                        audit_logger.log_user_login(user_info["id"])
                        logger.info(f"用户登录成功: {username}")
                        st.success("登录成功，正在跳转...")
                        st.rerun()
                    else:
                        audit_logger.log_user_login(username, success=False, error_message="用户名或密码错误")
                        st.error("用户名或密码错误")
        
        else:
            # 注册表单
            username = st.text_input("用户名", placeholder="请输入用户名（至少 3 个字符）", key="register_username")
            password = st.text_input("密码", type="password", placeholder="请输入密码（至少 6 个字符，包含字母和数字）", key="register_password")
            password_confirm = st.text_input("确认密码", type="password", placeholder="请再次输入密码", key="register_password_confirm")
            email = st.text_input("邮箱（可选）", placeholder="请输入邮箱地址", key="register_email")
            
            if st.button("注册", use_container_width=True, key="btn_register_submit"):
                if not username or not password:
                    st.error("请输入用户名和密码")
                elif password != password_confirm:
                    st.error("两次输入的密码不一致")
                else:
                    success, user_id, error = st.session_state["user_manager"].create_user(username, password, email)
                    if success:
                        audit_logger.log_user_register(user_id)
                        logger.info(f"用户注册成功: {username}")
                        st.success("注册成功，请登录")
                        st.session_state["auth_mode"] = "login"
                        st.rerun()
                    else:
                        audit_logger.log_user_register(username, success=False, error_message=error)
                        st.error(error)

# ====================
# 初始化会话状态
# ====================
@handle_exception
def init_session_state():
    """初始化会话状态"""
    from utils.session_manager import SessionManager
    from utils.audit_logger import audit_logger
    
    if "session_manager" not in st.session_state:
        st.session_state["session_manager"] = SessionManager()
        audit_logger.set_session_manager(st.session_state["session_manager"])
    
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
    
    if "current_user" not in st.session_state:
        st.session_state["current_user"] = None
    
    if st.session_state.get("logged_in") and st.session_state.get("current_user"):
        user_id = st.session_state["current_user"]["id"]
        
        if "current_session_id" not in st.session_state:
            sessions = st.session_state["session_manager"].get_all_sessions(user_id)
            if sessions:
                st.session_state["current_session_id"] = sessions[0]["id"]
            else:
                st.session_state["current_session_id"] = None
        
        from agent.react_agent import ReactAgent
        from rag.vector_store import VectorStoreService
        
        if "agent" not in st.session_state:
            st.session_state["agent"] = ReactAgent()
        
        if "vector_store" not in st.session_state:
            st.session_state["vector_store"] = VectorStoreService()
        
        if "message_loaded" not in st.session_state:
            st.session_state["message_loaded"] = False
        
        if "message" not in st.session_state:
            st.session_state["message"] = []

# ====================
# 主应用逻辑
# ====================
def main():
    """主应用函数"""
    try:
        # 初始化会话状态
        init_session_state()
        
        # 检查用户是否登录
        if not st.session_state.get("logged_in") or not st.session_state.get("current_user"):
            render_auth_page()
            return
        
        # 导入组件（登录后才导入，避免初始化问题）
        from components.sidebar import render_sidebar
        from components.chat import render_chat_area
        
        # 渲染页面标题
        st.title("🤖 企业级智能客服与知识管理")
        st.divider()
        
        # 渲染侧边栏
        render_sidebar()
        
        # 渲染聊天区域
        render_chat_area()
        
    except Exception as e:
        logger.error(f"主应用异常: {str(e)}")
        logger.error(traceback.format_exc())
        st.error("系统发生严重错误，请刷新页面重试")
        st.error(f"错误信息: {str(e)}")

# ====================
# 应用入口
# ====================
if __name__ == "__main__":
    main()