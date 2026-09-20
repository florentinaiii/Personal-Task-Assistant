# AI Personal Task Management Assistant

An AI-based personal assistant designed to help users create, organize, schedule, and manage daily tasks through natural language.

The application combines a FastAPI backend, React frontend, hybrid AI/NLP task processing, automated scheduling, secure user authentication, reminders, and productivity tools to transform conversational user input into structured and manageable tasks.

## Features

- **Natural Language Task Creation** – Create tasks using conversational commands instead of manually filling out forms.

- **Hybrid AI/NLP Processing** – Uses Google Gemini together with deterministic spaCy and rule-based parsing to interpret natural-language requests. If the Gemini API is unavailable or not configured, the system can continue using the deterministic fallback parser.

- **Secure User Authentication** – Supports account registration and login using email and password, with password hashing and JWT-based authentication.

- **User-Specific Task Access** – Tasks are associated with authenticated users so that each user can access and manage only their own tasks.

- **Task Management** – Create, view, update, complete, and delete personal tasks.

- **Task Prioritization** – Detects priority indicators such as urgent, important, high, or low.

- **Smart Scheduling** – Organizes tasks based on deadlines, priorities, and scheduling information.

- **Recurring Tasks** – Supports daily, weekly, biweekly, monthly, and multiple-times-per-day task patterns.

- **Automatic Rescheduling** – Supports reorganization of scheduled tasks when necessary.

- **Meeting Scheduler** – Helps determine suitable meeting times within the application's scheduling logic.

- **Email Reminders** – Sends task reminders through email using Brevo.

- **Real-Time Notifications** – WebSocket-based communication for real-time application updates.

- **Google Calendar Integration** – Optional integration for calendar functionality.

- **Productivity Insights** – Provides information about task completion and productivity patterns.

- **Multi-User Support** – Tasks and reminders are associated with individual authenticated user accounts.

- **Responsive Interface** – React-based interface styled with Tailwind CSS.

## System Architecture

The project consists of two main components:

```text
project/
│
├── backend/
│   ├── main.py
│   ├── models.py
│   ├── parser.py
│   ├── llm_parser.py
│   ├── planner.py
│   ├── db.py
│   ├── auth.py
│   ├── calendar_integration.py
│   ├── notifications.py
│   ├── email_service.py
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.js
│   │   ├── Login.js
│   │   ├── index.js
│   │   └── index.css
│   ├── public/
│   │   └── index.html
│   ├── package.json
│   └── tailwind.config.js
│
└── README.md
```

## Technologies Used

### Backend

- Python
- FastAPI
- SQLAlchemy
- SQLite for local development
- PostgreSQL / Neon for production
- Google Gemini API
- spaCy
- Regular expressions and deterministic parsing rules
- JWT authentication
- Password hashing
- WebSockets
- Brevo API
- Google Calendar API

### Frontend

- React
- Tailwind CSS
- Lucide Icons
- Axios

### AI and Natural Language Processing

The task-processing system uses a hybrid approach.

- **Google Gemini** is used for AI-assisted interpretation of conversational task requests.
- **spaCy** supports Natural Language Processing and task-title extraction.
- **Regular expressions and deterministic rules** detect structured information such as dates, times, deadlines, priorities, recurrence patterns, and reminder information.
- **Fallback processing** allows the application to continue parsing supported task requests even when the Gemini API is unavailable or not configured.

This hybrid architecture combines the flexibility of an AI model with deterministic processing for predictable task-management operations.

## Authentication and Security

The application uses authenticated user accounts to protect personal task data.

Users register with:

```text
Email
Password
```

Passwords are stored as secure password hashes rather than plain-text passwords.

After successful registration or login, the backend generates a JSON Web Token (JWT). The frontend includes this token in authenticated API requests.

Protected backend operations identify the current user from the authentication token rather than trusting a user email supplied by the client.

This ensures that task-management operations are associated with the authenticated account and prevents one user from accessing another user's tasks through task API requests.

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/florentinaiii/Personal-Task-Assistant.git
cd Personal-Task-Assistant
```

## Backend Setup

Navigate to the backend directory:

```bash
cd backend
```

Create a Python virtual environment:

```bash
python -m venv venv
```

Activate the environment.

### Windows

```bash
venv\Scripts\activate
```

### macOS/Linux

```bash
source venv/bin/activate
```

Install the Python dependencies:

```bash
python -m pip install -r requirements.txt
```

Install the required spaCy English model:

```bash
python -m spacy download en_core_web_sm
```

## Environment Variables

Create a `.env` file inside the `backend` directory.

The application supports the following environment variables:

```env
# Gemini AI
# Optional. If omitted or unavailable, supported requests can use
# the deterministic spaCy/rule-based fallback.
GEMINI_API_KEY=your_gemini_api_key_here

# Database
# Leave empty or use the local SQLite configuration during development.
# Production can use a PostgreSQL connection string.
DATABASE_URL=your_database_url_here

# Authentication
# Use a long, private, randomly generated value.
JWT_SECRET_KEY=your_long_random_secret_here

# Brevo Email Reminders
BREVO_API_KEY=your_brevo_api_key_here
BREVO_SENDER_EMAIL=your_verified_sender_email@example.com
BREVO_SENDER_NAME=Personal Task Assistant
```

Do not commit the real `.env` file, API keys, database credentials, passwords, JWT secrets, or other private credentials to GitHub.

An `.env.example` file can be included in the repository using placeholder values only.

## Database

The application uses SQLAlchemy for database access.

For local development, the application can use:

```text
SQLite
```

For the deployed production environment, the application supports:

```text
PostgreSQL
```

The production deployment uses a persistent PostgreSQL database hosted with Neon.

The database stores application information such as:

- Users
- Password hashes
- Tasks
- Deadlines
- Priorities
- Recurrence information
- Reminder information
- Task status

Each task is associated with a user account.

## Google Calendar Setup

Google Calendar integration is optional.

To configure it:

1. Open Google Cloud Console.
2. Create or select a Google Cloud project.
3. Enable the Google Calendar API.
4. Configure OAuth 2.0 credentials.
5. Download the required credentials file.
6. Place the credentials in the backend directory according to the application's calendar configuration.

The core task-management functionality can run without Google Calendar credentials.

## Running the Application

### Start the Backend

From the `backend` directory:

```bash
python -m uvicorn main:app --reload
```

The backend will normally be available at:

```text
http://127.0.0.1:8000
```

FastAPI interactive API documentation can normally be accessed at:

```text
http://127.0.0.1:8000/docs
```

### Start the Frontend

Open another terminal and navigate to the frontend directory:

```bash
cd frontend
```

Install the dependencies if they have not already been installed:

```bash
npm install
```

Start the React development server:

```bash
npm start
```

The frontend will normally open at:

```text
http://localhost:3000
```

## Using the Assistant

Users first create an account or sign in with their existing credentials.

After authentication, tasks can be created through conversational commands.

Examples:

```text
I need to buy groceries tomorrow at 6pm
```

```text
Remind me to drink tea after 10 minutes
```

```text
I need to pray by 8:15pm, remind me
```

```text
I need to finish the report tomorrow at 5pm, it is important
```

The assistant can extract structured information such as:

```text
Title
Deadline
Priority
Estimated duration
Reminder
Recurrence
Notification type
```

For example:

```text
Input:
I need to pray by 8:15pm, remind me

Parsed task:
Title: Pray
Deadline: 8:15 PM
Notification: Email reminder
```

## Natural Language Processing

The assistant recognizes several types of natural-language information.

### Relative Time

Examples:

```text
in 10 minutes
after 10 minutes
in 2 hours
after 2 hours
in 3 days
```

### Dates and Deadlines

Examples:

```text
today
tomorrow
tomorrow at 6pm
next Monday
March 15
15/03/2026
by 8:15pm
```

### Priority

Examples:

```text
urgent
asap
immediately
critical
very important
important
high
soon
low
later
sometime
```

These expressions are converted into the application's internal priority levels.

### Recurring Tasks

The system recognizes recurring expressions such as:

```text
every day
daily
each day
every week
weekly
every two weeks
biweekly
every month
monthly
```

It also supports multiple task times in a single request, for example:

```text
I need to pray 5 times per day, remind me by 5am, 2:30pm, 6pm, 7:45pm and 10pm
```

### Reminders

Reminder information can be extracted from expressions such as:

```text
remind me
remind me 10 minutes before
remind me 1 hour before
remind me at 5pm
```

Email reminders are associated with the authenticated user who created the task.

## Main Application Modules

### Task Parser

`parser.py` and `llm_parser.py` process conversational text and convert it into structured task data.

Their responsibilities include:

- AI-assisted task interpretation
- Action/title extraction
- Deadline detection
- Priority detection
- Duration extraction
- Recurrence detection
- Reminder extraction
- Multiple-time task processing
- Deterministic fallback processing

### Authentication

`auth.py` manages authentication-related functionality including:

- Password hashing and verification
- JWT creation
- JWT validation
- Identification of the authenticated user

### Task Planner

`planner.py` contains the application's scheduling and task-planning logic.

### Notifications

`notifications.py` manages reminder processing and notification logic.

### Email Service

`email_service.py` handles transactional reminder emails through the Brevo API.

### Database

`db.py` configures the SQLAlchemy database connection and supports local SQLite and production PostgreSQL environments.

### Frontend

The React frontend provides the user interface for:

- Account registration and login
- Conversational task creation
- Task management
- Schedule viewing
- Meeting scheduling
- Productivity insights
- Reminder-related functionality

Authenticated API requests include the user's JWT access token.

## Deployment

The application is deployed using separate frontend and backend services on Render.

### Backend

The production backend requires:

- Python dependencies from `requirements.txt`
- The spaCy `en_core_web_sm` model
- Production environment variables
- PostgreSQL database access
- A secure JWT secret
- Brevo configuration for email reminders
- Gemini configuration when AI-assisted parsing is enabled

A deployment build command may include:

```bash
pip install -r requirements.txt && python -m spacy download en_core_web_sm
```

A production backend start command can use:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Frontend

The frontend uses the backend API URL through its environment configuration.

Example:

```env
REACT_APP_API_URL=https://your-backend-service.onrender.com
```

API keys and authentication secrets must not be placed in frontend environment variables.

## Testing

Automated parser tests are implemented using `pytest`.

The current parser test suite contains 10 tests covering important task-processing scenarios, including:

- Explicit times
- Relative dates
- Relative dates with times
- 12-hour time formats
- Minute-specific times
- Rejection of past times for the current day
- Multi-day relative expressions
- Recurring weekly tasks
- Correct scheduling of recurring tasks into the future

Run the automated tests from the backend directory with:

```bash
python -m pytest -v
```

Current verified result:

```text
10 passed
```

The application has also been tested through its user interface for task creation, deadlines, relative-time requests, recurring tasks, authentication, user-specific task access, and email reminders.

## Production Architecture

The deployed application uses:

```text
React Frontend
      ↓
FastAPI Backend
      ↓
Authentication / JWT
      ↓
Hybrid Gemini + Deterministic Task Processing
      ↓
SQLAlchemy
      ↓
Neon PostgreSQL
```

Additional services include:

```text
Brevo → Email reminders
Google Calendar → Optional calendar integration
WebSockets → Real-time application communication
```

## Future Improvements

Possible future improvements include:

- Integration with additional calendar services
- Mobile application development
- Voice input
- Team collaboration
- More advanced scheduling algorithms
- Expanded productivity analytics
- Additional notification channels
- More advanced adaptive AI-based personalization

## Academic Context

This project was developed as part of an academic thesis focused on the development of an autonomous artificial-intelligence-based personal assistant for managing daily tasks.

The system explores how Artificial Intelligence, Natural Language Processing, automated scheduling, authentication, reminders, recurring-task management, and adaptive task-management mechanisms can be combined into a practical personal productivity assistant.

## License

This project was developed for academic and research purposes.