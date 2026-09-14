import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import pickle

class GoogleCalendarIntegration:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/calendar']
        self.creds_file = 'credentials.json'
        self.token_file = 'token.pickle'
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Calendar API"""
        creds = None
        
        # Load existing token if available
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)
        
        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if os.path.exists(self.creds_file):
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.creds_file, self.SCOPES)
                    creds = flow.run_local_server(port=0)
                else:
                    print("No credentials.json file found. Please download from Google Cloud Console")
                    return
            
            # Save the credentials for the next run
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)
        
        try:
            self.service = build('calendar', 'v3', credentials=creds)
        except Exception as e:
            print(f"Error building calendar service: {e}")
    
    def is_authenticated(self) -> bool:
        """Check if calendar service is authenticated"""
        return self.service is not None
    
    def create_event_from_task(self, task_title: str, deadline: datetime, 
                              description: str = "", duration_hours: float = 1.0) -> Optional[str]:
        """Create a Google Calendar event from a task"""
        if not self.is_authenticated():
            return None
        
        # Calculate end time based on duration
        end_time = deadline + timedelta(hours=duration_hours)
        
        event = {
            'summary': task_title,
            'description': description,
            'start': {
                'dateTime': deadline.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'UTC',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},  # 24 hours before
                    {'method': 'popup', 'minutes': 30},  # 30 minutes before
                ],
            },
        }
        
        try:
            event_result = self.service.events().insert(calendarId='primary', body=event).execute()
            return event_result.get('id')
        except Exception as e:
            print(f"Error creating calendar event: {e}")
            return None
    
    def get_upcoming_events(self, days_ahead: int = 7) -> List[Dict]:
        """Get upcoming events from Google Calendar"""
        if not self.is_authenticated():
            return []
        
        now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        end_time = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + 'Z'
        
        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now,
                timeMax=end_time,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            return events
        except Exception as e:
            print(f"Error fetching calendar events: {e}")
            return []
    
    def check_conflicts(self, task_deadline: datetime, duration_hours: float = 1.0) -> List[Dict]:
        """Check for scheduling conflicts with existing calendar events"""
        if not self.is_authenticated():
            return []
        
        # Get events for the day of the task
        start_of_day = task_deadline.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=start_of_day.isoformat() + 'Z',
                timeMax=end_of_day.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            conflicts = []
            
            task_end = task_deadline + timedelta(hours=duration_hours)
            
            for event in events:
                if 'dateTime' in event['start'] and 'dateTime' in event['end']:
                    event_start = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                    event_end = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                    
                    # Check for overlap
                    if (task_deadline < event_end and task_end > event_start):
                        conflicts.append({
                            'event': event,
                            'conflict_type': 'overlap',
                            'event_start': event_start,
                            'event_end': event_end
                        })
            
            return conflicts
        except Exception as e:
            print(f"Error checking conflicts: {e}")
            return []
    
    def sync_tasks_to_calendar(self, tasks: List[Dict]) -> Dict:
        """Sync multiple tasks to Google Calendar"""
        if not self.is_authenticated():
            return {'success': False, 'message': 'Not authenticated with Google Calendar'}
        
        results = {
            'success': True,
            'synced': [],
            'failed': [],
            'conflicts': []
        }
        
        for task in tasks:
            if not task.get('deadline'):
                continue
            
            # Check for conflicts
            conflicts = self.check_conflicts(
                datetime.fromisoformat(task['deadline']),
                task.get('estimated_duration', 1.0)
            )
            
            if conflicts:
                results['conflicts'].append({
                    'task': task,
                    'conflicts': conflicts
                })
                continue
            
            # Create event
            event_id = self.create_event_from_task(
                task['title'],
                datetime.fromisoformat(task['deadline']),
                task.get('description', ''),
                task.get('estimated_duration', 1.0)
            )
            
            if event_id:
                results['synced'].append({
                    'task_id': task.get('id'),
                    'event_id': event_id,
                    'title': task['title']
                })
            else:
                results['failed'].append({
                    'task_id': task.get('id'),
                    'title': task['title']
                })
        
        return results
    
    def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event"""
        if not self.is_authenticated():
            return False
        
        try:
            self.service.events().delete(calendarId='primary', eventId=event_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting event: {e}")
            return False
    
    def get_calendar_summary(self, days_ahead: int = 7) -> Dict:
        """Get a summary of calendar activity"""
        if not self.is_authenticated():
            return {'authenticated': False}
        
        events = self.get_upcoming_events(days_ahead)
        
        summary = {
            'authenticated': True,
            'total_events': len(events),
            'events_by_day': {},
            'busy_hours': 0,
            'next_event': None
        }
        
        # Group events by day and calculate busy hours
        for event in events:
            if 'dateTime' in event.get('start', {}):
                event_date = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00')).date()
                date_str = event_date.isoformat()
                
                if date_str not in summary['events_by_day']:
                    summary['events_by_day'][date_str] = []
                
                summary['events_by_day'][date_str].append(event)
                
                # Calculate duration
                if 'dateTime' in event.get('end', {}):
                    start_time = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                    end_time = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                    duration = (end_time - start_time).total_seconds() / 3600
                    summary['busy_hours'] += duration
        
        # Find next event
        upcoming_events = [e for e in events if 'dateTime' in e.get('start', {})]
        if upcoming_events:
            upcoming_events.sort(key=lambda x: x['start']['dateTime'])
            summary['next_event'] = upcoming_events[0]
        
        return summary
