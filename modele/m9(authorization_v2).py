
import sys
import os
import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import contextmanager
import time
import signal
import hashlib
import getpass
import atexit
from typing import Optional, Tuple

# add path to folder python_calculator
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "python_calculator")))

from python_calculator.calculator import process_expression

from flask import Flask, request, jsonify, render_template_string

from flask_cors import CORS

import uuid

# ----------------------------- HTML TEMPLATE ----------------------------------

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            background-color: #f0f0f0;
        }
        .window {
            position: absolute;
            left: {{ x }}px;
            top: {{ y }}px;
            width: {{ w }}px;
            height: {{ h }}px;
            border: 2px solid #333;
            background-color: #ccc;
            box-shadow: 2px 2px 10px rgba(0,0,0,0.5);
            padding: 10px;
        }
        .display-container {
            position: absolute;
            top: 50px;
            left: 100px;
            display: flex;
            align-items: center;
        }
        .display-label {
            font-family: sans-serif;
            font-size: 14px;
            margin-right: 10px;
        }
        .display-box {
            width: 200px;
            height: 50px;
            border: 1px solid #666;
            background-color: #fff;
            font-family: monospace;
            font-size: 14px;
            padding: 5px;
            box-sizing: border-box;
        }
        .radio-button {
            position: absolute;
            top: 120px;
            left: 100px;
            font-family: sans-serif;
            font-size: 14px;
        }
        .return-button {
            position: absolute;
            left: {{ ret_x }}px;
            top: {{ ret_y }}px;
            width: {{ ret_w }}px;
            height: {{ ret_h }}px;
            font-size: 12px;
        }
        .radio-group {
            position: absolute;
            top: 150px;
            left: 160px;
            width: 200px;
            border: 1px solid #333;
            background-color: #eee;
            padding: 10px;
        }
    </style>
</head>
<body>
    <div class="window">
        <div class="display-container">
            <div class="display-label">calculator function</div>
            <input class="display-box" type="text" value="{{ first_text }}" readonly>

            <div class="display-label" style="margin-left: 20px;">n-th fibbonaci number</div>
            <input class="display-box" type="text" value="{{ second_text }}" readonly>

            <div class="display-label" style="margin-left: 20px;">factorial of the number</div>
            <input class="display-box" type="text" value="{{ third_text }}" readonly>
        </div>
        
        <form method="post">
            <div class="radio-group">
                {% set custom_labels = ["calculator function", "n-th fibbonaci number", "factorial of the number"] %}
                {% for i in range(radio_buttons | length) %}
                <div class="radio-option">
                    <input type="radio" id="{{ radio_buttons[i].id }}" name="radio_option" value="{{ i + 1 }}" 
                        {% if selected_choice == i + 1 %}checked{% endif %}>
                    <label for="{{ radio_buttons[i].id }}">{{ custom_labels[i] }}</label>
                </div>
                {% endfor %}
            </div>
            
            <div style="position: absolute; top: 130px; left: 400px;">
                <label for="edit_box" style="font-family: sans-serif; font-size: 14px;">My Input</label><br>
                <textarea id="edit_box" name="edit_box" style="width: 150px; height: 100px; font-family: monospace; font-size: 14px;">{{ current_input }}</textarea>
            </div>
            
            <button class="return-button" type="submit">&Return</button>
        </form>
    </div>
</body>
</html>
"""

# ----------------------------- AUTHENTICATION SYSTEM ---------------------------

class AuthenticationManager:
    """Simple console-based authentication system"""
    
    def __init__(self):
        # Path to persisted auth state
        self.auth_state_path = os.path.join(os.path.dirname(__file__), '.auth_state.json')
        
        # Predefined users (in production, use a database)
        self.users = {
            'admin': {
                'password_hash': self._hash_password('admin123'),
                'role': 'admin'
            },
            'user': {
                'password_hash': self._hash_password('user123'),
                'role': 'user'
            }
        }
        # Use a global temp file or env-based storage for persistence across app startup
        self.auth_state_path = os.path.join(os.path.dirname(__file__), '.auth_state.json')
        self.current_user = None
        self.current_role = None
        self._load_auth_state()
    
    def _hash_password(self, password: str) -> str:
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def _load_auth_state(self):
        if os.path.exists(self.auth_state_path):
            try:
                with open(self.auth_state_path, 'r') as f:
                    state = json.load(f)
                    self.current_user = state.get('user')
                    self.current_role = state.get('role')
                    if self.current_user and self.current_role:
                        logger.info(f"Loaded persisted authentication for {self.current_user} ({self.current_role})")
            except Exception as e:
                logger.warning(f"Failed to load auth state: {e}")
    
    def _persist_auth_state(self):
        try:
            with open(self.auth_state_path, 'w') as f:
                json.dump({
                    'user': self.current_user,
                    'role': self.current_role
                }, f)
        except Exception as e:
            logger.warning(f"Failed to persist auth state: {e}")
    
    def authenticate_console(self) -> Tuple[bool, str]:
        """Console-based authentication with enhanced interrupt handling"""
        if self.current_user and self.current_role:
            print(f"Already authenticated as {self.current_user} ({self.current_role})")
            return True, self.current_role
        
        print("\n=== Calculator Authentication ===")
        max_attempts = 3
        
        for attempt in range(max_attempts):
            try:
                username = input("Username: ").strip()
                password = getpass.getpass("Password: ")
                
                if self.verify_credentials(username, password):
                    self.current_user = username
                    self.current_role = self.users[username]['role']
                    self._persist_auth_state()
                    print(f" Authentication successful! Logged in as {username} ({self.current_role})")
                    logger.info(f"User {username} authenticated successfully with role {self.current_role}")
                    return True, self.current_role
                else:
                    remaining = max_attempts - attempt - 1
                    if remaining > 0:
                        print(f" Invalid credentials. {remaining} attempts remaining.")
                    else:
                        print(" Authentication failed. Maximum attempts exceeded.")
                        logger.warning(f"Authentication failed for user: {username}")
                    
            except KeyboardInterrupt:
                print("\n\nAuthentication cancelled by user (Ctrl+C).")
                print("Cleaning up and exiting...")
                self.logout()  # Clear auth state if interrupted
                sys.exit(0)  # Exit cleanly instead of returning False
            except EOFError:
                print("\n\nInput terminated (terminal killed).")
                print("Cleaning up and exiting...")
                self.logout()  # Clear auth state if interrupted
                sys.exit(0)  # Exit cleanly
            except Exception as e:
                print(f"Authentication error: {e}")
                logger.error(f"Authentication error: {e}")
        
        self.logout()  # Clear auth state on final failure
        return False, None
    
    def verify_credentials(self, username: str, password: str) -> bool:
        """Verify user credentials"""
        if username not in self.users:
            return False
        
        password_hash = self._hash_password(password)
        return self.users[username]['password_hash'] == password_hash
    
    def is_admin(self) -> bool:
        """Check if current user is admin"""
        return self.current_role == 'admin'
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return self.current_user is not None
    
    def get_current_user(self) -> Optional[str]:
        """Get current username"""
        return self.current_user
    
    def get_current_role(self) -> Optional[str]:
        """Get current user role"""
        return self.current_role
    
    def logout(self):
        """Logout current user with enhanced logging"""
        if self.current_user:
            logger.info(f"User {self.current_user} ({self.current_role}) logging out")
            print(f"User {self.current_user} logged out.")
            
            # Log the logout time
            try:
                logout_info = {
                    'user': self.current_user,
                    'role': self.current_role,
                    'logout_time': datetime.utcnow().isoformat(),
                    'session_ended': True
                }
                logger.info(f"Logout details: {logout_info}")
            except Exception as e:
                logger.warning(f"Failed to log logout details: {e}")
        else:
            logger.info("Logout called but no user was logged in")
        
        self.current_user = None
        self.current_role = None
        
        # Remove persisted auth file
        if os.path.exists(self.auth_state_path):
            try:
                os.remove(self.auth_state_path)
                logger.info("Persisted authentication state removed")
            except Exception as e:
                logger.warning(f"Failed to remove auth state file: {e}")

# ----------------------------- LOGGING CONFIGURATION ---------------------------

def setup_enhanced_logging():
    """Setup enhanced logging system with separate files for different log levels"""
    
    # Create logs directory if it doesn't exist
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Remove existing handlers to avoid duplication
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-20s | %(funcName)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Main application log (all levels)
    main_handler = logging.FileHandler(os.path.join(logs_dir, 'calculator_app.log'))
    main_handler.setLevel(logging.DEBUG)
    main_handler.setFormatter(detailed_formatter)
    
    # Performance and calculation log (specific for calculations)
    calc_handler = logging.FileHandler(os.path.join(logs_dir, 'calculations.log'))
    calc_handler.setLevel(logging.INFO)
    calc_handler.setFormatter(simple_formatter)
    
    # Error log (errors only)
    error_handler = logging.FileHandler(os.path.join(logs_dir, 'errors.log'))
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(main_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)
    
    # Setup calculation logger
    calc_logger = logging.getLogger('calculations')
    calc_logger.setLevel(logging.INFO)
    calc_logger.addHandler(calc_handler)
    calc_logger.propagate = False  # Don't propagate to root logger to avoid duplication
    
    return root_logger, calc_logger

# Initialize enhanced logging
logger, calc_logger = setup_enhanced_logging()

# ----------------------------- DATABASE LAYER -------------------------------

class DatabaseManager:
    def __init__(self, db_path: str = "calculator_api.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize the database with required tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Requests table to store all API requests
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_requests (
                    id TEXT PRIMARY KEY,
                    operation_type TEXT NOT NULL,
                    input_value TEXT NOT NULL,
                    result TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    ip_address TEXT,
                    user_agent TEXT
                )
            ''')
            
            # Sessions table to maintain user sessions
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_sessions (
                    session_id TEXT PRIMARY KEY,
                    last_choice INTEGER DEFAULT 0,
                    last_input TEXT DEFAULT '',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            logger.info("Database initialized successfully")

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def log_request(self, operation_type: str, input_value: str, result: str = None, 
                status: str = "success", error_message: str = None, 
                ip_address: str = None, user_agent: str = None) -> str:
        """Log an API request to the database"""
        request_id = str(uuid.uuid4())
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO api_requests 
                (id, operation_type, input_value, result, status, error_message, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (request_id, operation_type, input_value, result, status, error_message, ip_address, user_agent))
            conn.commit()
        
        return request_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get user session data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_sessions WHERE session_id = ?', (session_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_session(self, session_id: str, last_choice: int = None, last_input: str = None):
        """Update or create user session"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if session exists
            cursor.execute('SELECT session_id FROM user_sessions WHERE session_id = ?', (session_id,))
            exists = cursor.fetchone()
            
            if exists:
                updates = []
                params = []
                
                if last_choice is not None:
                    updates.append('last_choice = ?')
                    params.append(last_choice)
                
                if last_input is not None:
                    updates.append('last_input = ?')
                    params.append(last_input)
                
                if updates:
                    updates.append('updated_at = CURRENT_TIMESTAMP')
                    params.append(session_id)
                    
                    cursor.execute(f'''
                        UPDATE user_sessions 
                        SET {', '.join(updates)}
                        WHERE session_id = ?
                    ''', params)
            else:
                cursor.execute('''
                    INSERT INTO user_sessions (session_id, last_choice, last_input)
                    VALUES (?, ?, ?)
                ''', (session_id, last_choice or 0, last_input or ''))
            
            conn.commit()

    def get_request_history(self, limit: int = 100, offset: int = 0) -> list:
        """Get request history with pagination"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM api_requests 
                ORDER BY timestamp DESC 
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            return [dict(row) for row in cursor.fetchall()]

    def get_analytics(self) -> Dict[str, Any]:
        """Get basic analytics about API usage"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total requests
            cursor.execute('SELECT COUNT(*) as total FROM api_requests')
            total_requests = cursor.fetchone()['total']
            
            # Requests by operation type
            cursor.execute('''
                SELECT operation_type, COUNT(*) as count 
                FROM api_requests 
                GROUP BY operation_type
            ''')
            operation_stats = {row['operation_type']: row['count'] for row in cursor.fetchall()}
            
            # Success rate
            cursor.execute('''
                SELECT status, COUNT(*) as count 
                FROM api_requests 
                GROUP BY status
            ''')
            status_stats = {row['status']: row['count'] for row in cursor.fetchall()}
            
            return {
                'total_requests': total_requests,
                'operation_stats': operation_stats,
                'status_stats': status_stats
            }

# ----------------------------- CACHE SYSTEM ------------------------------------

class ExpressionCache:
    """Enhanced cache system with detailed logging"""
    
    def __init__(self):
        self.cache = {
            'calculator': {},  # Cache for calculator expressions
            'fibonacci': {},   # Cache for fibonacci numbers
            'factorial': {}    # Cache for factorial
        }
        self.hit_count = 0
        self.miss_count = 0
    
    def get(self, operation_type: str, input_value: str):
        """Get cached result if exists with detailed logging"""
        cache_key = str(input_value).strip()
        start_time = time.time()
        
        if cache_key in self.cache[operation_type]:
            self.hit_count += 1
            access_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            result = self.cache[operation_type][cache_key]
            
            # Log cache hit
            calc_logger.info(f"CACHE_HIT | Operation: {operation_type} | Input: '{input_value}' | "
                        f"Result: {result} | Access_Time: {access_time:.2f}ms")
            
            logger.debug(f"Cache HIT for {operation_type}: {input_value} -> {result}")
            
            return result
        
        self.miss_count += 1
        access_time = (time.time() - start_time) * 1000
        
        # Log cache miss
        calc_logger.info(f"CACHE_MISS | Operation: {operation_type} | Input: '{input_value}' | "
                    f"Access_Time: {access_time:.2f}ms")
        
        logger.debug(f"Cache MISS for {operation_type}: {input_value}")
        
        return None
    
    def set(self, operation_type: str, input_value: str, result):
        """Store result in cache with logging"""
        cache_key = str(input_value).strip()
        start_time = time.time()
        
        self.cache[operation_type][cache_key] = result
        
        store_time = (time.time() - start_time) * 1000
        
        # Log cache store
        calc_logger.info(f"CACHE_STORE | Operation: {operation_type} | Input: '{input_value}' | "
                    f"Result: {result} | Store_Time: {store_time:.2f}ms")
        
        logger.debug(f"Cache STORED for {operation_type}: {input_value} = {result}")
    
    def get_stats(self):
        """Get cache statistics"""
        total_requests = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total_requests * 100) if total_requests > 0 else 0
        
        stats = {
            'hit_count': self.hit_count,
            'miss_count': self.miss_count,
            'hit_rate': round(hit_rate, 2),
            'cache_sizes': {
                'calculator': len(self.cache['calculator']),
                'fibonacci': len(self.cache['fibonacci']),
                'factorial': len(self.cache['factorial'])
            }
        }
        
        logger.info(f"Cache statistics requested: {stats}")
        return stats
    
    def clear_cache(self, operation_type: str = None):
        """Clear cache for specific operation or all with logging"""
        if operation_type and operation_type in self.cache:
            cleared_count = len(self.cache[operation_type])
            self.cache[operation_type].clear()
            
            calc_logger.info(f"CACHE_CLEAR | Operation: {operation_type} | Cleared_Items: {cleared_count}")
            logger.info(f"Cache cleared for {operation_type}, {cleared_count} items removed")
        else:
            total_cleared = sum(len(cache) for cache in self.cache.values())
            for cache_type in self.cache:
                self.cache[cache_type].clear()
            self.hit_count = 0
            self.miss_count = 0
            
            calc_logger.info(f"CACHE_CLEAR_ALL | Cleared_Items: {total_cleared}")
            logger.info(f"All caches cleared, {total_cleared} items removed")


# ----------------------------- CLASSES ---------------------------------------

class Point:
    def __init__(self, x, y):
        self._x = x
        self._y = y

    def getX(self):
        return self._x

    def getY(self):
        return self._y
    
    def setY(self, y):
        self._y = y

class Fl_Output:
    def __init__(self, x, y, w, h, label=None):
        self.x = x
        self.y = y
        self.width = w
        self.height = h
        self.label = label
        self._value = ""

    def value(self, txt):
        self._value = txt

    def redraw(self):
        pass

    def getText(self):
        return self._value

class MyDisplayBox(Fl_Output):
    def __init__(self, pos: Point, w: int, h: int, label: str = None):
        super().__init__(pos.getX(), pos.getY(), w, h, label)

    def setText(self, txt: str):
        self.value(txt)
        self.redraw()

class MyReturnButton:
    def __init__(self, pos: Point, w: int, h: int, label: str = "&Return"):
        self.x = pos.getX()
        self.y = pos.getY()
        self.w = w
        self.h = h
        self.label = label
        self.tooltip = "Push Return button to exit"
        self.labelsize = 12

    def getRenderParams(self):
        return {
            "ret_x": self.x,
            "ret_y": self.y,
            "ret_w": self.w,
            "ret_h": self.h,
            "label": self.label
        }

# ----------------------------- EDIT BOX CLASS ----------------------------------

class MyEditBox:
    def __init__(self, pos: Point, w: int, h: int, label: str):
        self.x = pos.getX()
        self.y = pos.getY()
        self.w = w
        self.h = h
        self.label = label
        self.tooltip = "Input field for short text with newlines."
        self.wrap = True  # Equivalent behavior
        self.controller = None
        self.value = ""

    def setText(self, txt: str):
        self.value = txt

    def getText(self):
        return self.value

    def input_cb(self):
        # Placeholder for future callback logic, e.g., notify controller or update model
        pass

    def getRenderParams(self):
        return {
            "edit_x": self.x,
            "edit_y": self.y,
            "edit_w": self.w,
            "edit_h": self.h,
            "edit_label": self.label,
            "edit_value": self.value
        }
        
# ----------------------------- MODEL CLASS ------------------------------------

class Model:
    def __init__(self, db_manager: DatabaseManager, session_id: str = None, cache: ExpressionCache = None):
        self.db_manager = db_manager
        self.session_id = session_id or str(uuid.uuid4())
        # Use provided cache or create new one (for backwards compatibility)
        self.cache = cache if cache is not None else ExpressionCache()
        
        # Load session data
        session_data = self.db_manager.get_session(self.session_id)
        if session_data:
            self.lastChoice = session_data['last_choice']
            self.lastInput = session_data['last_input']
        else:
            self.lastChoice = 0
            self.lastInput = ""
        
        # Views (for web interface compatibility)
        self.calculatorOutputView = None
        self.fibonacciOutputView = None
        self.factorialOutputView = None

    def setLastChoice(self, ch):
        self.lastChoice = ch
        self.db_manager.update_session(self.session_id, last_choice=ch)
        self.notify()

    def getLastChoice(self):
        return self.lastChoice

    def setCalculatorView(self, db: MyDisplayBox):
        self.calculatorOutputView = db

    def setFibonacciView(self, db: MyDisplayBox):
        self.fibonacciOutputView = db
    
    def setLastInput(self, txt):
        self.lastInput = txt
        self.db_manager.update_session(self.session_id, last_input=txt)

    def setFactorialView(self, db: MyDisplayBox):
        self.factorialOutputView = db

    def notify(self):
        if self.calculatorOutputView:
            self.calculatorOutputView.setText("Last choice is " + str(self.lastChoice))
        if self.fibonacciOutputView:
            self.fibonacciOutputView.setText(f"Last input is `{self.lastInput}`")
    
    def get_session_id(self):
        return self.session_id
    
    def get_cache_stats(self):
        """Get cache statistics"""
        return self.cache.get_stats()
    
    def clear_cache(self, operation_type: str = None):
        """Clear cache"""
        self.cache.clear_cache(operation_type)

# ----------------------------- CONTROLLER CLASS -------------------------------

class Controller:
    def __init__(self, db_manager: DatabaseManager = None, auth_manager: AuthenticationManager = None):
        self.model = None
        self.db_manager = db_manager
        self.auth_manager = auth_manager or AuthenticationManager()
        
        # Define restricted operations (only admin can use these)
        self.admin_only_operations = {
            'calculator': ['eval', 'exec', 'import', '__'],  # Dangerous expressions
            'fibonacci': [30, 100],  # Numbers above these values
            'factorial': [100, 200]  # Numbers above these values
        }

    def setModel(self, aModel: Model):
        self.model = aModel
    
    def check_permission(self, operation_type: str, input_value: str) -> Tuple[bool, str]:
        """Check if current user has permission for the operation"""
        if not self.auth_manager.is_authenticated():
            return False, "Authentication required"
        
        if self.auth_manager.is_admin():
            return True, "Admin access granted"
        
        # Check user restrictions
        if operation_type == 'calculator':
            # Check for dangerous expressions
            dangerous_keywords = self.admin_only_operations['calculator']
            input_lower = input_value.lower()
            for keyword in dangerous_keywords:
                if keyword in input_lower:
                    return False, f"Expression contains restricted keyword '{keyword}'. Admin access required."
        
        elif operation_type == 'fibonacci':
            try:
                n = int(input_value.strip())
                if n > 29 and not self.auth_manager.is_admin():
                    return False, f"Fibonacci numbers above {max(self.admin_only_operations['fibonacci'])} require admin access."
            except ValueError:
                return False, "Invalid input for fibonacci"
        
        elif operation_type == 'factorial':
            try:
                n = int(input_value.strip())
                if n > max(self.admin_only_operations['factorial']):
                    return False, f"Factorial numbers above {max(self.admin_only_operations['factorial'])} require admin access."
            except ValueError:
                return False, "Invalid input for factorial"
        
        return True, "User access granted"

    def chControl(self, aString: str):
        """Apply the action from the GUI to the model with logging"""
        start_time = time.time()
        try:
            ch = int(aString.strip().split()[-1])
            self.model.setLastChoice(ch)
            
            execution_time = (time.time() - start_time) * 1000
            calc_logger.info(f"CHOICE_CHANGE | User: {self.auth_manager.get_current_user()} | "
                        f"Choice: {ch} | Execution_Time: {execution_time:.2f}ms")
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            error_msg = f"Invalid input to Controller.chControl: {aString}"
            
            calc_logger.error(f"CHOICE_ERROR | User: {self.auth_manager.get_current_user()} | "
                        f"Input: '{aString}' | Error: {str(e)} | Execution_Time: {execution_time:.2f}ms")
            
            print(error_msg, e)
            
    def inpControl(self, aString: str):
        """Apply the action from the GUI to the model with comprehensive logging"""
        overall_start_time = time.time()
        operation_type = None
        
        try:
            self.model.setLastInput(aString)
            choice = self.model.getLastChoice()
            
            # Determine operation type
            if choice == 1:
                operation_type = "calculator"
            elif choice == 2:
                operation_type = "fibonacci"
            elif choice == 3:
                operation_type = "factorial"
            
            calc_logger.info(f"CALCULATION_START | Operation: {operation_type} | Input: '{aString}' | Choice: {choice}")
            
            if choice == 1:  # Calculator
                return self._handle_calculator(aString, overall_start_time)
            elif choice == 2:  # Fibonacci
                return self._handle_fibonacci(aString, overall_start_time)
            elif choice == 3:  # Factorial
                return self._handle_factorial(aString, overall_start_time)
            else:
                error_msg = "No operation selected"
                execution_time = (time.time() - overall_start_time) * 1000
                
                calc_logger.warning(f"NO_OPERATION | Choice: {choice} | Input: '{aString}' | "
                                f"Execution_Time: {execution_time:.2f}ms")
                
                return error_msg
                
        except Exception as e:
            execution_time = (time.time() - overall_start_time) * 1000
            error_msg = f"Unexpected error in inpControl: {str(e)}"
            
            calc_logger.error(f"UNEXPECTED_ERROR | Operation: {operation_type} | Input: '{aString}' | "
                            f"Error: {str(e)} | Execution_Time: {execution_time:.2f}ms")
            logger.error(error_msg)
            
            return error_msg

    def _handle_calculator(self, aString: str, overall_start_time: float):
        """Handle calculator operation with detailed logging"""
        calc_start_time = time.time()
        try:
            n = aString.strip()
            
            # Check cache first
            cached_result = self.model.cache.get('calculator', n)
            if cached_result is not None:
                self.model.calculatorOutputView.setText(f"{cached_result} (cached)")
                
                total_time = (time.time() - overall_start_time) * 1000
                calc_logger.info(f"CALCULATION_SUCCESS_CACHED | Operation: calculator | Input: '{n}' | "
                            f"Result: {cached_result} | Total_Time: {total_time:.2f}ms")
                
                return cached_result
            
            # Calculate if not in cache
            result = process_expression(n)
            
            calc_time = (time.time() - calc_start_time) * 1000
            
            # Store in cache
            self.model.cache.set('calculator', n, result)
            
            self.model.calculatorOutputView.setText(str(result))
            
            total_time = (time.time() - overall_start_time) * 1000
            calc_logger.info(f"CALCULATION_SUCCESS | Operation: calculator | Input: '{n}' | "
                        f"Result: {result} | Calc_Time: {calc_time:.2f}ms | Total_Time: {total_time:.2f}ms")
            
            return result
            
        except Exception as e:
            error_msg = "Invalid expression"
            calc_time = (time.time() - calc_start_time) * 1000
            total_time = (time.time() - overall_start_time) * 1000
            
            self.model.calculatorOutputView.setText(error_msg)
            
            calc_logger.error(f"CALCULATION_ERROR | Operation: calculator | Input: '{aString}' | "
                            f"Error: {str(e)} | Calc_Time: {calc_time:.2f}ms | Total_Time: {total_time:.2f}ms")
            logger.error(f"Calculator error for input '{aString}': {e}")
            
            return error_msg
    
    def _handle_fibonacci(self, aString: str, overall_start_time: float):
        """Handle fibonacci operation with detailed logging"""
        calc_start_time = time.time()
        try:
            n = int(aString.strip())
            
            # Check cache first
            cached_result = self.model.cache.get('fibonacci', str(n))
            if cached_result is not None:
                self.model.fibonacciOutputView.setText(f"{cached_result} (cached)")
                
                total_time = (time.time() - overall_start_time) * 1000
                calc_logger.info(f"CALCULATION_SUCCESS_CACHED | Operation: fibonacci | Input: {n} | "
                            f"Result: {cached_result} | Total_Time: {total_time:.2f}ms")
                
                return cached_result
            
            # Calculate if not in cache
            fib = self.fibonnaci(n)
            
            calc_time = (time.time() - calc_start_time) * 1000
            
            # Store in cache
            self.model.cache.set('fibonacci', str(n), fib)
            
            self.model.fibonacciOutputView.setText(str(fib))
            
            total_time = (time.time() - overall_start_time) * 1000
            calc_logger.info(f"CALCULATION_SUCCESS | Operation: fibonacci | Input: {n} | "
                        f"Result: {fib} | Calc_Time: {calc_time:.2f}ms | Total_Time: {total_time:.2f}ms")
            
            return fib
            
        except Exception as e:
            error_msg = "Invalid input"
            calc_time = (time.time() - calc_start_time) * 1000
            total_time = (time.time() - overall_start_time) * 1000
            
            self.model.fibonacciOutputView.setText(error_msg)
            
            calc_logger.error(f"CALCULATION_ERROR | Operation: fibonacci | Input: '{aString}' | "
                            f"Error: {str(e)} | Calc_Time: {calc_time:.2f}ms | Total_Time: {total_time:.2f}ms")
            logger.error(f"Fibonacci error for input '{aString}': {e}")
            
            return error_msg
    
    def _handle_factorial(self, aString: str, overall_start_time: float):
        """Handle factorial operation with detailed logging"""
        calc_start_time = time.time()
        
        try:
            n = int(aString.strip())
            
            # Check cache first
            cached_result = self.model.cache.get('factorial', str(n))
            if cached_result is not None:
                self.model.factorialOutputView.setText(f"{cached_result} (cached)")
                
                total_time = (time.time() - overall_start_time) * 1000
                calc_logger.info(f"CALCULATION_SUCCESS_CACHED | Operation: factorial | Input: {n} | "
                            f"Result: {cached_result} | Total_Time: {total_time:.2f}ms")
                
                return cached_result
            
            # Calculate if not in cache
            factorial_result = self.factorial(n)
            
            calc_time = (time.time() - calc_start_time) * 1000
            
            # Store in cache
            self.model.cache.set('factorial', str(n), factorial_result)
            
            self.model.factorialOutputView.setText(str(factorial_result))
            
            total_time = (time.time() - overall_start_time) * 1000
            calc_logger.info(f"CALCULATION_SUCCESS | Operation: factorial | Input: {n} | "
                        f"Result: {factorial_result} | Calc_Time: {calc_time:.2f}ms | Total_Time: {total_time:.2f}ms")
            
            return factorial_result
            
        except Exception as e:
            error_msg = "Invalid input"
            calc_time = (time.time() - calc_start_time) * 1000
            total_time = (time.time() - overall_start_time) * 1000
            
            self.model.factorialOutputView.setText(error_msg)
            
            calc_logger.error(f"CALCULATION_ERROR | Operation: factorial | Input: '{aString}' | "
                            f"Error: {str(e)} | Calc_Time: {calc_time:.2f}ms | Total_Time: {total_time:.2f}ms")
            logger.error(f"Factorial error for input '{aString}': {e}")
            
            return error_msg

    def fibonnaci(self, n):
        """Fibonacci calculation with logging for large numbers"""
        if n > 100:  # Log performance for large fibonacci numbers
            start_time = time.time()
            logger.info(f"Computing large Fibonacci number: {n}")
        
        # Base condition
        if(n <= 1):
            return n
        
        # Problem broken down into 2 function calls
        last = self.fibonnaci(n - 1)
        slast = self.fibonnaci(n - 2)
        
        result = last + slast
        
        if n > 100:
            execution_time = (time.time() - start_time) * 1000
            logger.info(f"Large Fibonacci {n} computed in {execution_time:.2f}ms")
        
        return result

    def factorial(self, n):
        """Factorial calculation with logging"""
        if n < 0:
            logger.warning(f"Negative factorial requested: {n}")
            return "Error: negative number"
        
        if n > 1000:  # Log for large factorials
            logger.info(f"Computing large factorial: {n}")
        
        P = 1
        for i in range(1, n + 1):
            P *= i
        return P
    
    def calculate(self, operation_type: str, input_value: str, ip_address: str = None, user_agent: str = None):
        """Main calculation method for API calls with comprehensive logging"""
        api_start_time = time.time()
        request_id = None
        
        try:
            # Log API request start
            calc_logger.info(f"API_REQUEST_START | Operation: {operation_type} | Input: '{input_value}' | "
                        f"IP: {ip_address} | User_Agent: {user_agent}")
            
            # Set operation type
            operation_map = {
                'calculator': 1,
                'fibonacci': 2,
                'factorial': 3
            }
            
            if operation_type not in operation_map:
                raise ValueError(f"Invalid operation type: {operation_type}")
            
            # Ensure display views are initialized to prevent 'NoneType' errors
            if self.model.calculatorOutputView is None:
                self.model.setCalculatorView(MyDisplayBox(Point(0, 0), 0, 0))
            if self.model.fibonacciOutputView is None:
                self.model.setFibonacciView(MyDisplayBox(Point(0, 0), 0, 0))
            if self.model.factorialOutputView is None:
                self.model.setFactorialView(MyDisplayBox(Point(0, 0), 0, 0))
            
            # Check cache first
            cached_result = self.model.cache.get(operation_type, input_value)
            if cached_result is not None:
                api_time = (time.time() - api_start_time) * 1000
                
                # Log successful cached request
                request_id = self.db_manager.log_request(
                    operation_type=operation_type,
                    input_value=input_value,
                    result=f"{cached_result} (cached)",
                    status="success_cached",
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                
                calc_logger.info(f"API_REQUEST_SUCCESS_CACHED | Operation: {operation_type} | Input: '{input_value}' | "
                            f"Result: {cached_result} | API_Time: {api_time:.2f}ms | Request_ID: {request_id}")
                
                return {
                    'request_id': request_id,
                    'operation_type': operation_type,
                    'input_value': input_value,
                    'result': cached_result,
                    'cached': True,
                    'status': 'success',
                    'session_id': self.model.get_session_id(),
                    'execution_time_ms': api_time
                }
            
            # Calculate if not cached
            calc_start_time = time.time()
            
            self.chControl(str(operation_map[operation_type]))
            result = self.inpControl(input_value)
            
            calc_time = (time.time() - calc_start_time) * 1000
            
            # Extract the result from the view if it is not returned directly
            if result is None:
                if operation_type == "calculator":
                    result = self.model.calculatorOutputView.getText()
                elif operation_type == "fibonacci":
                    result = self.model.fibonacciOutputView.getText()
                elif operation_type == "factorial":
                    result = self.model.factorialOutputView.getText()
            
            api_time = (time.time() - api_start_time) * 1000
            
            # Log successful request
            request_id = self.db_manager.log_request(
                operation_type=operation_type,
                input_value=input_value,
                result=str(result),
                status="success",
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            calc_logger.info(f"API_REQUEST_SUCCESS | Operation: {operation_type} | Input: '{input_value}' | "
                        f"Result: {result} | Calc_Time: {calc_time:.2f}ms | API_Time: {api_time:.2f}ms | "
                        f"Request_ID: {request_id}")
            
            return {
                'request_id': request_id,
                'operation_type': operation_type,
                'input_value': input_value,
                'result': result,
                'cached': False,
                'status': 'success',
                'session_id': self.model.get_session_id(),
                'execution_time_ms': api_time,
                'calculation_time_ms': calc_time
            }
            
        except Exception as e:
            api_time = (time.time() - api_start_time) * 1000
            error_message = str(e)
            
            # Log failed request
            request_id = self.db_manager.log_request(
                operation_type=operation_type,
                input_value=input_value,
                status="error",
                error_message=error_message,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            calc_logger.error(f"API_REQUEST_ERROR | Operation: {operation_type} | Input: '{input_value}' | "
                            f"Error: {error_message} | API_Time: {api_time:.2f}ms | Request_ID: {request_id}")
            logger.error(f"API Calculation error: {error_message}")
            
            return {
                'request_id': request_id,
                'operation_type': operation_type,
                'input_value': input_value,
                'error': error_message,
                'cached': False,
                'status': 'error',
                'session_id': self.model.get_session_id(),
                'execution_time_ms': api_time
            }

# ----------------------------- VIEW-CONTROLLER ASSOCIATION --------------------

class MyRadioButton:
    _id_counter = 0

    def __init__(self, pos: Point, w: int, h: int, slabel: str):
        self.x = pos.getX()
        self.y = pos.getY()
        self.w = w
        self.h = h
        self.label = slabel
        self.tooltip = "Radio button, only one button is set at a time."
        self.down_box = "FL_ROUND_DOWN_BOX"
        self.id = f"radio{MyRadioButton._id_counter}"
        MyRadioButton._id_counter += 1
        self.controller = None

    def getRenderParams(self):
        return {
            "id": self.id,
            "label": self.label
        }

    def setController(self, aCntrl):
        self.controller = aCntrl

    def radio_button_cb(self):
        if self.controller:
            self.controller.chControl(self.label)

class MyRadioGroup:
    def __init__(self, pos: Point, w: int, h: int, label: str, no: int):
        self.elts = []
        bpos = Point(pos.getX(), pos.getY())
        for i in range(no):
            bpos.setY(pos.getY() + i * 30)
            rb = MyRadioButton(bpos, w, h // no, f"My Choice {i + 1}")
            self.elts.append(rb)

    def getButtons(self):
        return self.elts
    
    def setController(self, aCntrl):
        for rb in self.elts:
            rb.setController(aCntrl)

# ----------------------------- CONNECTION LOGIC ----------------------------------------

class MyWindow:
    def __init__(self, pos: Point, w: int, h: int, title: str):
        if pos is None:
            self.x, self.y = 100, 200
        else:
            self.x, self.y = pos.getX(), pos.getY()
        self.w = w
        self.h = h
        self.title = title
        self.display_box = None
        self.return_button = None
        self.radio_buttons = []
        
        # Store references to all three display boxes
        self.firstdb = None
        self.seconddb = None
        self.thirddb = None

    def addDisplayBox(self, display_box: MyDisplayBox):
        if self.firstdb is None:
            self.firstdb = display_box
        elif self.seconddb is None:
            self.seconddb = display_box
        elif self.thirddb is None:
            self.thirddb = display_box

    def addReturnButton(self, return_button: MyReturnButton):
        self.return_button = return_button
        
    def addRadioButton(self, rb: MyRadioButton):
        self.radio_buttons.append(rb)
    
    def addRadioGroup(self, group):
        self.radio_buttons.extend(group.getButtons())

    def getRenderParams(self):
        params = {
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "title": self.title,
            "first_display_box_text": self.firstdb.getText() if self.firstdb else "",
            "second_display_box_text": self.seconddb.getText() if self.seconddb else "",
            "third_display_box_text": self.thirddb.getText() if self.thirddb else "",
            "label": self.display_box.label if self.display_box else ""
        }
        if self.return_button:
            params.update(self.return_button.getRenderParams())
        if self.radio_buttons:
            params["radio_buttons"] = [rb.getRenderParams() for rb in self.radio_buttons]
        return params

# ----------------------------- FLASK APPLICATION SETUP ---------------------

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
CORS(app)

# Initialize database manager
db_manager = DatabaseManager()

# Initialize GLOBAL cache that persists between requests
global_cache = ExpressionCache()

# ----------------------------- API ENDPOINTS --------------------------------

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    }), 200

@app.route('/api/calculate', methods=['POST'])
def api_calculate():
    """Main calculation endpoint with enhanced logging"""
    request_start_time = time.time()
    client_ip = request.remote_addr
    
    try:
        data = request.get_json()
        
        # Log request received
        logger.info(f"API request received from {client_ip}: {data}")
        
        if not data:
            error_msg = 'No JSON data provided'
            logger.warning(f"Bad request from {client_ip}: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        operation_type = data.get('operation_type')
        input_value = data.get('input_value')
        session_id = data.get('session_id')
        
        if not operation_type or input_value is None:
            error_msg = 'operation_type and input_value are required'
            logger.warning(f"Bad request from {client_ip}: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        # Create model and controller with GLOBAL cache
        model = Model(db_manager, session_id, global_cache)
        controller = Controller(db_manager)
        controller.setModel(model)
        
        # Get client info
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent')
        
        # Perform calculation
        result = controller.calculate(
            operation_type=operation_type,
            input_value=str(input_value),
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        request_time = (time.time() - request_start_time) * 1000
        
        if result['status'] == 'success':
            logger.info(f"API request completed successfully in {request_time:.2f}ms for {client_ip}")
            return jsonify(result), 200
        else:
            logger.warning(f"API request failed in {request_time:.2f}ms for {client_ip}: {result.get('error', 'Unknown error')}")
            return jsonify(result), 400
            
    except Exception as e:
        request_time = (time.time() - request_start_time) * 1000
        error_msg = f'Internal server error: {str(e)}'
        
        logger.error(f"API calculation error in {request_time:.2f}ms for {client_ip}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/calculator', methods=['POST'])
def api_calculator():
    """Calculator-specific endpoint"""
    try:
        data = request.get_json()
        if not data or 'expression' not in data:
            return jsonify({'error': 'expression is required'}), 400
        
        data['operation_type'] = 'calculator'
        data['input_value'] = data.pop('expression')
        
        # Reuse the main calculate endpoint logic
        return api_calculate()
        
    except Exception as e:
        logger.error(f"Calculator API error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/fibonacci', methods=['POST'])
def api_fibonacci():
    """Fibonacci-specific endpoint"""
    try:
        data = request.get_json()
        if not data or 'n' not in data:
            return jsonify({'error': 'n is required'}), 400
        
        data['operation_type'] = 'fibonacci'
        data['input_value'] = data.pop('n')
        
        return api_calculate()
        
    except Exception as e:
        logger.error(f"Fibonacci API error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/factorial', methods=['POST'])
def api_factorial():
    """Factorial-specific endpoint"""
    try:
        data = request.get_json()
        if not data or 'n' not in data:
            return jsonify({'error': 'n is required'}), 400
        
        data['operation_type'] = 'factorial'
        data['input_value'] = data.pop('n')
        
        return api_calculate()
        
    except Exception as e:
        logger.error(f"Factorial API error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/history', methods=['GET'])
def api_history():
    """Get request history with pagination"""
    try:
        limit = min(int(request.args.get('limit', 50)), 1000)  # Max 1000 records
        offset = int(request.args.get('offset', 0))
        
        history = db_manager.get_request_history(limit=limit, offset=offset)
        
        return jsonify({
            'history': history,
            'limit': limit,
            'offset': offset,
            'count': len(history)
        }), 200
        
    except Exception as e:
        logger.error(f"History API error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/analytics', methods=['GET'])
def api_analytics():
    """Get basic analytics"""
    try:
        analytics = db_manager.get_analytics()
        return jsonify(analytics), 200
        
    except Exception as e:
        logger.error(f"Analytics API error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/cache/stats', methods=['GET'])
def api_cache_stats():
    """Get cache statistics"""
    try:
        # Use the global cache for stats
        stats = global_cache.get_stats()
        
        return jsonify({
            'cache_stats': stats,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Cache stats API error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/cache/clear', methods=['POST'])
def api_cache_clear():
    """Clear cache with enhanced logging"""
    request_start_time = time.time()
    client_ip = request.remote_addr
    
    try:
        if request.content_type != 'application/json':
            data = {}
        else:
            data = request.get_json() or {}

        operation_type = data.get('operation_type')  # Optional: clear specific operation
        
        logger.info(f"Cache clear request from {client_ip} for operation: {operation_type or 'all'}")

        # Clear the global cache
        global_cache.clear_cache(operation_type)

        message = f"Cache cleared for {operation_type}" if operation_type else "All caches cleared"
        request_time = (time.time() - request_start_time) * 1000
        
        logger.info(f"Cache clear completed in {request_time:.2f}ms for {client_ip}")

        return jsonify({
            'message': message,
            'timestamp': datetime.utcnow().isoformat(),
            'execution_time_ms': request_time
        }), 200

    except Exception as e:
        request_time = (time.time() - request_start_time) * 1000
        logger.error(f"Cache clear error in {request_time:.2f}ms for {client_ip}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/login', methods=['POST'])
def api_login():
    """API endpoint for authentication"""
    try:
        data = request.get_json()
        
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({'error': 'Username and password are required'}), 400
        
        username = data['username']
        password = data['password']
        
        if auth_manager.verify_credentials(username, password):
            auth_manager.current_user = username
            auth_manager.current_role = auth_manager.users[username]['role']
            
            logger.info(f"API authentication successful for user: {username}")
            
            return jsonify({
                'status': 'success',
                'message': 'Authentication successful',
                'user': username,
                'role': auth_manager.current_role,
                'timestamp': datetime.utcnow().isoformat()
            }), 200
        else:
            logger.warning(f"API authentication failed for user: {username}")
            return jsonify({'error': 'Invalid credentials'}), 401
            
    except Exception as e:
        logger.error(f"Login API error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """API endpoint for logout"""
    try:
        current_user = auth_manager.get_current_user()
        auth_manager.logout()
        
        return jsonify({
            'status': 'success',
            'message': f'User {current_user} logged out successfully',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Logout API error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/auth/status', methods=['GET'])
def api_auth_status():
    """Get current authentication status"""
    try:
        return jsonify({
            'authenticated': auth_manager.is_authenticated(),
            'user': auth_manager.get_current_user(),
            'role': auth_manager.get_current_role(),
            'is_admin': auth_manager.is_admin(),
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Auth status API error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# ----------------------------- ROUTING --------------------------

@app.route("/", methods=["GET", "POST"])
def index():
    posMainWindow = Point(100, 200)
    mainwindow = MyWindow(posMainWindow, 950, 400, "Main Window")

    # Display Boxes
    posFirstDB = Point(100, 50)
    firstdb = MyDisplayBox(posFirstDB, 200, 50, "My display box")

    posSndDB = Point(375, 50)
    seconddb = MyDisplayBox(posSndDB, 200, 50, "Second display")

    posTrdDB = Point(200, 275)
    thirddb = MyDisplayBox(posTrdDB, 250, 50, "Third display")

    firstdb.setText("My first output text.")
    seconddb.setText("My second output text.")
    thirddb.setText("My third output text.")

    mainwindow.addDisplayBox(firstdb)
    mainwindow.addDisplayBox(seconddb)
    mainwindow.addDisplayBox(thirddb)

    # Model and Controller - Use global cache
    model = Model(db_manager, cache=global_cache) 
    model.setCalculatorView(firstdb) # set the calculator view to the first display box
    model.setFibonacciView(seconddb) # set the fibonacci view to the second display box
    model.setFactorialView(thirddb)  # set the factorial view to the third display box

    chCntrl = Controller(db_manager)  # Pass db_manager to Controller
    chCntrl.setModel(model)

    # Radio Group
    posRG = Point(160, 150)
    rg = MyRadioGroup(posRG, 150, 90, "MyChoice", 3)
    rg.setController(chCntrl)
    mainwindow.addRadioGroup(rg)

    # Return Button
    posRet = Point(400, 350)
    ret = MyReturnButton(posRet, 100, 25)
    mainwindow.addReturnButton(ret)

    # Edit Box input
    posEB = Point(400, 130)
    eb = MyEditBox(posEB, 150, 100, "&My Input")
    eb.setText("Initial edit text\nSecond line")

    if request.method == "POST":
        input_text = request.form.get("edit_box", "")
        selected_choice = request.form.get("radio_option", "") # processing the value of the selected radio button
        
        # Process radio button selection
        if selected_choice:
            chCntrl.chControl(selected_choice)
        
        # Enforce permission check before proceeding to inpControl
        operation_type = None
        if selected_choice:
            selected_choice = int(selected_choice)
            if selected_choice == 1:
                operation_type = "calculator"
            elif selected_choice == 2:
                operation_type = "fibonacci"
            elif selected_choice == 3:
                operation_type = "factorial"

        # Check permission only if operation type is known
        error_message = None
        if operation_type:
            permitted, msg = chCntrl.check_permission(operation_type, input_text)
            if not permitted:
                error_message = msg
                # Display error in appropriate output box
                if operation_type == "calculator":
                    firstdb.setText(msg)
                elif operation_type == "fibonacci":
                    seconddb.setText(msg)
                elif operation_type == "factorial":
                    thirddb.setText(msg)
        
        # Proceed if no permission error
        if not error_message:
            chCntrl.inpControl(input_text)
        
        # Set current_input for rendering
        current_input = input_text
        eb.setText(input_text)
    else:
        # For GET requests, use the initial text
        current_input = eb.getText()
        selected_choice = ""
    
    # Prepare render parameters
    render_params = mainwindow.getRenderParams()
    render_params.update({
        "selected_choice": int(selected_choice) if selected_choice else 0,
        "current_input": current_input,
        "first_text": firstdb.getText(),
        "second_text": seconddb.getText(),
        "third_text": thirddb.getText()
    })
    
    return render_template_string(HTML_TEMPLATE, **render_params)

def setup_signal_handlers(auth_manager):
    """Setup signal handlers for graceful shutdown and logout"""
    
    def signal_handler(sig, frame):
        """Handle termination signals and logout user"""
        signal_names = {
            signal.SIGINT: "SIGINT (Ctrl+C)",
            signal.SIGTERM: "SIGTERM (kill)",
        }
        
        signal_name = signal_names.get(sig, f"Signal {sig}")
        current_user = auth_manager.get_current_user()
        
        print(f"\n\n=== {signal_name} received ===")
        
        if current_user:
            print(f"Logging out user: {current_user}")
            auth_manager.logout()
            print("User logged out successfully.")
        else:
            print("No user was logged in.")
        
        print("Shutting down gracefully...")
        print("Goodbye!")
        
        # Exit cleanly
        sys.exit(0)
    
    def cleanup_on_exit():
        """Cleanup function called on normal exit"""
        current_user = auth_manager.get_current_user()
        if current_user:
            print(f"\nCleaning up: logging out user {current_user}")
            auth_manager.logout()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # kill command
    
    # Register cleanup function for normal exit
    atexit.register(cleanup_on_exit)
    
    logger.info("Signal handlers registered for graceful shutdown")

if __name__ == "__main__":
    print("=== Calculator Application with Authentication ===")
    print("Default credentials:")
    print("Admin: username='admin', password='admin123'")
    print("User:  username='user', password='user123'")
    print()
    
    # Remove persisted auth state before authentication
    auth_state_path = os.path.join(os.path.dirname(__file__), '.auth_state.json')
    if os.path.exists(auth_state_path):
        try:
            os.remove(auth_state_path)
            print("Previous authentication state cleared.")
        except Exception as e:
            print(f"Failed to clear previous auth state: {e}")
    
    # Initialize authentication manager
    auth_manager = AuthenticationManager()

    # Console authentication
    auth_success, user_role = auth_manager.authenticate_console()
    
    if not auth_success:
        print("Authentication failed. Exiting...")
        sys.exit(1)
    
    # Setup signal handlers AFTER successful authentication
    setup_signal_handlers(auth_manager)
    
    print(f"\nStarting Flask application with user role: {user_role}")
    print("Server will run on http://127.0.0.1:5000")
    print("Press Ctrl+C to stop the server and logout.")
    
    try:
        app.run(debug=True, use_reloader=False)  # Disable reloader to avoid signal conflicts
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
        auth_manager.logout()
        print("Goodbye!")
    except Exception as e:
        print(f"Server error: {e}")
        auth_manager.logout()
        sys.exit(1)