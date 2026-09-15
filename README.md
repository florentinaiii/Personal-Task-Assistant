# AI Personal Task Management Assistant

An AI-based personal assistant designed to help users create, organize, schedule, and manage daily tasks through natural language.

The application combines a FastAPI backend, React frontend, rule-based task processing, and spaCy-based Natural Language Processing (NLP) to transform conversational user input into structured tasks.

## Features

- **Natural Language Task Creation** – Create tasks using conversational commands instead of manually filling out forms.
- **Hybrid NLP Processing** – Uses spaCy together with deterministic parsing rules to extract task actions, deadlines, priorities, recurrence patterns, and reminder information.
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
- **Multi-User Support** – Tasks and reminders are associated with individual user accounts.
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
│   ├── planner.py
│   ├── db.py
│   ├── calendar_integration.py
│   ├── notifications.py
│   ├── email_service.py
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.js
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
- SQLite
- spaCy
- WebSockets
- Brevo API
- Google Calendar API

### Frontend

- React
- Tailwind CSS
- Lucide Icons

### Natural Language Processing

The task parser uses a hybrid NLP approach:

- **spaCy** for identifying the main task action and producing concise task titles.
- **Regular expressions and deterministic rules** for detecting dates, times, deadlines, priorities, recurrence patterns, reminder intervals, and other structured task information.

The current implementation does not require an external Large Language Model API for task parsing.

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

For email reminders using Brevo:

```env
BREVO_API_KEY=your_brevo_api_key
BREVO_SENDER_EMAIL=your_verified_sender_email
BREVO_SENDER_NAME=Personal Task Assistant
```

Do not commit real API keys or credentials to GitHub.

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

Users can create tasks through conversational commands.

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

The assistant extracts structured information such as:

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

The parser recognizes several types of natural-language information.

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

Email reminders are associated with the user who created the task.

## Main Application Modules

### Task Parser

`parser.py` converts conversational text into structured task data.

Its responsibilities include:

- Action/title extraction
- Deadline detection
- Priority detection
- Duration extraction
- Recurrence detection
- Reminder extraction
- Multiple-time task processing

### Task Planner

`planner.py` contains the application's scheduling and task-planning logic.

### Notifications

`notifications.py` manages reminder processing and notification logic.

### Email Service

`email_service.py` handles transactional reminder emails through the Brevo API.

### Database

The application uses SQLAlchemy with SQLite for local data persistence.

### Frontend

The React frontend provides the user interface for interacting with the assistant, managing tasks, viewing schedules, and accessing productivity information.

## Deployment

The application can also be deployed as separate backend and frontend services.

When deploying the backend, make sure that:

- All Python dependencies are installed.
- The spaCy `en_core_web_sm` model is installed.
- Required environment variables are configured securely.
- API keys are never stored directly in the repository.

A deployment build command may include:

```bash
pip install -r requirements.txt && python -m spacy download en_core_web_sm
```

A production backend start command can use:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Testing

The system can be evaluated with multiple users over several days.

Testing can focus on:

- Accuracy of natural-language task recognition
- Correct extraction of deadlines
- Correct extraction of priorities
- Reminder reliability
- Recurring-task handling
- Usability of the interface
- Scheduling functionality
- Overall usefulness for daily task management

## Future Improvements

Possible future improvements include:

- Integration with additional calendar services
- Mobile application development
- Large Language Model integration for more advanced conversational understanding
- Voice input
- Team collaboration
- More advanced scheduling algorithms
- Expanded productivity analytics
- Additional notification channels
- PostgreSQL support for larger deployments

## Academic Context

This project was developed as part of a Master's thesis focused on the development of an autonomous artificial-intelligence-based personal assistant for managing daily tasks.

The system explores how Natural Language Processing, automated scheduling, reminders, and adaptive task-management mechanisms can be combined into a practical personal productivity assistant.

## License

This project was developed for academic and research purposes.