import streamlit as st
# Set page config must be the first Streamlit command
st.set_page_config(page_title="Magentic-One Interface", page_icon="🤖", layout="wide")

import asyncio
from magentic_one_helper import MagenticOneHelper
from datetime import datetime
import os
import uuid
import json
import re
import time
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
import openai
import shutil

# Get current directory and API key
current_dir = os.path.dirname(os.path.abspath(__file__))
api_key = os.getenv('OPENAI_API_KEY')

# Load API key from .env if not in environment
if not api_key:
    try:
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                content = f.read()
                for line in content.splitlines():
                    if line.startswith('OPENAI_API_KEY='):
                        api_key = line.split('=', 1)[1].strip()
                        # Handle both quoted and unquoted keys
                        if (api_key.startswith("'") and api_key.endswith("'")) or \
                           (api_key.startswith('"') and api_key.endswith('"')):
                            api_key = api_key[1:-1]
                        break
                
                # Add debug info to help diagnose
                with st.expander("🔍 API Key Debug", expanded=False):
                    st.write(f"Raw API key starts with: {api_key[:4] if api_key else 'None'}")
                    st.write(f"API key length: {len(api_key) if api_key else 0}")
    except Exception as e:
        st.error(f"Error loading API key: {str(e)}")
        st.stop()

if not api_key:
    st.error("OpenAI API key not found. Please set OPENAI_API_KEY environment variable or add it to .env file.")
    st.stop()

# Set the API key in environment variable (this is what magentic_one_helper.py expects)
os.environ['OPENAI_API_KEY'] = api_key

# Remove the openai.api_key setting since magentic_one_helper.py handles this
# openai.api_key = api_key  # Remove or comment out this line

@retry(
    retry=retry_if_exception_type(openai.RateLimitError),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5)
)
async def run_with_retry(func, *args, **kwargs):
    try:
        return await func(*args, **kwargs)
    except openai.RateLimitError as e:
        wait_time = float(str(e).split('Please try again in ')[1].split('s')[0])
        st.warning(f"Rate limit hit. Waiting {wait_time} seconds...")
        time.sleep(wait_time + 1)
        raise

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'current_chat_index' not in st.session_state:
    st.session_state.current_chat_index = None
if 'task_completed' not in st.session_state:
    st.session_state.task_completed = False
if 'viewing_files' not in st.session_state:
    st.session_state.viewing_files = False

# Initialize theme in session state
if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

# Add to your session state initialization
if 'clipboard' not in st.session_state:
    st.session_state.clipboard = None

def view_chat_files(folder_path):
    st.subheader("📁 Chat Files")
    files = os.listdir(folder_path)
    
    for file in files:
        file_path = os.path.join(folder_path, file)
        with st.expander(f"📄 {file}"):
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    st.code(content)
                # Add copy button
                if st.button("📋 Copy", key=f"copy_{file}"):
                    st.write("Content copied to clipboard!")
                    st.session_state['clipboard'] = content
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")

def display_url_preview(url):
    """Display a preview for URLs and images"""
    try:
        if url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            st.image(url, caption="Image Preview", use_column_width=True)
        else:
            # Create an iframe for web pages
            iframe_html = f"""
                <div style="border: 1px solid #ddd; padding: 5px; border-radius: 5px;">
                    <iframe src="{url}" width="100%" height="400" frameborder="0"></iframe>
                </div>
                """
            st.markdown(iframe_html, unsafe_allow_html=True)
    except Exception as e:
        st.warning(f"Could not load preview for: {url}")

# Function to toggle theme
def toggle_theme():
    st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'

# Header section with theme toggle
col1, col3 = st.columns([6, 3])
with col1:
    st.markdown("<h1 style='margin: 0;'>🤖 Magentic-One Interface</h1>", unsafe_allow_html=True)

with col3:
    # Choose emoji based on current theme
    icon = '🌞' if st.session_state.theme == 'dark' else '🌙'
    # Create the toggle button
    if st.button(icon, key='theme_toggle', help='Toggle Dark/Light Mode'):
        toggle_theme()
        st.rerun()

# Inject CSS based on the selected theme
dark_theme_css = """
<style>
    :root {
        --background: #1A2F1A;
        --text: #C5E1A5;
        --primary: #4CAF50;
        --secondary: #81C784;
        --accent: #A5D6A7;
        --card: rgba(46, 70, 46, 0.8);
        --hover: rgba(76, 175, 80, 0.1);
        --border: rgba(197, 225, 165, 0.2);
        --success: #66BB6A;
        --error: #EF5350;
        --info: #4CAF50;
        --warning: #FFB74D;
        --shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        --glass: rgba(46, 70, 46, 0.25);
    }
</style>
"""

light_theme_css = """
<style>
    :root {
        --background: #F1F8E9;
        --text: #33691E;
        --primary: #4CAF50;
        --secondary: #81C784;
        --accent: #C8E6C9;
        --card: rgba(255, 255, 255, 0.8);
        --hover: rgba(76, 175, 80, 0.05);
        --border: rgba(51, 105, 30, 0.1);
        --success: #66BB6A;
        --error: #EF5350;
        --info: #4CAF50;
        --warning: #FFB74D;
        --shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        --glass: rgba(255, 255, 255, 0.25);
    }
</style>
"""

# Apply the appropriate CSS based on the current theme
if st.session_state.theme == 'dark':
    st.markdown(dark_theme_css, unsafe_allow_html=True)
else:
    st.markdown(light_theme_css, unsafe_allow_html=True)

# Load CSS
current_dir = os.path.dirname(os.path.abspath(__file__))
css_file = os.path.join(current_dir, "style.css")
if os.path.exists(css_file):
    with open(css_file) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Task templates
TASK_TEMPLATES = {
    "Custom Task": "",
    "Web Research": "Search and summarize information about [topic]",
    "Code Analysis": "Analyze the code in [repository/file] and provide insights",
    "Data Processing": "Process the data in [file] and generate a report",
    "System Command": "Execute and explain the results of [command]",
    "Content Creation": "Generate a [type] for [purpose]",
    "SEO Optimization": "Improve the SEO for [website/page]",
    "Market Analysis": "Analyze market trends for [industry/product/company]",
    "Customer Feedback": "Summarize and categorize customer feedback from [source]",
    "Financial Analysis": "Perform a financial analysis on [company/stock]"
}

def reset_chat():
    st.session_state.current_chat_index = None
    st.session_state.task_completed = False

def format_agent_message(source, message):
    """Format agent messages with consistent styling"""
    icons = {
        "Orchestrator": "🎯",
        "WebSurfer": "🌐",
        "FileSurfer": "📁",
        "Coder": "💻",
        "ComputerTerminal": "⌨️"
    }
    icon = icons.get(source.split()[0], "🤖")
    
    # Check if message contains URLs
    urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message)
    
    formatted_message = f"""
    <div class="agent-message">
        <div style="font-weight: bold; margin-bottom: 0.5rem;">
            {icon} {source}
        </div>
        <div style="white-space: pre-wrap; line-height: 1.5;">
            {message}
        </div>
    </div>
    """
    
    return formatted_message, urls

# Main layout
try:
    with col3:
        st.markdown("<div class='intro-panel'><h3>👥 Introduction to the Team</h3>", unsafe_allow_html=True)
        team = {
            "Orchestrator": "Coordinates tasks",
            "WebSurfer": "Finds web info",
            "FileSurfer": "Manages files",
            "Coder": "Writes code",
            "DataAnalyzer": "Processes data"
        }
        for agent, description in team.items():
            st.markdown(f"- **{agent}**: {description}")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # Columns layout
    left_col, main_col = st.columns([1.5, 4])

    # Left Panel
    with left_col:
        # Define logs_dir for file operations
        logs_dir = os.path.join(current_dir, "my_logs")
        os.makedirs(logs_dir, exist_ok=True)
        
        # Load existing chats if session state is empty
        if not st.session_state.chat_history:
            for folder_name in os.listdir(logs_dir):
                folder_path = os.path.join(logs_dir, folder_name)
                if os.path.isdir(folder_path):
                    log_file = os.path.join(folder_path, "log.jsonl")
                    if os.path.exists(log_file):
                        # Parse the folder name to get timestamp and task
                        parts = folder_name.split('_', 2)  # Split into date, uuid, task
                        if len(parts) >= 3:
                            timestamp = datetime.strptime(parts[0], '%Y%m%d').strftime("%Y-%m-%d %H:%M:%S")
                            task = parts[2].replace('-', ' ').capitalize()
                            
                            # Load logs
                            logs = []
                            try:
                                with open(log_file, 'r') as f:
                                    for line in f:
                                        try:
                                            log_entry = json.loads(line.strip())
                                            logs.append(log_entry)
                                        except json.JSONDecodeError:
                                            continue
                            except Exception as e:
                                st.error(f"Error loading logs for {folder_name}: {str(e)}")
                                continue
                            
                            # Get final answer from the last relevant log entry
                            final_answer = None
                            for log in reversed(logs):
                                if log.get('source') == 'Orchestrator' and 'Final Answer:' in log.get('message', ''):
                                    final_answer = log['message'].split('Final Answer:', 1)[1].strip()
                                    break
                            
                            chat_entry = {
                                'task': task,
                                'timestamp': timestamp,
                                'logs': logs,
                                'final_answer': final_answer,
                                'folder': folder_name
                            }
                            st.session_state.chat_history.append(chat_entry)
            
            # Sort chats by timestamp (newest first)
            st.session_state.chat_history.sort(key=lambda x: x['timestamp'], reverse=True)

        # Chat History Header
        st.markdown("""
            <div class="left-panel">
                <div class="panel-header">
                    <h3>💬 Chat History</h3>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # New Chat Button
        if st.button("➕ New Chat", key="new_chat", 
                    help="Start a new chat"):
            reset_chat()

        # Search Box
        search_query = st.text_input("🔍", 
                                   placeholder="Search chats...",
                                   label_visibility="collapsed",
                                   key="search_chats")

        # Chat List Container
        st.markdown('<div class="chat-list-container">', unsafe_allow_html=True)
        
        # Add handle_menu_actions function
        def handle_menu_actions(idx, chat, logs_dir):
            menu_col1, menu_col2, menu_col3 = st.columns(3)
            with menu_col1:
                if st.button("📤 Share", key=f"share_{idx}"):
                    share_text = f"Task: {chat['task']}\nTimestamp: {chat['timestamp']}\n\n"
                    if chat.get('final_answer'):
                        share_text += f"Final Answer: {chat['final_answer']}\n"
                    st.session_state['clipboard'] = share_text
                    st.success("Copied to clipboard!")
            
            with menu_col2:
                if st.button("📁 Files", key=f"files_{idx}"):
                    st.session_state['viewing_files'] = True
                    st.session_state['viewing_folder'] = os.path.join(logs_dir, chat['folder'])
                    st.rerun()
            
            with menu_col3:
                if st.button("🗑️ Delete", key=f"delete_{idx}"):
                    folder_path = os.path.join(logs_dir, chat['folder'])
                    try:
                        # Delete the folder and its contents
                        shutil.rmtree(folder_path)
                        # Remove the chat from session state history
                        st.session_state.chat_history.pop(idx)
                        # Reset current chat index if we're deleting the currently selected chat
                        if st.session_state.current_chat_index == idx:
                            st.session_state.current_chat_index = None
                            st.session_state.task_completed = False
                        # Adjust current_chat_index if we're deleting a chat before it
                        elif st.session_state.current_chat_index and st.session_state.current_chat_index > idx:
                            st.session_state.current_chat_index -= 1
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting chat: {str(e)}")

        for idx, chat in enumerate(st.session_state.chat_history):
            if search_query.lower() in chat['task'].lower():
                chat_container = st.container()
                
                with chat_container:
                    col1, col2 = st.columns([0.85, 0.15])
                    
                    with col1:
                        # Add custom class to button
                        button_label = f"💭 {chat['task']} - {chat['timestamp'].split()[0]}"
                        if st.button(button_label, 
                                   key=f"chat_btn_{idx}", 
                                   help="Select this chat",
                                   use_container_width=True,
                                   # Add custom CSS class
                                   kwargs={"class": "chat-item-button"}):
                            st.session_state.current_chat_index = idx
                            st.session_state.task_completed = True
                            st.rerun()
                    
                    with col2:
                        if st.button("⋮", key=f"menu_btn_{idx}", help="Open menu"):
                            st.session_state[f'show_menu_{idx}'] = not st.session_state.get(f'show_menu_{idx}', False)
                    
                    # Show menu if activated
                    if st.session_state.get(f'show_menu_{idx}', False):
                        st.markdown('<div class="chat-menu">', unsafe_allow_html=True)
                        handle_menu_actions(idx, chat, logs_dir)
                        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

    # Main Content
    with main_col:
        if st.session_state.current_chat_index is None:
            # Task input
            st.subheader("🚀 Start a New Task")
            template_type = st.selectbox("Choose a task template:", list(TASK_TEMPLATES.keys()), key="template_selector", index=0)
            task_placeholder = TASK_TEMPLATES[template_type]
            task = st.text_input("Describe your task:", value=task_placeholder if task_placeholder else "", key="task_input")
            if st.button("Run Task", key="run_task", disabled=not task.strip()):
                # Create a folder name using timestamp, UUID and truncated task
                folder_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}_{task.strip().lower()[:20]}"
                chat_folder = folder_name  # Use folder name instead of full path
                full_chat_folder = os.path.join(logs_dir, chat_folder)
                os.makedirs(full_chat_folder, exist_ok=True)

                new_chat = {
                    'task': task,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'logs': [],
                    'final_answer': None,
                    'folder': folder_name
                }
                st.session_state.chat_history.append(new_chat)
                st.session_state.current_chat_index = len(st.session_state.chat_history) - 1
                st.session_state.task_completed = False
                st.rerun()
        else:
            # Display selected chat
            chat = st.session_state.chat_history[st.session_state.current_chat_index]
            st.subheader(f"📜 Task: {chat['task']}")
            st.write(f"🕒 {chat['timestamp']}")
            st.markdown("---")

            # Status containers
            status_container = st.empty()
            agent_container = st.container()
            result_container = st.empty()

            if not st.session_state.task_completed:
                async def run_magentic_one():
                    try:
                        status_container.info("Initializing Magentic-One...")
                        # Create full path for the chat folder
                        chat_logs_dir = os.path.join(current_dir, "my_logs", chat['folder'])
                        magnetic_one = MagenticOneHelper(logs_dir=chat_logs_dir)
                        await magnetic_one.initialize()

                        task_future = asyncio.create_task(
                            run_with_retry(magnetic_one.run_task, chat['task'])
                        )

                        async for log_entry in magnetic_one.stream_logs():
                            chat['logs'].append(log_entry)
                            # Save log entry to file with error handling
                            try:
                                with open(os.path.join(current_dir, "my_logs", chat['folder'], "log.jsonl"), "a") as log_file:
                                    json_str = json.dumps(log_entry)
                                    log_file.write(json_str + "\n")
                            except json.JSONDecodeError as e:
                                st.error(f"Error writing log entry: {str(e)}")
                                continue
                            except Exception as e:
                                st.error(f"Error saving log: {str(e)}")
                                continue

                            if "source" in log_entry and "message" in log_entry:
                                source = log_entry["source"]
                                message = log_entry["message"]

                                with agent_container:
                                    formatted_message, urls = format_agent_message(source, message)
                                    st.markdown(formatted_message, unsafe_allow_html=True)
                                    for url in urls:
                                        display_url_preview(url)

                        await task_future

                        final_answer = magnetic_one.get_final_answer()
                        if final_answer:
                            st.success(f"**Final Answer:**\n{final_answer}")
                            chat['final_answer'] = final_answer
                        else:
                            st.error("No final answer found.")

                        st.session_state.task_completed = True
                        status_container.empty()

                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}")
                        status_container.empty()

                asyncio.run(run_magentic_one())
            else:
                # Display chat history
                for log_entry in chat['logs']:
                    if "source" in log_entry and "message" in log_entry:
                        source = log_entry["source"]
                        message = log_entry["message"]
                        formatted_message, urls = format_agent_message(source, message)
                        st.markdown(formatted_message, unsafe_allow_html=True)
                        for url in urls:
                            display_url_preview(url)
                if chat['final_answer']:
                    st.success(f"**Final Answer:**\n{chat['final_answer']}")

            if st.button("🔄 Restart Task", key="restart_task"):
                reset_chat()
                st.rerun()

except Exception as e:
    st.error(f"An unexpected error occurred: {str(e)}")