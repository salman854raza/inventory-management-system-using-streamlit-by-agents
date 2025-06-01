import streamlit as st
from PIL import Image
import time
import threading
import json
import os
from datetime import datetime
from main import EmailAgent, InventoryManager, InventorySystem, WhatsAppAgent  # Assuming your code is in inventory_system.py

# Set page config
st.set_page_config(
    page_title="AI Inventory Management",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Password protection configuration
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")  # Change this to a strong password or set via environment variable

# Custom CSS for styling
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("style.css")  # You can create a style.css file for additional styling

# Initialize the inventory system
if 'system' not in st.session_state:
    st.session_state.system = InventorySystem()
    st.session_state.running = True

# Password protection function
def check_password():
    """Returns True if the user had the correct password or has already authenticated."""
    
    if st.session_state.get("password_correct", False):
        return True
    
    password = st.text_input("Enter admin password:", type="password", key="password_input")
    
    if st.button("Authenticate"):
        if password == ADMIN_PASSWORD:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Incorrect password. Please try again.")
    
    return False

# Sidebar for navigation
with st.sidebar:
    st.title("📦 AI Inventory Management")
    st.markdown("""
    **Three Autonomous Agents:**
    1. 🤖 Inventory Manager
    2. 📱 WhatsApp Agent
    3. ✉️ Email Agent
    """)

    selected_tab = st.radio(
        "Navigation",
        ["Dashboard", "Inventory", "Agents Activity", "Settings"],
        index=0
    )

    st.markdown("---")
    st.markdown("### System Status")

    # System status indicator
    status_placeholder = st.empty()
    if st.session_state.running:
        status_placeholder.success("✅ System Running")
    else:
        status_placeholder.warning("⚠️ System Paused")

    if st.button("🔄 Restart System"):
        st.session_state.system.shutdown()
        st.session_state.system = InventorySystem()
        st.session_state.running = True
        st.rerun()

    if st.session_state.running:
        if st.button("⏸️ Pause System"):
            st.session_state.system.inventory_manager.stop()
            st.session_state.running = False
            st.rerun()
    else:
        if st.button("▶️ Resume System"):
            st.session_state.system.inventory_manager = InventoryManager(
                st.session_state.system.db,
                st.session_state.system.whatsapp_agent,
                st.session_state.system.email_agent
            )
            st.session_state.running = True
            st.rerun()

# Dashboard Tab
if selected_tab == "Dashboard":
    st.title("📊 Inventory Dashboard")

    # Stats columns
    status = st.session_state.system.db.get_inventory_status()
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Products", status['total_products'])

    with col2:
        st.metric("Out of Stock", status['out_of_stock'], delta_color="inverse")

    with col3:
        st.metric("Low Stock", status['low_stock'], delta_color="off")

    with col4:
        st.metric("Total Value", f"${status['total_value']:,.2f}")

    st.markdown("---")

    # Recent activity
    st.subheader("📝 Recent Activities")
    activities = st.session_state.system.db.get_recent_activities(10)

    for activity in activities:
        with st.expander(f"{activity['timestamp']} - {activity['agent']}: {activity['action']}"):
            st.write(activity['details'])
            if "error" in activity['action'].lower():
                st.error("This action encountered an error")
            elif "alert" in activity['action'].lower():
                st.warning("This is an alert notification")

    # Quick actions
    st.markdown("---")
    st.subheader("⚡ Quick Actions")
    action_col1, action_col2, action_col3 = st.columns(3)

    with action_col1:
        if st.button("📱 Get WhatsApp Update"):
            st.session_state.system.whatsapp_agent.notify_activity()
            st.toast("WhatsApp notification sent!")

    with action_col2:
        if st.button("📧 Send Email Report"):
            if st.session_state.system.email_agent.send_daily_report():
                st.toast("Email report sent successfully!")
            else:
                st.error("Failed to send email report")

    with action_col3:
        if st.button("🤖 Get AI Suggestions"):
            st.session_state.system.whatsapp_agent.suggest_actions()
            st.toast("AI suggestions sent to WhatsApp!")

# Inventory Tab
elif selected_tab == "Inventory":
    st.title("🛍️ Inventory Management")

    tab1, tab2 = st.tabs(["View Inventory", "Manage Products"])

    with tab1:
        st.subheader("Current Inventory")

        # Search and filter
        search_col1, search_col2 = st.columns(2)
        with search_col1:
            search_term = st.text_input("Search products")

        with search_col2:
            filter_category = st.selectbox(
                "Filter by category",
                ["All"] + list(set(p['category'] for p in st.session_state.system.db.inventory.values() if p['category']))
            )

        # Display inventory table
        inventory_data = []
        for product_id, product in st.session_state.system.db.inventory.items():
            if (not search_term or search_term.lower() in product['name'].lower()) and \
               (filter_category == "All" or product['category'] == filter_category):
                inventory_data.append({
                    "ID": product_id,
                    "Name": product['name'],
                    "Category": product['category'],
                    "Quantity": product['quantity'],
                    "Price": f"${product['price']:.2f}",
                    "Last Updated": product['last_updated'],
                    "Status": "❌ Out of Stock" if product['quantity'] <= 0 else \
                             "⚠️ Low Stock" if product['quantity'] < 10 else \
                             "✅ In Stock"
                })

        st.dataframe(
            inventory_data,
            column_config={
                "Status": st.column_config.TextColumn(
                    "Status",
                    help="Inventory status",
                    width="small"
                )
            },
            hide_index=True,
            use_container_width=True
        )

    with tab2:
        st.subheader("Add/Update Products")

        with st.form("product_form"):
            col1, col2 = st.columns(2)

            with col1:
                product_id = st.text_input("Product ID", placeholder="P001")
                product_name = st.text_input("Product Name", placeholder="Wireless Mouse")
                product_category = st.text_input("Category", placeholder="Electronics")

            with col2:
                product_quantity = st.number_input("Quantity", min_value=0, step=1)
                product_price = st.number_input("Price", min_value=0.0, step=0.01, format="%.2f")

            submitted = st.form_submit_button("Save Product")

            if submitted:
                if product_id in st.session_state.system.db.inventory:
                    # Update existing product
                    st.session_state.system.db.inventory[product_id]['name'] = product_name
                    st.session_state.system.db.inventory[product_id]['category'] = product_category
                    st.session_state.system.db.inventory[product_id]['quantity'] = product_quantity
                    st.session_state.system.db.inventory[product_id]['price'] = product_price
                    st.session_state.system.db.inventory[product_id]['last_updated'] = str(datetime.now())

                    activity = {
                        'timestamp': str(datetime.now()),
                        'agent': 'Streamlit UI',
                        'action': 'update_product',
                        'details': f"Updated {product_name} (ID: {product_id})"
                    }
                    st.session_state.system.db.activity_log.append(activity)
                    st.session_state.system.db.save_data()

                    st.toast(f"Product {product_id} updated successfully!")
                else:
                    # Add new product
                    if st.session_state.system.db.add_product(
                        product_id, product_name, product_quantity, product_price, product_category
                    ):
                        st.toast(f"Product {product_id} added successfully!")
                    else:
                        st.error(f"Product {product_id} already exists!")

        st.markdown("---")
        st.subheader("Quick Actions")

        col1, col2 = st.columns(2)

        with col1:
            with st.form("sell_form"):
                sell_product_id = st.selectbox(
                    "Product to Sell",
                    list(st.session_state.system.db.inventory.keys()),
                    format_func=lambda x: f"{x} - {st.session_state.system.db.inventory[x]['name']}"
                )
                sell_quantity = st.number_input("Quantity", min_value=1, step=1)

                if st.form_submit_button("Sell Product"):
                    if st.session_state.system.db.sell_product(sell_product_id, sell_quantity):
                        st.toast(f"Sold {sell_quantity} of {sell_product_id}")
                    else:
                        st.error("Failed to sell product - check quantity")

        with col2:
            with st.form("update_form"):
                update_product_id = st.selectbox(
                    "Product to Update",
                    list(st.session_state.system.db.inventory.keys()),
                    format_func=lambda x: f"{x} - {st.session_state.system.db.inventory[x]['name']}",
                    key="update_select"
                )
                quantity_change = st.number_input("Quantity Change", step=1)

                if st.form_submit_button("Update Quantity"):
                    if st.session_state.system.db.update_quantity(update_product_id, quantity_change):
                        st.toast(f"Updated {update_product_id} by {quantity_change}")
                    else:
                        st.error("Failed to update quantity")

# Agents Activity Tab
elif selected_tab == "Agents Activity":
    st.title("🤖 Agents Activity Monitor")

    st.subheader("Agent Status")
    status_col1, status_col2, status_col3 = st.columns(3)

    with status_col1:
        st.markdown("### 🤖 Inventory Manager")
        st.markdown("""
        - Monitors stock levels
        - Generates alerts
        - Runs continuously
        """)
        st.progress(100, text="Running")

    with status_col2:
        st.markdown("### 📱 WhatsApp Agent")
        st.markdown("""
        - Sends notifications
        - Provides AI suggestions
        - Responds to queries
        """)
        st.progress(100, text="Running")

    with status_col3:
        st.markdown("### ✉️ Email Agent")
        st.markdown("""
        - Sends daily reports
        - Provides CSV exports
        - Sends alerts
        """)
        st.progress(100, text="Running")

    st.markdown("---")

    st.subheader("Agent Communication Log")

    # Filter options
    col1, col2, col3 = st.columns(3)
    with col1:
        agent_filter = st.selectbox("Filter by Agent", ["All", "InventoryManager", "WhatsApp Agent", "Email Agent"])

    with col2:
        action_filter = st.selectbox("Filter by Action", ["All", "notification", "alert", "error"])

    with col3:
        time_filter = st.selectbox("Time Range", ["Last 24 hours", "Last week", "Last month", "All time"])

    # Filter activities
    filtered_activities = st.session_state.system.db.activity_log.copy()

    if agent_filter != "All":
        filtered_activities = [a for a in filtered_activities if a['agent'] == agent_filter]

    if action_filter != "All":
        filtered_activities = [a for a in filtered_activities if action_filter in a['action'].lower()]

    # Display filtered activities
    for activity in reversed(filtered_activities):
        with st.container(border=True):
            cols = st.columns([1, 4])
            with cols[0]:
                if "whatsapp" in activity['agent'].lower():
                    st.markdown("📱")
                elif "email" in activity['agent'].lower():
                    st.markdown("✉️")
                else:
                    st.markdown("🤖")

                st.markdown(f"**{activity['agent']}**")
                st.caption(activity['timestamp'])

            with cols[1]:
                st.markdown(f"**{activity['action']}**")
                st.write(activity['details'])

                if "error" in activity['action'].lower():
                    st.error("This action encountered an error")
                elif "alert" in activity['action'].lower():
                    st.warning("This is an alert notification")

# Settings Tab
elif selected_tab == "Settings":
    st.title("⚙️ System Settings")
    
    # Password protection for settings
    if not check_password():
        st.stop()  # Don't show settings until authenticated
    
    st.subheader("Agent Configuration")

    with st.expander("📱 WhatsApp Settings", expanded=False):
        st.markdown("Configure WhatsApp notifications")
        twilio_account_sid = st.text_input("Twilio Account SID", value=os.getenv('TWILIO_ACCOUNT_SID', ''))
        twilio_auth_token = st.text_input("Twilio Auth Token", value=os.getenv('TWILIO_AUTH_TOKEN', ''), type="password")
        twilio_whatsapp_number = st.text_input("Twilio WhatsApp Number", value=os.getenv('TWILIO_WHATSAPP_NUMBER', ''))
        recipient_whatsapp_number = st.text_input("Recipient WhatsApp Number", value=os.getenv('RECIPIENT_WHATSAPP_NUMBER', ''))

        if st.button("Save WhatsApp Settings"):
            os.environ['TWILIO_ACCOUNT_SID'] = twilio_account_sid
            os.environ['TWILIO_AUTH_TOKEN'] = twilio_auth_token
            os.environ['TWILIO_WHATSAPP_NUMBER'] = twilio_whatsapp_number
            os.environ['RECIPIENT_WHATSAPP_NUMBER'] = recipient_whatsapp_number
            st.session_state.system.whatsapp_agent = WhatsAppAgent(st.session_state.system.db)
            st.toast("WhatsApp settings updated!")

    with st.expander("✉️ Email Settings", expanded=False):
        st.markdown("Configure email notifications")
        smtp_server = st.text_input("SMTP Server", value=os.getenv('SMTP_SERVER', 'smtp.gmail.com'))
        smtp_port = st.number_input("SMTP Port", value=int(os.getenv('SMTP_PORT', 587)))
        smtp_email = st.text_input("SMTP Email", value=os.getenv('SMTP_EMAIL', ''))
        smtp_password = st.text_input("SMTP Password", value=os.getenv('SMTP_PASSWORD', ''), type="password")
        recipient_email = st.text_input("Recipient Email", value=os.getenv('RECIPIENT_EMAIL', ''))

        if st.button("Save Email Settings"):
            os.environ['SMTP_SERVER'] = smtp_server
            os.environ['SMTP_PORT'] = str(smtp_port)
            os.environ['SMTP_EMAIL'] = smtp_email
            os.environ['SMTP_PASSWORD'] = smtp_password
            os.environ['RECIPIENT_EMAIL'] = recipient_email
            st.session_state.system.email_agent = EmailAgent(st.session_state.system.db)
            st.toast("Email settings updated!")

    with st.expander("🔄 System Maintenance", expanded=False):
        st.warning("These actions will affect the running system")

        if st.button("🔄 Reset Inventory Database"):
            st.session_state.system.db.inventory = {}
            st.session_state.system.db.activity_log = []
            st.session_state.system.db.save_data()
            st.toast("Inventory database reset!")

        if st.button("🧹 Clear Activity Log"):
            st.session_state.system.db.activity_log = []
            st.session_state.system.db.save_data()
            st.toast("Activity log cleared!")

        if st.button("📤 Export Database"):
            with open("inventory_export.json", "w") as f:
                json.dump({
                    "inventory": st.session_state.system.db.inventory,
                    "activity_log": st.session_state.system.db.activity_log
                }, f)

            with open("inventory_export.json", "rb") as f:
                st.download_button(
                    label="Download Export",
                    data=f,
                    file_name="inventory_export.json",
                    mime="application/json"
                )

# Real-time updates
def update_dashboard():
    while True:
        if st.session_state.running:
            status = st.session_state.system.db.get_inventory_status()

            # Update metrics (this would need Streamlit's experimental features)
            # For now, we'll just sleep
            time.sleep(5)
        else:
            time.sleep(1)

# Start the update thread
if 'update_thread' not in st.session_state:
    st.session_state.update_thread = threading.Thread(target=update_dashboard, daemon=True)
    st.session_state.update_thread.start() streamlit as st
# from PIL import Image
# import time
# import threading
# import json
# import os
# from datetime import datetime
# from main import EmailAgent, InventoryManager, InventorySystem, WhatsAppAgent  # Assuming your code is in inventory_system.py

# Set page config
st.set_page_config(
    page_title="AI Inventory Management",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("style.css")  # You can create a style.css file for additional styling

# Initialize the inventory system
if 'system' not in st.session_state:
    st.session_state.system = InventorySystem()
    st.session_state.running = True

# Sidebar for navigation
with st.sidebar:
    st.title("📦 AI Inventory Management")
    st.markdown("""
    **Three Autonomous Agents:**
    1. 🤖 Inventory Manager
    2. 📱 WhatsApp Agent
    3. ✉️ Email Agent
    """)
    
    selected_tab = st.radio(
        "Navigation",
        ["Dashboard", "Inventory", "Agents Activity", "Settings"],
        index=0
    )
    
    st.markdown("---")
    st.markdown("### System Status")
    
    # System status indicator
    status_placeholder = st.empty()
    if st.session_state.running:
        status_placeholder.success("✅ System Running")
    else:
        status_placeholder.warning("⚠️ System Paused")
    
    if st.button("🔄 Restart System"):
        st.session_state.system.shutdown()
        st.session_state.system = InventorySystem()
        st.session_state.running = True
        st.rerun()
    
    if st.session_state.running:
        if st.button("⏸️ Pause System"):
            st.session_state.system.inventory_manager.stop()
            st.session_state.running = False
            st.rerun()
    else:
        if st.button("▶️ Resume System"):
            st.session_state.system.inventory_manager = InventoryManager(
                st.session_state.system.db,
                st.session_state.system.whatsapp_agent,
                st.session_state.system.email_agent
            )
            st.session_state.running = True
            st.rerun()

# Dashboard Tab
if selected_tab == "Dashboard":
    st.title("📊 Inventory Dashboard")
    
    # Stats columns
    status = st.session_state.system.db.get_inventory_status()
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Products", status['total_products'])
    
    with col2:
        st.metric("Out of Stock", status['out_of_stock'], delta_color="inverse")
    
    with col3:
        st.metric("Low Stock", status['low_stock'], delta_color="off")
    
    with col4:
        st.metric("Total Value", f"${status['total_value']:,.2f}")
    
    st.markdown("---")
    
    # Recent activity
    st.subheader("📝 Recent Activities")
    activities = st.session_state.system.db.get_recent_activities(10)
    
    for activity in activities:
        with st.expander(f"{activity['timestamp']} - {activity['agent']}: {activity['action']}"):
            st.write(activity['details'])
            if "error" in activity['action'].lower():
                st.error("This action encountered an error")
            elif "alert" in activity['action'].lower():
                st.warning("This is an alert notification")
    
    # Quick actions
    st.markdown("---")
    st.subheader("⚡ Quick Actions")
    action_col1, action_col2, action_col3 = st.columns(3)
    
    with action_col1:
        if st.button("📱 Get WhatsApp Update"):
            st.session_state.system.whatsapp_agent.notify_activity()
            st.toast("WhatsApp notification sent!")
    
    with action_col2:
        if st.button("📧 Send Email Report"):
            if st.session_state.system.email_agent.send_daily_report():
                st.toast("Email report sent successfully!")
            else:
                st.error("Failed to send email report")
    
    with action_col3:
        if st.button("🤖 Get AI Suggestions"):
            st.session_state.system.whatsapp_agent.suggest_actions()
            st.toast("AI suggestions sent to WhatsApp!")

# Inventory Tab
elif selected_tab == "Inventory":
    st.title("🛍️ Inventory Management")
    
    tab1, tab2 = st.tabs(["View Inventory", "Manage Products"])
    
    with tab1:
        st.subheader("Current Inventory")
        
        # Search and filter
        search_col1, search_col2 = st.columns(2)
        with search_col1:
            search_term = st.text_input("Search products")
        
        with search_col2:
            filter_category = st.selectbox(
                "Filter by category",
                ["All"] + list(set(p['category'] for p in st.session_state.system.db.inventory.values() if p['category']))
            )
        
        # Display inventory table
        inventory_data = []
        for product_id, product in st.session_state.system.db.inventory.items():
            if (not search_term or search_term.lower() in product['name'].lower()) and \
               (filter_category == "All" or product['category'] == filter_category):
                inventory_data.append({
                    "ID": product_id,
                    "Name": product['name'],
                    "Category": product['category'],
                    "Quantity": product['quantity'],
                    "Price": f"${product['price']:.2f}",
                    "Last Updated": product['last_updated'],
                    "Status": "❌ Out of Stock" if product['quantity'] <= 0 else \
                             "⚠️ Low Stock" if product['quantity'] < 10 else \
                             "✅ In Stock"
                })
        
        st.dataframe(
            inventory_data,
            column_config={
                "Status": st.column_config.TextColumn(
                    "Status",
                    help="Inventory status",
                    width="small"
                )
            },
            hide_index=True,
            use_container_width=True
        )
    
    with tab2:
        st.subheader("Add/Update Products")
        
        with st.form("product_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                product_id = st.text_input("Product ID", placeholder="P001")
                product_name = st.text_input("Product Name", placeholder="Wireless Mouse")
                product_category = st.text_input("Category", placeholder="Electronics")
            
            with col2:
                product_quantity = st.number_input("Quantity", min_value=0, step=1)
                product_price = st.number_input("Price", min_value=0.0, step=0.01, format="%.2f")
            
            submitted = st.form_submit_button("Save Product")
            
            if submitted:
                if product_id in st.session_state.system.db.inventory:
                    # Update existing product
                    st.session_state.system.db.inventory[product_id]['name'] = product_name
                    st.session_state.system.db.inventory[product_id]['category'] = product_category
                    st.session_state.system.db.inventory[product_id]['quantity'] = product_quantity
                    st.session_state.system.db.inventory[product_id]['price'] = product_price
                    st.session_state.system.db.inventory[product_id]['last_updated'] = str(datetime.now())
                    
                    activity = {
                        'timestamp': str(datetime.now()),
                        'agent': 'Streamlit UI',
                        'action': 'update_product',
                        'details': f"Updated {product_name} (ID: {product_id})"
                    }
                    st.session_state.system.db.activity_log.append(activity)
                    st.session_state.system.db.save_data()
                    
                    st.toast(f"Product {product_id} updated successfully!")
                else:
                    # Add new product
                    if st.session_state.system.db.add_product(
                        product_id, product_name, product_quantity, product_price, product_category
                    ):
                        st.toast(f"Product {product_id} added successfully!")
                    else:
                        st.error(f"Product {product_id} already exists!")
        
        st.markdown("---")
        st.subheader("Quick Actions")
        
        col1, col2 = st.columns(2)
        
        with col1:
            with st.form("sell_form"):
                sell_product_id = st.selectbox(
                    "Product to Sell",
                    list(st.session_state.system.db.inventory.keys()),
                    format_func=lambda x: f"{x} - {st.session_state.system.db.inventory[x]['name']}"
                )
                sell_quantity = st.number_input("Quantity", min_value=1, step=1)
                
                if st.form_submit_button("Sell Product"):
                    if st.session_state.system.db.sell_product(sell_product_id, sell_quantity):
                        st.toast(f"Sold {sell_quantity} of {sell_product_id}")
                    else:
                        st.error("Failed to sell product - check quantity")
        
        with col2:
            with st.form("update_form"):
                update_product_id = st.selectbox(
                    "Product to Update",
                    list(st.session_state.system.db.inventory.keys()),
                    format_func=lambda x: f"{x} - {st.session_state.system.db.inventory[x]['name']}",
                    key="update_select"
                )
                quantity_change = st.number_input("Quantity Change", step=1)
                
                if st.form_submit_button("Update Quantity"):
                    if st.session_state.system.db.update_quantity(update_product_id, quantity_change):
                        st.toast(f"Updated {update_product_id} by {quantity_change}")
                    else:
                        st.error("Failed to update quantity")

# Agents Activity Tab
elif selected_tab == "Agents Activity":
    st.title("🤖 Agents Activity Monitor")
    
    st.subheader("Agent Status")
    status_col1, status_col2, status_col3 = st.columns(3)
    
    with status_col1:
        st.markdown("### 🤖 Inventory Manager")
        st.markdown("""
        - Monitors stock levels
        - Generates alerts
        - Runs continuously
        """)
        st.progress(100, text="Running")
    
    with status_col2:
        st.markdown("### 📱 WhatsApp Agent")
        st.markdown("""
        - Sends notifications
        - Provides AI suggestions
        - Responds to queries
        """)
        st.progress(100, text="Running")
    
    with status_col3:
        st.markdown("### ✉️ Email Agent")
        st.markdown("""
        - Sends daily reports
        - Provides CSV exports
        - Sends alerts
        """)
        st.progress(100, text="Running")
    
    st.markdown("---")
    
    st.subheader("Agent Communication Log")
    
    # Filter options
    col1, col2, col3 = st.columns(3)
    with col1:
        agent_filter = st.selectbox("Filter by Agent", ["All", "InventoryManager", "WhatsApp Agent", "Email Agent"])
    
    with col2:
        action_filter = st.selectbox("Filter by Action", ["All", "notification", "alert", "error"])
    
    with col3:
        time_filter = st.selectbox("Time Range", ["Last 24 hours", "Last week", "Last month", "All time"])
    
    # Filter activities
    filtered_activities = st.session_state.system.db.activity_log.copy()
    
    if agent_filter != "All":
        filtered_activities = [a for a in filtered_activities if a['agent'] == agent_filter]
    
    if action_filter != "All":
        filtered_activities = [a for a in filtered_activities if action_filter in a['action'].lower()]
    
    # Display filtered activities
    for activity in reversed(filtered_activities):
        with st.container(border=True):
            cols = st.columns([1, 4])
            with cols[0]:
                if "whatsapp" in activity['agent'].lower():
                    st.markdown("📱")
                elif "email" in activity['agent'].lower():
                    st.markdown("✉️")
                else:
                    st.markdown("🤖")
                
                st.markdown(f"**{activity['agent']}**")
                st.caption(activity['timestamp'])
            
            with cols[1]:
                st.markdown(f"**{activity['action']}**")
                st.write(activity['details'])
                
                if "error" in activity['action'].lower():
                    st.error("This action encountered an error")
                elif "alert" in activity['action'].lower():
                    st.warning("This is an alert notification")

# Settings Tab
elif selected_tab == "Settings":
    st.title("⚙️ System Settings")
    
    st.subheader("Agent Configuration")
    
    with st.expander("📱 WhatsApp Settings"):
        st.markdown("Configure WhatsApp notifications")
        twilio_account_sid = st.text_input("Twilio Account SID", value=os.getenv('TWILIO_ACCOUNT_SID', ''))
        twilio_auth_token = st.text_input("Twilio Auth Token", value=os.getenv('TWILIO_AUTH_TOKEN', ''), type="password")
        twilio_whatsapp_number = st.text_input("Twilio WhatsApp Number", value=os.getenv('TWILIO_WHATSAPP_NUMBER', ''))
        recipient_whatsapp_number = st.text_input("Recipient WhatsApp Number", value=os.getenv('RECIPIENT_WHATSAPP_NUMBER', ''))
        
        if st.button("Save WhatsApp Settings"):
            os.environ['TWILIO_ACCOUNT_SID'] = twilio_account_sid
            os.environ['TWILIO_AUTH_TOKEN'] = twilio_auth_token
            os.environ['TWILIO_WHATSAPP_NUMBER'] = twilio_whatsapp_number
            os.environ['RECIPIENT_WHATSAPP_NUMBER'] = recipient_whatsapp_number
            st.session_state.system.whatsapp_agent = WhatsAppAgent(st.session_state.system.db)
            st.toast("WhatsApp settings updated!")
    
    with st.expander("✉️ Email Settings"):
        st.markdown("Configure email notifications")
        smtp_server = st.text_input("SMTP Server", value=os.getenv('SMTP_SERVER', 'smtp.gmail.com'))
        smtp_port = st.number_input("SMTP Port", value=int(os.getenv('SMTP_PORT', 587)))
        smtp_email = st.text_input("SMTP Email", value=os.getenv('SMTP_EMAIL', ''))
        smtp_password = st.text_input("SMTP Password", value=os.getenv('SMTP_PASSWORD', ''), type="password")
        recipient_email = st.text_input("Recipient Email", value=os.getenv('RECIPIENT_EMAIL', ''))
        
        if st.button("Save Email Settings"):
            os.environ['SMTP_SERVER'] = smtp_server
            os.environ['SMTP_PORT'] = str(smtp_port)
            os.environ['SMTP_EMAIL'] = smtp_email
            os.environ['SMTP_PASSWORD'] = smtp_password
            os.environ['RECIPIENT_EMAIL'] = recipient_email
            st.session_state.system.email_agent = EmailAgent(st.session_state.system.db)
            st.toast("Email settings updated!")
    
    with st.expander("🔄 System Maintenance"):
        st.warning("These actions will affect the running system")
        
        if st.button("🔄 Reset Inventory Database"):
            st.session_state.system.db.inventory = {}
            st.session_state.system.db.activity_log = []
            st.session_state.system.db.save_data()
            st.toast("Inventory database reset!")
        
        if st.button("🧹 Clear Activity Log"):
            st.session_state.system.db.activity_log = []
            st.session_state.system.db.save_data()
            st.toast("Activity log cleared!")
        
        if st.button("📤 Export Database"):
            with open("inventory_export.json", "w") as f:
                json.dump({
                    "inventory": st.session_state.system.db.inventory,
                    "activity_log": st.session_state.system.db.activity_log
                }, f)
            
            with open("inventory_export.json", "rb") as f:
                st.download_button(
                    label="Download Export",
                    data=f,
                    file_name="inventory_export.json",
                    mime="application/json"
                )

# Real-time updates
def update_dashboard():
    while True:
        if st.session_state.running:
            status = st.session_state.system.db.get_inventory_status()
            
            # Update metrics (this would need Streamlit's experimental features)
            # For now, we'll just sleep
            time.sleep(5)
        else:
            time.sleep(1)

# Start the update thread
if 'update_thread' not in st.session_state:
    st.session_state.update_thread = threading.Thread(target=update_dashboard, daemon=True)
    st.session_state.update_thread.start()
