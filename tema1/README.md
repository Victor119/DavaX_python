<pre lang="markdown"> ## Project Structure ```
TEMA1/
    ├── __pycache__/
    ├── data/                     # has file SQLite `calculator_api.db`
    ├── logs/                    # log directory
    │   ├── calculations.log
    │   ├── calculator_app.log
    │   └── errors.log
    ├── python_calculator/       # for mathematical expressions
    ├── .dockerignore
    ├── compose.yaml             # Config Docker Compose
    ├── dockerfile               # Dockerfile for containerization
    ├── main.py                  # Flask main application + web UI logic
    ├── requirements.txt         # Python dependencies
    ├── test_api_script.py       # API test script (automation)
``` </pre>

Key Features
1. Authentication
    Predefined users: admin / user

    Passwords are hashed using SHA-256

    Session persistence in .auth_state.json

    CLI-based authentication and support for environment variables in container mode

2. Operations
    Three types of calculations are supported:

    calculator – mathematical expressions (e.g., 2+2, sqrt(16))

    fibonacci – the n-th Fibonacci number

    factorial – the factorial of an integer

3. Caching
    Results are cached in memory for speed

    Types: calculator, fibonacci, factorial

    Statistics available via /api/cache/stats

    Dedicated endpoint for clearing: /api/cache/clear

4. Persistence via SQLite
    Two tables:

        api_requests: logs for every API request (with timestamp, IP, user-agent, etc.)

        user_sessions: stores the user's last selection and input

5. Complete RESTful API
    POST /api/calculate – main endpoint

    POST /api/calculator, /api/fibonacci, /api/factorial – specialized endpoints

    GET /api/health – health check

    GET /api/history – request history

    GET /api/analytics – usage statistics

    GET /api/cache/stats, POST /api/cache/clear – cache management

Automated Testing – test_api_script.py
    This script includes:

    Health check tests (/api/health)

    History verification (/api/history)

    Analytics validation (/api/analytics)

    Cache functionality tests (hit/miss)

    Endpoint-specific validation

Running the script confirms the full functionality of the application.

Web Interface (HTML Template)
Minimalist web UI with:

    Three output boxes (calculator, fibonacci, factorial)

    Radio button group for selecting the operation

    Text area for input

    &Return button (form submission)

    Results are dynamically displayed on screen

Each component has an associated Python class: MyDisplayBox, MyReturnButton, MyEditBox, MyRadioGroup

Dockerization
    dockerfile (assumed content)
    Includes standard steps:

    Copy source code

    Install dependencies (requirements.txt)

    Expose ports

    Run main.py

compose.yaml
Runs the application with:

    Flask binds to 0.0.0.0:5000 inside the container, which allows external access.
    You should open http://localhost:5000 in your browser.

    Volumes for data/ and logs/ for persistence

    Optional environment variables for username/password

