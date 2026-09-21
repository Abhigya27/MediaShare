import os
import re
import streamlit as st
import requests
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="MediaShare", layout="wide")

# Backend base URL. Defaults to local dev; set API_BASE_URL in production
# (e.g. Render) to the deployed FastAPI service's URL.
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{3,32}$")

# Initialize session state
if 'token' not in st.session_state:
    st.session_state.token = None
if 'user' not in st.session_state:
    st.session_state.user = None
if 'feed_page' not in st.session_state:
    st.session_state.feed_page = 1

FEED_PAGE_SIZE = 10


def get_headers():
    """Get authorization headers with token"""
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}


def login_page():
    st.title("🚀 Welcome to MediaShare")

    username = st.text_input("Username:")
    password = st.text_input("Password:", type="password")

    if username and password:
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Login", type="primary", use_container_width=True):
                # Login using FastAPI Users JWT endpoint (username, not email)
                login_data = {"username": username, "password": password}
                response = requests.post(
                    f"{API_BASE_URL}/auth/jwt/login", data=login_data)

                if response.status_code == 200:
                    token_data = response.json()
                    st.session_state.token = token_data["access_token"]

                    # Get user info
                    user_response = requests.get(
                        f"{API_BASE_URL}/users/me", headers=get_headers())
                    if user_response.status_code == 200:
                        st.session_state.user = user_response.json()
                        st.rerun()
                    else:
                        st.error("Failed to get user info")
                else:
                    st.error("Invalid username or password!")

        with col2:
            if st.button("Sign Up", type="secondary", use_container_width=True):
                if not USERNAME_PATTERN.match(username):
                    st.error(
                        "Usernames must be 3-32 characters: letters, numbers, "
                        "and underscores only.")
                else:
                    # Register using FastAPI Users. fastapi-users requires an
                    # email internally, so we generate a hidden placeholder
                    # one from the username -- the user never sees or uses it.
                    signup_data = {
                        "email": f"{username}@users.mediashare.app",
                        "username": username,
                        "password": password,
                    }
                    response = requests.post(
                        f"{API_BASE_URL}/auth/register", json=signup_data)

                    if response.status_code == 201:
                        st.success("Account created! Click Login now.")
                    else:
                        error_detail = response.json().get("detail", "Registration failed")
                        if error_detail == "REGISTER_USER_ALREADY_EXISTS":
                            error_detail = "That username is already taken."
                        st.error(f"Registration failed: {error_detail}")
    else:
        st.info("Enter your username and password above")


def upload_page():
    st.title("📸 Share Something")

    uploaded_file = st.file_uploader(
        "Choose media", type=['png', 'jpg', 'jpeg', 'mp4', 'avi', 'mov', 'mkv', 'webm'])
    caption = st.text_area("Caption:", placeholder="What's on your mind?")

    if uploaded_file and st.button("Share", type="primary"):
        with st.spinner("Uploading..."):
            files = {"file": (uploaded_file.name,
                              uploaded_file.getvalue(), uploaded_file.type)}
            data = {"title": caption}
            response = requests.post(
                f"{API_BASE_URL}/post", files=files, data=data, headers=get_headers())

            if response.status_code == 201:
                st.success("Posted!")
                st.session_state.feed_page = 1
                st.rerun()
            elif response.status_code == 429:
                detail = response.json().get(
                    "detail", "You're posting too fast. Please slow down.")
                st.warning(detail)
            else:
                err = response.json().get(
                    "detail", "Upload failed") if response.content else "Upload failed"
                st.error(f"Upload failed: {err}")


def create_transformed_url(original_url, transformation_params):
    if not transformation_params:
        return original_url

    parts = original_url.split("/")
    file_path = "/".join(parts[4:])
    base_url = "/".join(parts[:4])
    return f"{base_url}/tr:{transformation_params}/{file_path}"


def feed_page():
    st.title("🏠 Feed")

    response = requests.get(
        f"{API_BASE_URL}/feed",
        params={"page": st.session_state.feed_page, "page_size": FEED_PAGE_SIZE},
        headers=get_headers())

    if response.status_code == 200:
        data = response.json()
        posts = data["posts"]
        total_pages = max(data.get("total_pages", 1), 1)

        if not posts and st.session_state.feed_page == 1:
            st.info("No posts yet! Be the first to share something.")
            return

        for post in posts:
            st.markdown("---")

            # Header with user, date, and delete button (if owner)
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{post['username']}** • {post['created_at'][:10]}")
            with col2:
                if post.get('is_owner', False):
                    if st.button("🗑️", key=f"delete_{post['id']}", help="Delete post"):
                        # Delete the post
                        response = requests.delete(
                            f"{API_BASE_URL}/posts/{post['id']}", headers=get_headers())
                        if response.status_code == 200:
                            st.success("Post deleted!")
                            st.rerun()
                        else:
                            st.error("Failed to delete post!")

            # Display media separately from its caption.
            caption = post.get('title', '')
            if post['file_type'] == 'image':
                uniform_url = create_transformed_url(post['url'], "")
                st.image(uniform_url, width=300)
            else:
                uniform_video_url = create_transformed_url(
                    post['url'], "w-400,h-200,cm-pad_resize,bg-blurred")
                st.video(uniform_video_url, width=300)
            if caption:
                st.caption(caption)

            st.markdown("")  # Space between posts

        # Pagination controls
        st.markdown("---")
        prev_col, mid_col, next_col = st.columns([1, 2, 1])
        with prev_col:
            if st.button("⬅️ Previous", disabled=st.session_state.feed_page <= 1,
                         use_container_width=True):
                st.session_state.feed_page -= 1
                st.rerun()
        with mid_col:
            st.markdown(
                f"<div style='text-align:center'>Page {st.session_state.feed_page} "
                f"of {total_pages}</div>", unsafe_allow_html=True)
        with next_col:
            if st.button("Next ➡️", disabled=st.session_state.feed_page >= total_pages,
                         use_container_width=True):
                st.session_state.feed_page += 1
                st.rerun()
    else:
        st.error("Failed to load feed")


# Main app logic
if st.session_state.user is None:
    login_page()
else:
    # Sidebar navigation
    st.sidebar.title(f"👋 Hi {st.session_state.user['username']}!")

    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.session_state.token = None
        st.session_state.feed_page = 1
        st.rerun()

    st.sidebar.markdown("---")
    page = st.sidebar.radio("Navigate:", ["🏠 Feed", "📸 Upload"])

    if page == "🏠 Feed":
        feed_page()
    else:
        upload_page()