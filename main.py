import json
import csv
import os
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import google.generativeai as genai
import threading
import time
from dotenv import load_dotenv
from twilio.rest import Client

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("YOUR_GEMINI_API_KEY"))  # Updated environment variable name
model = genai.GenerativeModel('gemini-2.0-flash')

# ========================
# Inventory Database
# ========================

class InventoryDB:
    def __init__(self, filename='inventory.json'):
        self.filename = filename
        self.activity_log = []
        self.load_data()
    
    def load_data(self):
        """Load inventory and activity log from files"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    self.inventory = json.load(f)
            else:
                self.inventory = {}
            
            if os.path.exists('activity_log.json'):
                with open('activity_log.json', 'r') as f:
                    self.activity_log = json.load(f)
        except Exception as e:
            print(f"Error loading data: {str(e)}")
            self.inventory = {}
            self.activity_log = []
    
    def save_data(self):
        """Save inventory and activity log to files"""
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.inventory, f, indent=2)
            
            with open('activity_log.json', 'w') as f:
                json.dump(self.activity_log, f, indent=2)
        except Exception as e:
            print(f"Error saving data: {str(e)}")
    
    def add_product(self, product_id, name, quantity, price, category=""):
        """Add a new product to inventory"""
        if product_id in self.inventory:
            return False
        
        self.inventory[product_id] = {
            'name': name,
            'quantity': quantity,
            'price': price,
            'category': category,
            'last_updated': str(datetime.now())
        }
        
        activity = {
            'timestamp': str(datetime.now()),
            'agent': 'InventoryManager',
            'action': 'add_product',
            'details': f"Added {name} (ID: {product_id}), Qty: {quantity}, Price: {price}"
        }
        self.activity_log.append(activity)
        self.save_data()
        return True
    
    def update_quantity(self, product_id, change):
        """Update product quantity"""
        if product_id not in self.inventory:
            return False
        
        self.inventory[product_id]['quantity'] += change
        self.inventory[product_id]['last_updated'] = str(datetime.now())
        
        activity = {
            'timestamp': str(datetime.now()),
            'agent': 'InventoryManager',
            'action': 'update_quantity',
            'details': f"Updated {self.inventory[product_id]['name']} (ID: {product_id}) by {change}. New Qty: {self.inventory[product_id]['quantity']}"
        }
        self.activity_log.append(activity)
        self.save_data()
        return True
    
    def sell_product(self, product_id, quantity_sold):
        """Sell a product (reduce quantity)"""
        if product_id not in self.inventory:
            return False
        
        if self.inventory[product_id]['quantity'] < quantity_sold:
            return False
        
        self.inventory[product_id]['quantity'] -= quantity_sold
        self.inventory[product_id]['last_updated'] = str(datetime.now())
        
        activity = {
            'timestamp': str(datetime.now()),
            'agent': 'InventoryManager',
            'action': 'sell_product',
            'details': f"Sold {quantity_sold} of {self.inventory[product_id]['name']} (ID: {product_id}). Remaining Qty: {self.inventory[product_id]['quantity']}"
        }
        self.activity_log.append(activity)
        self.save_data()
        return True
    
    def delete_product(self, product_id):
        """Remove a product from inventory"""
        if product_id not in self.inventory:
            return False
        
        product_name = self.inventory[product_id]['name']
        del self.inventory[product_id]
        
        activity = {
            'timestamp': str(datetime.now()),
            'agent': 'InventoryManager',
            'action': 'delete_product',
            'details': f"Deleted {product_name} (ID: {product_id})"
        }
        self.activity_log.append(activity)
        self.save_data()
        return True
    
    def get_inventory_status(self):
        """Get summary of inventory status"""
        status = {
            'total_products': len(self.inventory),
            'out_of_stock': sum(1 for p in self.inventory.values() if p['quantity'] <= 0),
            'low_stock': sum(1 for p in self.inventory.values() if 0 < p['quantity'] < 10),
            'total_value': sum(p['quantity'] * p['price'] for p in self.inventory.values())
        }
        return status
    
    def get_recent_activities(self, limit=10):
        """Get recent activities from log"""
        return self.activity_log[-limit:][::-1]

# ========================
# WhatsApp Agent
# ========================

class WhatsAppAgent:
    def __init__(self, db):
        self.db = db
        self.name = "WhatsApp Agent"
        
        # Load Twilio configuration from environment variables
        self.twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.twilio_whatsapp_number = os.getenv('TWILIO_WHATSAPP_NUMBER')
        self.recipient_number = os.getenv('RECIPIENT_WHATSAPP_NUMBER')
        
        # Initialize Twilio client
        if all([self.twilio_account_sid, self.twilio_auth_token]):
            self.twilio_client = Client(self.twilio_account_sid, self.twilio_auth_token)
        else:
            print("Warning: Twilio credentials not found. WhatsApp notifications will not work.")
            self.twilio_client = None
    
    def send_real_whatsapp(self, message):
        """Send actual WhatsApp message using Twilio API"""
        if not self.twilio_client:
            print("WhatsApp not configured - cannot send message")
            return False
        
        try:
            # Ensure numbers are in correct format
            from_whatsapp = f"whatsapp:{self.twilio_whatsapp_number.strip('whatsapp:')}"
            to_whatsapp = f"whatsapp:{self.recipient_number.strip('whatsapp:')}"
            
            print(f"Attempting to send WhatsApp message to {to_whatsapp}")
            
            message = self.twilio_client.messages.create(
                body=message,
                from_=from_whatsapp,
                to=to_whatsapp
            )
            
            print(f"WhatsApp message sent successfully! SID: {message.sid}")
            
            # Log the activity
            activity = {
                'timestamp': str(datetime.now()),
                'agent': self.name,
                'action': 'whatsapp_notification',
                'details': f"Sent WhatsApp to {self.recipient_number}: {message}"
            }
            self.db.activity_log.append(activity)
            self.db.save_data()
            
            return True
        except Exception as e:
            error_msg = f"Failed to send WhatsApp: {str(e)}"
            print(error_msg)
            
            # Log the error
            activity = {
                'timestamp': str(datetime.now()),
                'agent': self.name,
                'action': 'whatsapp_error',
                'details': error_msg
            }
            self.db.activity_log.append(activity)
            self.db.save_data()
            
            return False
    
    def send_message(self, message):
        """Send a WhatsApp-style message (console and real)"""
        timestamp = datetime.now().strftime("%H:%M")
        print(f"[{timestamp}] {self.name}: {message}")
        
        # Also send real WhatsApp if configured
        if self.twilio_client:
            self.send_real_whatsapp(message)
        
        # Log the activity
        activity = {
            'timestamp': str(datetime.now()),
            'agent': self.name,
            'action': 'notification',
            'details': message
        }
        self.db.activity_log.append(activity)
        self.db.save_data()
    
    def get_ai_response(self, prompt):
        """Get AI-generated response using Gemini"""
        try:
            response = model.generate_content(
                f"You are an inventory management assistant. Respond conversationally to: {prompt}"
            )
            return response.text
        except Exception as e:
            return f"Sorry, I encountered an error: {str(e)}"
    
    def notify_activity(self):
        """Notify about recent activities"""
        activities = self.db.get_recent_activities(5)
        if not activities:
            self.send_message("No recent activities to report.")
            return
        
        message = "📊 Recent Inventory Activities:\n"
        for idx, activity in enumerate(activities, 1):
            message += f"\n{idx}. ⏰ {activity['timestamp']}\n   👤 {activity['agent']}\n   🛠️ {activity['action']}\n   📝 {activity['details']}\n"
        
        self.send_message(message)
    
    def suggest_actions(self):
        """Use AI to suggest inventory actions"""
        status = self.db.get_inventory_status()
        prompt = f"""Based on this inventory status, suggest 3-5 management actions:
        - Total products: {status['total_products']}
        - Out of stock: {status['out_of_stock']}
        - Low stock: {status['low_stock']}
        - Total inventory value: ${status['total_value']:.2f}
        
        Respond in a conversational WhatsApp message format with emojis."""
        
        suggestion = self.get_ai_response(prompt)
        self.send_message("🤖 AI Suggestions:\n" + suggestion)

# ========================
# Email Agent
# ========================

class EmailAgent:
    def __init__(self, db):
        self.db = db
        self.name = "Email Agent"
        
        # Load SMTP configuration from environment variables
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.sender_email = os.getenv('SMTP_EMAIL')
        self.sender_password = os.getenv('SMTP_PASSWORD')
        self.recipient_email = os.getenv('RECIPIENT_EMAIL', 'salman854raza@gmail.com')
    
    def send_email(self, subject, body, attachments=None, to_email=None):
        """Send email with optional attachments"""
        if to_email is None:
            to_email = self.recipient_email
        
        if not all([self.smtp_server, self.smtp_port, self.sender_email, self.sender_password]):
            print("Email not configured properly - cannot send message")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add both plain and HTML versions
            msg.attach(MIMEText(body, 'plain'))
            html_body = f"<pre>{body}</pre>"  # Simple HTML version
            msg.attach(MIMEText(html_body, 'html'))
            
            if attachments:
                for attachment in attachments:
                    with open(attachment['filename'], 'rb') as f:
                        part = MIMEApplication(
                            f.read(),
                            Name=os.path.basename(attachment['filename'])
                        )
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment["filename"])}"'
                    msg.attach(part)
            
            # Debug print before sending
            print(f"Attempting to send email to {to_email} with subject: {subject}")
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
                print("Email sent successfully!")
            
            # Log email activity
            activity = {
                'timestamp': str(datetime.now()),
                'agent': self.name,
                'action': 'send_email',
                'details': f"Sent email to {to_email} with subject: {subject}"
            }
            self.db.activity_log.append(activity)
            self.db.save_data()
            return True
        except Exception as e:
            error_msg = f"Failed to send email to {to_email}: {str(e)}"
            print(error_msg)
            activity = {
                'timestamp': str(datetime.now()),
                'agent': self.name,
                'action': 'email_error',
                'details': error_msg
            }
            self.db.activity_log.append(activity)
            self.db.save_data()
            return False
    
    def generate_inventory_report_csv(self):
        """Generate CSV report of current inventory"""
        filename = f"inventory_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        try:
            with open(filename, 'w', newline='') as csvfile:
                fieldnames = ['ID', 'Name', 'Category', 'Quantity', 'Price', 'Last Updated']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for product_id, product in self.db.inventory.items():
                    writer.writerow({
                        'ID': product_id,
                        'Name': product['name'],
                        'Category': product['category'],
                        'Quantity': product['quantity'],
                        'Price': product['price'],
                        'Last Updated': product['last_updated']
                    })
            return filename
        except Exception as e:
            print(f"Error generating CSV report: {str(e)}")
            return None
    
    def send_daily_report(self):
        """Send daily inventory report with CSV attachment"""
        status = self.db.get_inventory_status()
        csv_file = self.generate_inventory_report_csv()

        if not csv_file:
            return False
        
        subject = f"Inventory Daily Report - {datetime.now().strftime('%Y-%m-%d')}"

        # Enhanced email body with recent activities
        activities = self.db.get_recent_activities(5)
        activities_text = "\n".join(
            f"{idx}. {act['timestamp']} - {act['action']}: {act['details']}"
            for idx, act in enumerate(activities, 1))

        body = f"""📊 Inventory Status Report:
        
🛍️ Total Products: {status['total_products']}
❌ Out of Stock Items: {status['out_of_stock']}
⚠️ Low Stock Items: {status['low_stock']}
💰 Total Inventory Value: ${status['total_value']:.2f}

📅 Recent Activities:
{activities_text}

📎 See attached CSV for full inventory details.
"""
        
        attachments = [{
            'filename': csv_file,
            'description': 'Inventory CSV Report'
        }] if csv_file else None
        
        success = self.send_email(subject, body, attachments)
        
        # Clean up CSV file
        try:
            if csv_file and os.path.exists(csv_file):
                os.remove(csv_file)
        except Exception as e:
            print(f"Error removing CSV file: {str(e)}")
        
        return success

    def send_activity_notification(self, message):
        """Send immediate notification about important activities"""
        subject = "🚨 Inventory Activity Notification"
        body = f"""📢 New inventory activity:
        
{message}

⏰ Timestamp: {datetime.now()}
"""
        return self.send_email(subject, body)

# ========================
# Inventory Manager Agent
# ========================

class InventoryManager:
    def __init__(self, db, whatsapp_agent, email_agent):
        self.db = db
        self.whatsapp_agent = whatsapp_agent
        self.email_agent = email_agent
        self.name = "Inventory Manager"
        self.running = True
        self.thread = threading.Thread(target=self.monitor_inventory)
        self.thread.daemon = True
        self.thread.start()
    
    def monitor_inventory(self):
        """Background monitoring of inventory"""
        while self.running:
            try:
                status = self.db.get_inventory_status()
                
                # Check for out of stock items
                if status['out_of_stock'] > 0:
                    message = f"🚨 Alert: {status['out_of_stock']} product(s) out of stock!"
                    self.whatsapp_agent.send_message(message)
                    self.email_agent.send_activity_notification(message)
                    
                    activity = {
                        'timestamp': str(datetime.now()),
                        'agent': self.name,
                        'action': 'out_of_stock_alert',
                        'details': f"{status['out_of_stock']} product(s) out of stock"
                    }
                    self.db.activity_log.append(activity)
                    self.db.save_data()
                
                # Check for low stock items
                if status['low_stock'] > 0:
                    message = f"⚠️ Alert: {status['low_stock']} product(s) low on stock!"
                    self.whatsapp_agent.send_message(message)
                    self.email_agent.send_activity_notification(message)
                    
                    activity = {
                        'timestamp': str(datetime.now()),
                        'agent': self.name,
                        'action': 'low_stock_alert',
                        'details': f"{status['low_stock']} product(s) low on stock"
                    }
                    self.db.activity_log.append(activity)
                    self.db.save_data()
                
                # Send daily report at 9 AM
                now = datetime.now()
                if now.hour == 9 and now.minute == 0:
                    self.email_agent.send_daily_report()
                    self.whatsapp_agent.send_message("📅 Daily inventory report has been sent to your email!")
                
                time.sleep(60)  # Check every minute (for demo purposes)
                
            except Exception as e:
                print(f"Error in inventory monitoring: {str(e)}")
                time.sleep(60)  # Wait before retrying
    
    def stop(self):
        """Stop the monitoring thread"""
        self.running = False
        self.thread.join()

# ========================
# Main System
# ========================

class InventorySystem:
    def __init__(self):
        # Initialize database
        self.db = InventoryDB()
        
        # Initialize agents
        self.whatsapp_agent = WhatsAppAgent(self.db)
        self.email_agent = EmailAgent(self.db)
        self.inventory_manager = InventoryManager(
            self.db, 
            self.whatsapp_agent, 
            self.email_agent
        )
        
        # Start with initial notifications
        self.whatsapp_agent.send_message("🔄 Inventory system initialized and ready!")
        self.email_agent.send_email(
            "System Initialized",
            'Inventory management system is now running'
        )
    
    def shutdown(self):
        """Shut down the system"""
        self.inventory_manager.stop()
        self.whatsapp_agent.send_message("🛑 Inventory system shutting down. Goodbye!")
        self.email_agent.send_email(
            "System Shutdown",
            'Inventory management system is shutting down'
        )

# ========================
# Demonstration
# ========================

if __name__ == "__main__":
    print("=== AI-Powered Inventory Management System ===")
    print("Initializing system with three agents...")
    
    # Initialize the system
    system = InventorySystem()
    
    # Add some sample products
    print("\nAdding sample products...")
    system.db.add_product("P001", "Wireless Mouse", 50, 19.99, "Electronics")
    system.db.add_product("P002", "Mechanical Keyboard", 15, 89.99, "Electronics")
    system.db.add_product("P003", "Monitor Stand", 3, 29.99, "Accessories")
    system.db.add_product("P004", "USB-C Cable", 0, 9.99, "Accessories")  # Out of stock
    
    # Simulate some sales
    print("\nSimulating sales...")
    system.db.sell_product("P001", 5)  # Sell 5 mice
    system.db.sell_product("P002", 10)  # Sell 10 keyboards
    
    # Update quantity
    print("\nUpdating stock...")
    system.db.update_quantity("P003", -2)  # Remove 2 monitor stands
    
    # Get WhatsApp notifications
    print("\nGetting WhatsApp notifications...")
    system.whatsapp_agent.notify_activity()
    system.whatsapp_agent.suggest_actions()
    
    # Send email report
    print("\nSending email report...")
    system.email_agent.send_daily_report()
    
    # Keep the system running for a while to demonstrate monitoring
    print("\nSystem will run for 5 minutes to demonstrate monitoring...")
    time.sleep(300)  # 5 minutes
    
    # Shutdown
    print("\nShutting down system...")
    system.shutdown()
    print("System shutdown complete.")