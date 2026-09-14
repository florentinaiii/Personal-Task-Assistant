# AI Personal Task Management Assistant

An autonomous AI-based personal assistant for daily task management, built with FastAPI backend and React frontend.

## Features

- **Natural Language Processing**: Parse tasks from natural language input
- **Intelligent Prioritization**: Automatic task prioritization based on deadlines and importance
- **Smart Scheduling**: AI-powered schedule suggestions and conflict detection
- **Google Calendar Integration**: Sync tasks with Google Calendar
- **Real-time Notifications**: WebSocket-based notifications for reminders and updates
- **Productivity Insights**: Analytics and insights about task completion patterns
- **Modern UI**: Clean, responsive React interface with Tailwind CSS

## Architecture

```
project/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── models.py            # Database models
│   ├── parser.py            # NLP task parser
│   ├── planner.py           # Task planning algorithm
│   ├── db.py               # Database setup
│   ├── calendar_integration.py  # Google Calendar integration
│   ├── notifications.py    # Real-time notifications
│   └── requirements.txt     # Python dependencies
│
├── frontend/
│   ├── src/
│   │   ├── App.js          # Main React component
│   │   ├── index.js        # React entry point
│   │   └── index.css       # Tailwind CSS styles
│   ├── public/
│   │   └── index.html      # HTML template
│   ├── package.json        # Node.js dependencies
│   └── tailwind.config.js  # Tailwind configuration
│
└── README.md
```

## Installation

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv
```

3. Activate the virtual environment:
- Windows: `venv\Scripts\activate`
- macOS/Linux: `source venv/bin/activate`

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Set up Google Calendar (optional):
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project
   - Enable Google Calendar API
   - Create OAuth 2.0 credentials
   - Download `credentials.json` and place it in the backend directory

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

## Usage

### Starting the Application

1. Start the backend server:
```bash
cd backend
python main.py
```

2. Start the frontend development server:
```bash
cd frontend
npm start
```

3. Open your browser and navigate to `http://localhost:3000`

### Using the Assistant

1. **Chat Interface**: Simply type natural language commands like:
   - "Remind me to send the project tomorrow"
   - "I need to finish the report by Friday"
   - "Schedule a meeting for next week"

2. **Task Management**: View, edit, and complete tasks in the Tasks tab

3. **Schedule Planning**: See AI-generated schedule suggestions in the Schedule tab

4. **Productivity Insights**: Track your productivity patterns in the Insights tab

5. **Calendar Sync**: Connect to Google Calendar to sync tasks

## API Endpoints

### Tasks
- `GET /tasks` - Get all tasks
- `POST /tasks` - Create a new task
- `GET /tasks/{id}` - Get a specific task
- `PUT /tasks/{id}` - Update a task
- `DELETE /tasks/{id}` - Delete a task

### Chat
- `POST /chat` - Send a message to the AI assistant

### Schedule
- `GET /schedule` - Get suggested schedule
- `GET /conflicts` - Get scheduling conflicts
- `POST /auto-reschedule` - Auto-reschedule tasks

### Insights
- `GET /insights` - Get productivity insights

### Google Calendar
- `GET /calendar/status` - Check authentication status
- `GET /calendar/events` - Get calendar events
- `POST /calendar/sync` - Sync tasks to calendar
- `GET /calendar/summary` - Get calendar summary

### WebSocket
- `WS /ws` - Real-time notifications

## Natural Language Processing

The system can understand various natural language patterns:

**Time expressions:**
- "tomorrow", "today", "next week", "next month"
- "in 3 days", "in 2 hours"
- "by 5pm", "by Friday"
- "on March 15", "on 15/03/2024"

**Priority indicators:**
- "urgent", "asap", "immediately" → High priority
- "important", "high", "soon" → Medium priority
- "low", "later", "sometime" → Low priority

**Duration:**
- "2 hours", "30 minutes", "1h"

## Testing

The system is designed for testing with 3-5 users over several days to evaluate:
- Usability of the interface
- Accuracy of task recognition
- Effectiveness of prioritization
- Overall usefulness in daily task management

## Technologies Used

- **Backend**: Python, FastAPI, SQLAlchemy, SQLite
- **Frontend**: React, Tailwind CSS, Lucide Icons
- **AI/NLP**: Custom parser with spaCy integration
- **Real-time**: WebSocket notifications
- **Calendar**: Google Calendar API
- **Database**: SQLite (easily upgradeable to PostgreSQL)

## Future Improvements

- Integration with more calendar services (Outlook, Apple Calendar)
- Mobile app development
- Advanced AI features using OpenAI GPT
- Team collaboration features
- Email integration
- Voice input support
- Advanced analytics and reporting

## License

This project is part of a thesis on autonomous AI-based personal assistants for daily task management.
