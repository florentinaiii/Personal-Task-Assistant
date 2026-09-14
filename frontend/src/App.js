import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { format } from 'date-fns';
import {
  Bot,
  Send,
  Calendar,
  CheckCircle,
  Clock,
  AlertTriangle,
  TrendingUp,
  Trash2,
  LogOut,
} from 'lucide-react';
import Login from './Login';
import './index.css';

function App() {
  const [user, setUser] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [chatMessages, setChatMessages] = useState([]);
  const [currentMessage, setCurrentMessage] = useState('');
  const [schedule, setSchedule] = useState({});
  const [insights, setInsights] = useState({});
  const [activeTab, setActiveTab] = useState('chat');
  const [loading, setLoading] = useState(false);
  const [meetingTitle, setMeetingTitle] = useState('');
  const [meetingDuration, setMeetingDuration] = useState(1.0);
  const [meetingUrgency, setMeetingUrgency] = useState('normal');
  const [meetingSuggestions, setMeetingSuggestions] = useState(null);

  useEffect(() => {
    const savedUser = localStorage.getItem('user');
    if (savedUser) {
      setUser(JSON.parse(savedUser));
    }
  }, []);

  useEffect(() => {
    if (user) {
      fetchTasks();
      fetchSchedule();
      fetchInsights();
    }
  }, [user]);

  const handleLogin = (loggedInUser) => {
    setUser(loggedInUser);
  };

  const handleLogout = () => {
    localStorage.removeItem('user');
    localStorage.removeItem('userEmail');
    setUser(null);
    setTasks([]);
    setChatMessages([]);
    setSchedule({});
    setInsights({});
    setCurrentMessage('');
    setActiveTab('chat');
  };

  const fetchTasks = async () => {
    if (!user) return;

    try {
      const response = await axios.get(
        `/tasks?user_email=${encodeURIComponent(user.email)}`
      );
      setTasks(response.data);
    } catch (error) {
      console.error('Error fetching tasks:', error);
    }
  };

  const fetchSchedule = async () => {
    if (!user) return;

    try {
      const response = await axios.get(
        `/schedule?user_email=${encodeURIComponent(user.email)}`
      );
      setSchedule(response.data);
    } catch (error) {
      console.error('Error fetching schedule:', error);
    }
  };

  const fetchInsights = async () => {
    if (!user) return;

    try {
      const response = await axios.get(
        `/insights?user_email=${encodeURIComponent(user.email)}`
      );
      setInsights(response.data);
    } catch (error) {
      console.error('Error fetching insights:', error);
    }
  };

  const sendMessage = async () => {
    if (!currentMessage.trim() || !user) return;

    const userMessage = { message: currentMessage, sender: 'user' };
    setChatMessages((prev) => [...prev, userMessage]);
    setCurrentMessage('');
    setLoading(true);

    try {
      const response = await axios.post('/chat', {
        message: currentMessage,
        user_email: user.email,
      });

      const assistantMessage = {
        message: response.data.response,
        sender: 'assistant',
        tasksCreated: response.data.tasks_created,
      };

      setChatMessages((prev) => [...prev, assistantMessage]);

      await fetchTasks();
      await fetchSchedule();
      await fetchInsights();
    } catch (error) {
      console.error('Error sending message:', error);

      const errorMessage = {
        message: 'Sorry, I encountered an error. Please try again.',
        sender: 'assistant',
      };

      setChatMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const updateTaskStatus = async (taskId, newStatus) => {
    try {
      await axios.put(`/tasks/${taskId}`, { status: newStatus });
      await fetchTasks();
      await fetchInsights();
      await fetchSchedule();
    } catch (error) {
      console.error('Error updating task:', error);
    }
  };

  const deleteTask = async (taskId) => {
    try {
      await axios.delete(`/tasks/${taskId}`);
      await fetchTasks();
      await fetchInsights();
      await fetchSchedule();
    } catch (error) {
      console.error('Error deleting task:', error);
    }
  };

  const findBestMeetingTime = async () => {
    console.log('findBestMeetingTime called');
    console.log('meetingTitle:', meetingTitle);
    console.log('meetingDuration:', meetingDuration);
    console.log('meetingUrgency:', meetingUrgency);

    if (!meetingTitle.trim()) {
      console.log('Meeting title is empty, returning');
      alert('Please enter a meeting title');
      return;
    }

    setLoading(true);
    try {
      console.log('Sending request to /meeting/best');
      const response = await axios.post('/meeting/best', {
        title: meetingTitle,
        duration_hours: meetingDuration,
        urgency: meetingUrgency,
      });
      console.log('Response received:', response.data);
      setMeetingSuggestions(response.data);
    } catch (error) {
      console.error('Error finding meeting time:', error);
      console.error('Error response:', error.response);
      alert('Failed to find meeting time: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const scheduleMeeting = async () => {
    console.log('scheduleMeeting called');
    console.log('meetingSuggestions:', meetingSuggestions);
    console.log('user:', user);

    if (!meetingSuggestions || !meetingSuggestions.recommended) {
      console.log('No meeting suggestions or not recommended');
      return;
    }

    if (!user || !user.email) {
      console.error('User not logged in or no email');
      alert('Please log in to schedule a meeting');
      return;
    }

    setLoading(true);
    try {
      const taskData = {
        title: meetingSuggestions.title,
        description: `Meeting scheduled via AI scheduler. Reasoning: ${meetingSuggestions.reasoning}`,
        deadline: new Date(meetingSuggestions.start_time).toISOString(),
        priority: 2, // Medium priority for meetings
        estimated_duration: meetingSuggestions.duration_hours,
        category: 'Meeting',
        notification_type: 'email',
      };

      console.log('Sending task data:', taskData);
      console.log('User email:', user.email);

      const response = await axios.post('/tasks', taskData, {
        params: { user_email: user.email }
      });
      console.log('Task created successfully:', response.data);

      await fetchTasks();
      await fetchInsights();
      await fetchSchedule();
      
      // Reset meeting form
      setMeetingTitle('');
      setMeetingSuggestions(null);
      setActiveTab('tasks');
    } catch (error) {
      console.error('Error scheduling meeting:', error);
      console.error('Error response:', error.response);
      alert('Failed to schedule meeting: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const scheduleAlternativeMeeting = async (alternative) => {
    console.log('scheduleAlternativeMeeting called');
    console.log('alternative:', alternative);
    console.log('user:', user);

    if (!user || !user.email) {
      console.error('User not logged in or no email');
      alert('Please log in to schedule a meeting');
      return;
    }

    setLoading(true);
    try {
      const taskData = {
        title: meetingSuggestions.title,
        description: `Meeting scheduled via AI scheduler (alternative option). Score: ${alternative.score}`,
        deadline: new Date(alternative.start_time).toISOString(),
        priority: 2, // Medium priority for meetings
        estimated_duration: alternative.duration_hours,
        category: 'Meeting',
        notification_type: 'email',
      };

      console.log('Sending alternative task data:', taskData);
      console.log('User email:', user.email);

      const response = await axios.post('/tasks', taskData, {
        params: { user_email: user.email }
      });
      console.log('Alternative task created successfully:', response.data);

      await fetchTasks();
      await fetchInsights();
      await fetchSchedule();
      
      // Reset meeting form
      setMeetingTitle('');
      setMeetingSuggestions(null);
      setActiveTab('tasks');
    } catch (error) {
      console.error('Error scheduling alternative meeting:', error);
      console.error('Error response:', error.response);
      alert('Failed to schedule meeting: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 3:
        return 'priority-high';
      case 2:
        return 'priority-medium';
      case 1:
      default:
        return 'priority-low';
    }
  };

  const getPriorityLabel = (priority) => {
    switch (priority) {
      case 3:
        return 'High';
      case 2:
        return 'Medium';
      case 1:
      default:
        return 'Low';
    }
  };

  if (!user) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-3">
              <Bot className="h-8 w-8 text-blue-600" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">AI Task Assistant</h1>
                <p className="text-sm text-gray-500">{user.email}</p>
              </div>
            </div>

            <div className="flex items-center space-x-3">
              <button
                onClick={() => setActiveTab('chat')}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  activeTab === 'chat'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Chat
              </button>

              <button
                onClick={() => setActiveTab('tasks')}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  activeTab === 'tasks'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Tasks
              </button>

              <button
                onClick={() => setActiveTab('schedule')}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  activeTab === 'schedule'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Schedule
              </button>

              <button
                onClick={() => setActiveTab('insights')}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  activeTab === 'insights'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Insights
              </button>

              <button
                onClick={() => setActiveTab('meeting')}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  activeTab === 'meeting'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Meeting
              </button>

              <button
                onClick={handleLogout}
                className="px-4 py-2 rounded-lg font-medium text-red-600 hover:text-red-800 flex items-center space-x-2"
              >
                <LogOut className="h-4 w-4" />
                <span>Logout</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'chat' && (
          <div className="bg-white rounded-lg shadow-sm border">
            <div className="h-96 overflow-y-auto p-4 space-y-4">
              {chatMessages.length === 0 && (
                <div className="text-center text-gray-500 py-8">
                  <Bot className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                  <p>Hello! I'm your AI task assistant. Tell me what you need to do!</p>
                  <p className="text-sm mt-2">
                    Try: "Remind me to send the project tomorrow"
                  </p>
                </div>
              )}

              {chatMessages.map((msg, index) => (
                <div
                  key={index}
                  className={`chat-message ${
                    msg.sender === 'user' ? 'user-message' : 'assistant-message'
                  }`}
                >
                  <div className="flex items-start space-x-2">
                    {msg.sender === 'assistant' && <Bot className="h-5 w-5 mt-1" />}
                    <div>
                      <p className="text-sm">{msg.message}</p>
                      {msg.tasksCreated && msg.tasksCreated.length > 0 && (
                        <div className="mt-2 text-xs opacity-90">
                          Created {msg.tasksCreated.length} task(s)
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}

              {loading && (
                <div className="chat-message assistant-message">
                  <div className="flex items-center space-x-2">
                    <Bot className="h-5 w-5" />
                    <div className="animate-pulse">Thinking...</div>
                  </div>
                </div>
              )}
            </div>

            <div className="border-t p-4">
              <div className="flex space-x-2">
                <input
                  type="text"
                  value={currentMessage}
                  onChange={(e) => setCurrentMessage(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                  placeholder="Tell me what you need to do..."
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={loading}
                />
                <button
                  onClick={sendMessage}
                  disabled={loading || !currentMessage.trim()}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
                >
                  <Send className="h-4 w-4" />
                  <span>Send</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'tasks' && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-semibold text-gray-900">All Tasks</h2>
              <div className="text-sm text-gray-500">
                {tasks.filter((t) => t.status === 'completed').length} / {tasks.length} completed
              </div>
            </div>

            {tasks.length === 0 ? (
              <div className="text-center py-12 bg-white rounded-lg border">
                <CheckCircle className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                <p className="text-gray-500">No tasks yet. Start by chatting with the assistant!</p>
              </div>
            ) : (
              tasks.map((task) => (
                <div
                  key={task.id}
                  className={`task-card ${getPriorityColor(task.priority)} ${
                    task.status === 'completed' ? 'status-completed' : ''
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <h3 className="font-medium text-gray-900">{task.title}</h3>

                      {task.description && (
                        <p className="text-sm text-gray-600 mt-1">{task.description}</p>
                      )}

                      <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                        <span
                          className={`px-2 py-1 rounded-full text-xs font-medium ${
                            task.priority === 3
                              ? 'bg-red-100 text-red-800'
                              : task.priority === 2
                              ? 'bg-yellow-100 text-yellow-800'
                              : 'bg-green-100 text-green-800'
                          }`}
                        >
                          {getPriorityLabel(task.priority)} Priority
                        </span>

                        {task.is_recurring && (
                          <span className="px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                            {task.recurring_pattern || 'Recurring'}
                          </span>
                        )}

                        {task.deadline && (
                          <span className="flex items-center space-x-1">
                            <Calendar className="h-4 w-4" />
                            <span>{format(new Date(task.deadline), 'MMM d, yyyy')}</span>
                          </span>
                        )}

                        {task.estimated_duration && (
                          <span className="flex items-center space-x-1">
                            <Clock className="h-4 w-4" />
                            <span>{task.estimated_duration}h</span>
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center space-x-2 ml-4">
                      {task.status !== 'completed' && (
                        <button
                          onClick={() => updateTaskStatus(task.id, 'completed')}
                          className="text-green-600 hover:text-green-800"
                          title="Mark as complete"
                        >
                          <CheckCircle className="h-5 w-5" />
                        </button>
                      )}

                      <button
                        onClick={() => deleteTask(task.id)}
                        className="text-red-600 hover:text-red-800"
                        title="Delete task"
                      >
                        <Trash2 className="h-5 w-5" />
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'schedule' && (
          <div className="space-y-6">
            <h2 className="text-xl font-semibold text-gray-900">Suggested Schedule</h2>

            {Object.entries(schedule).map(([period, periodTasks]) =>
              Array.isArray(periodTasks) && periodTasks.length > 0 ? (
                <div key={period} className="bg-white rounded-lg border p-4">
                  <h3 className="font-medium text-gray-900 mb-3 capitalize">
                    {period.replace('_', ' ')} ({periodTasks.length} tasks)
                  </h3>

                  <div className="space-y-2">
                    {periodTasks.map((task) => (
                      <div key={task.id} className={`task-card ${getPriorityColor(task.priority)}`}>
                        <div className="flex justify-between items-center">
                          <h4 className="font-medium text-gray-900">{task.title}</h4>
                          {task.deadline && (
                            <span className="text-sm text-gray-500">
                              {format(new Date(task.deadline), 'MMM d, h:mm a')}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null
            )}

            {Object.values(schedule).every(
              (periodTasks) => !Array.isArray(periodTasks) || periodTasks.length === 0
            ) && (
              <div className="text-center py-12 bg-white rounded-lg border">
                <Calendar className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                <p className="text-gray-500">No scheduled tasks. Add some tasks to see your schedule!</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'insights' && (
          <div className="space-y-6">
            <h2 className="text-xl font-semibold text-gray-900">Productivity Insights</h2>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="insight-card">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Completion Rate</p>
                    <p className="text-2xl font-bold text-gray-900">
                      {Math.round((insights.completion_rate || 0) * 100)}%
                    </p>
                  </div>
                  <CheckCircle className="h-8 w-8 text-green-600" />
                </div>
              </div>

              <div className="insight-card">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Avg Duration</p>
                    <p className="text-2xl font-bold text-gray-900">
                      {insights.avg_task_duration ? insights.avg_task_duration.toFixed(1) : '0'}h
                    </p>
                  </div>
                  <Clock className="h-8 w-8 text-blue-600" />
                </div>
              </div>

              <div className="insight-card">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Overdue Tasks</p>
                    <p className="text-2xl font-bold text-red-600">
                      {insights.overdue_count || 0}
                    </p>
                  </div>
                  <AlertTriangle className="h-8 w-8 text-red-600" />
                </div>
              </div>

              <div className="insight-card">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Total Tasks</p>
                    <p className="text-2xl font-bold text-gray-900">{tasks.length}</p>
                  </div>
                  <TrendingUp className="h-8 w-8 text-purple-600" />
                </div>
              </div>
            </div>

            <div className="insight-card">
              <h3 className="font-medium text-gray-900 mb-4">Priority Distribution</h3>
              <div className="space-y-2">
                {Object.entries(insights.priority_distribution || {}).map(([priority, count]) => (
                  <div key={priority} className="flex justify-between items-center">
                    <span
                      className={`px-2 py-1 rounded-full text-xs font-medium ${
                        priority == 3
                          ? 'bg-red-100 text-red-800'
                          : priority == 2
                          ? 'bg-yellow-100 text-yellow-800'
                          : 'bg-green-100 text-green-800'
                      }`}
                    >
                      {priority == 3 ? 'High' : priority == 2 ? 'Medium' : 'Low'} Priority
                    </span>
                    <span className="font-medium">{count} tasks</span>
                  </div>
                ))}
              </div>
            </div>

            {insights.upcoming_deadlines && insights.upcoming_deadlines.length > 0 && (
              <div className="insight-card">
                <h3 className="font-medium text-gray-900 mb-4">Upcoming Deadlines</h3>
                <div className="space-y-2">
                  {insights.upcoming_deadlines.map((task) => (
                    <div key={task.id} className={`task-card ${getPriorityColor(task.priority)}`}>
                      <div className="flex justify-between items-center">
                        <h4 className="font-medium text-gray-900">{task.title}</h4>
                        <span className="text-sm text-red-600 font-medium">
                          {format(new Date(task.deadline), 'MMM d, h:mm a')}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'meeting' && (
          <div className="space-y-6">
            <h2 className="text-xl font-semibold text-gray-900">Meeting Scheduler</h2>

            <div className="bg-white rounded-lg border p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Meeting Title
                </label>
                <input
                  type="text"
                  value={meetingTitle}
                  onChange={(e) => setMeetingTitle(e.target.value)}
                  placeholder="e.g., Team Standup"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Duration (hours)
                  </label>
                  <select
                    value={meetingDuration}
                    onChange={(e) => setMeetingDuration(parseFloat(e.target.value))}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="0.5">0.5 hours (30 min)</option>
                    <option value="1.0">1.0 hours</option>
                    <option value="1.5">1.5 hours</option>
                    <option value="2.0">2.0 hours</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Urgency
                  </label>
                  <select
                    value={meetingUrgency}
                    onChange={(e) => setMeetingUrgency(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="normal">Normal (2 weeks)</option>
                    <option value="urgent">Urgent (3 days)</option>
                    <option value="flexible">Flexible (3 weeks)</option>
                  </select>
                </div>
              </div>

              <button
                onClick={findBestMeetingTime}
                disabled={loading || !meetingTitle.trim()}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Finding best time...' : 'Find Best Meeting Time'}
              </button>
            </div>

            {meetingSuggestions && (
              <div className="bg-white rounded-lg border p-6">
                <h3 className="font-medium text-gray-900 mb-4">Recommended Meeting Time</h3>
                
                {meetingSuggestions.recommended ? (
                  <div className="space-y-4">
                    <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                      <div className="flex items-center space-x-2 mb-2">
                        <CheckCircle className="h-5 w-5 text-green-600" />
                        <span className="font-medium text-green-900">
                          {meetingSuggestions.title}
                        </span>
                      </div>
                      <div className="text-sm text-green-800 space-y-1">
                        <p><strong>Date:</strong> {new Date(meetingSuggestions.date).toLocaleDateString()}</p>
                        <p><strong>Start:</strong> {new Date(meetingSuggestions.start_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</p>
                        <p><strong>End:</strong> {new Date(meetingSuggestions.end_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</p>
                        <p><strong>Duration:</strong> {meetingSuggestions.duration_hours} hours</p>
                        <p><strong>Reasoning:</strong> {meetingSuggestions.reasoning}</p>
                      </div>
                      <button
                        onClick={scheduleMeeting}
                        disabled={loading}
                        className="mt-3 w-full px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {loading ? 'Scheduling...' : 'Schedule This Meeting'}
                      </button>
                    </div>

                    {meetingSuggestions.alternatives && meetingSuggestions.alternatives.length > 0 && (
                      <div>
                        <h4 className="font-medium text-gray-900 mb-2">Alternative Options</h4>
                        <div className="space-y-2">
                          {meetingSuggestions.alternatives.map((alt, idx) => (
                            <div key={idx} className="bg-gray-50 border border-gray-200 rounded-lg p-3">
                              <div className="flex justify-between items-center">
                                <div>
                                  <p className="text-sm font-medium">{new Date(alt.date).toLocaleDateString()} at {new Date(alt.start_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</p>
                                  <p className="text-xs text-gray-500">Score: {alt.score}</p>
                                </div>
                                <button
                                  onClick={() => scheduleAlternativeMeeting(alt)}
                                  disabled={loading}
                                  className="px-3 py-1 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  Schedule
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                    <p className="text-yellow-800">{meetingSuggestions.reasoning}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;