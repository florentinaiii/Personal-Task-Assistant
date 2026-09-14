import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { format } from 'date-fns';

const API_URL =
  process.env.REACT_APP_API_URL || 'http://localhost:8001';

axios.defaults.baseURL = API_URL;
import {
  Send,
  Calendar,
  CheckCircle,
  Clock,
  AlertTriangle,
  TrendingUp,
  Trash2,
  LogOut,
  ArrowRight,
  Sparkles,
} from 'lucide-react';
import Login from './Login';
import './index.css';
import robot from './assets/robot.png';
import logo from './assets/logo.png';


const robotAvatar = '/robot-reference.png';

function App() {
  const [user, setUser] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [chatMessages, setChatMessages] = useState([]);
  const [currentMessage, setCurrentMessage] = useState('');
  const [schedule, setSchedule] = useState({});
  const [insights, setInsights] = useState({});
  const [activeTab, setActiveTab] = useState('chat');
  const [loading, setLoading] = useState(false);
  const [showTypingIndicator, setShowTypingIndicator] = useState(false);
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

  useEffect(() => {
    const chatContainer = document.getElementById('chat-container');
    if (chatContainer) {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }
  }, [chatMessages, showTypingIndicator]);

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
    setShowTypingIndicator(true);
    const startTime = Date.now();

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

      // Ensure minimum typing indicator duration (700-1000ms)
      const typingDuration = Date.now() - startTime;
      const minTypingDuration = 800;
      const remainingDelay = Math.max(0, minTypingDuration - typingDuration);

      setTimeout(async () => {
        setShowTypingIndicator(false);
        setChatMessages((prev) => [...prev, assistantMessage]);
        setLoading(false);
        
        // Refresh data after showing the message
        await fetchTasks();
        await fetchSchedule();
        await fetchInsights();
      }, remainingDelay);
    } catch (error) {
      console.error('Error sending message:', error);

      const errorMessage = {
        message: 'Sorry, I encountered an error. Please try again.',
        sender: 'assistant',
      };

      // Ensure minimum typing indicator duration even for errors
      const typingDuration = Date.now() - startTime;
      const minTypingDuration = 800;
      const remainingDelay = Math.max(0, minTypingDuration - typingDuration);

      setTimeout(() => {
        setShowTypingIndicator(false);
        setChatMessages((prev) => [...prev, errorMessage]);
        setLoading(false);
      }, remainingDelay);
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
      <div
            className="min-h-screen lg:h-screen lg:flex lg:flex-col lg:overflow-hidden"
            style={{ backgroundColor: '#FAF8FF' }}
      >
      {/* HEADER */}
      <header className="bg-white shadow-sm border-b border-purple-100 lg:flex-shrink-0">
        <div className="w-full px-6 sm:px-8 lg:px-10 xl:px-12">
          <div className="flex flex-col sm:flex-row justify-between items-center py-4 space-y-4 sm:space-y-0">
            <div className="flex items-center space-x-3">
              <img
                src={logo}
                alt="AI Assistant"
                className="w-10 h-10 rounded-full object-cover"
                style={{
                  background: 'linear-gradient(135deg, #F3EEFF, #E8D9FF)',
                }}
              />

              <div>
                <h1
                  className="text-xl sm:text-2xl font-bold"
                  style={{ color: '#17143D' }}
                >
                  AI Task Assistant
                </h1>

                <p
                  className="text-xs sm:text-sm"
                  style={{ color: '#9B4DE3' }}
                >
                  {user.email}
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-2 sm:space-x-3 overflow-x-auto">
              <button
                onClick={() => setActiveTab('chat')}
                className={`px-3 sm:px-4 py-2 rounded-lg font-medium transition-colors text-sm sm:text-base ${
                  activeTab === 'chat' ? 'text-white' : ''
                }`}
                style={
                  activeTab === 'chat'
                    ? { backgroundColor: '#7C2BD1' }
                    : { color: '#9B4DE3' }
                }
              >
                Chat
              </button>

              <button
                onClick={() => setActiveTab('tasks')}
                className={`px-3 sm:px-4 py-2 rounded-lg font-medium transition-colors text-sm sm:text-base ${
                  activeTab === 'tasks' ? 'text-white' : ''
                }`}
                style={
                  activeTab === 'tasks'
                    ? { backgroundColor: '#7C2BD1' }
                    : { color: '#9B4DE3' }
                }
              >
                Tasks
              </button>

              <button
                onClick={() => setActiveTab('schedule')}
                className={`px-3 sm:px-4 py-2 rounded-lg font-medium transition-colors text-sm sm:text-base ${
                  activeTab === 'schedule' ? 'text-white' : ''
                }`}
                style={
                  activeTab === 'schedule'
                    ? { backgroundColor: '#7C2BD1' }
                    : { color: '#9B4DE3' }
                }
              >
                Schedule
              </button>

              <button
                onClick={() => setActiveTab('insights')}
                className={`px-3 sm:px-4 py-2 rounded-lg font-medium transition-colors text-sm sm:text-base ${
                  activeTab === 'insights' ? 'text-white' : ''
                }`}
                style={
                  activeTab === 'insights'
                    ? { backgroundColor: '#7C2BD1' }
                    : { color: '#9B4DE3' }
                }
              >
                Insights
              </button>

              <button
                onClick={() => setActiveTab('meeting')}
                className={`px-3 sm:px-4 py-2 rounded-lg font-medium transition-colors text-sm sm:text-base ${
                  activeTab === 'meeting' ? 'text-white' : ''
                }`}
                style={
                  activeTab === 'meeting'
                    ? { backgroundColor: '#7C2BD1' }
                    : { color: '#9B4DE3' }
                }
              >
                Meeting
              </button>

              <button
                onClick={handleLogout}
                className="px-3 sm:px-4 py-2 rounded-lg font-medium flex items-center space-x-2 hover:opacity-80 text-sm sm:text-base"
                style={{ color: '#9B4DE3' }}
              >
                <LogOut className="h-4 w-4" />
                <span className="hidden sm:inline">Logout</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* MAIN */}
      <main className="w-full px-8 sm:px-10 lg:px-14 xl:px-16 py-5 lg:flex-1 lg:min-h-0 lg:overflow-hidden">
        {/* CHAT */}
        {activeTab === 'chat' && (
          <div className="grid grid-cols-1 lg:grid-cols-[240px_minmax(0,1fr)_300px] xl:grid-cols-[260px_minmax(0,1fr)_320px] gap-6 xl:gap-8 lg:h-full lg:min-h-0">
            {/* LEFT */}
            <div className="hidden lg:block lg:h-full">
              <div className="h-full flex flex-col justify-start pt-12 xl:pt-14">
                <div className="max-w-[220px] xl:max-w-[240px]">
                  <div className="mb-7">
                    <h2
                      className="text-[30px] xl:text-[34px] font-bold leading-[1.05]"
                      style={{ color: '#17143D' }}
                    >
                      Plan
                    </h2>

                    <h2
                      className="text-[30px] xl:text-[34px] font-bold leading-[1.05]"
                      style={{ color: '#17143D' }}
                    >
                      Organize
                    </h2>

                    <h2
                      className="text-[30px] xl:text-[34px] font-bold leading-[1.05] mt-1"
                      style={{
                        background: 'linear-gradient(90deg, #8B2BE2, #5B21B6)',
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                      }}
                    >
                      Get Things Done
                    </h2>
                  </div>

                  <p
                    className="text-[15px] xl:text-[16px] leading-7 mb-7"
                    style={{ color: '#34305E' }}
                  >
                    Your personal AI assistant
                    <br />
                    for a more organized and
                    <br />
                    balanced day.
                  </p>

                  <div
                    className="w-14 h-[3px] rounded-full mb-9"
                    style={{
                      background: 'linear-gradient(90deg, #7C2BD1, #B96BFF)',
                    }}
                  />

                   <div
                    className="rounded-[24px] px-7 py-7"
                    style={{
                      background:
                        'linear-gradient(145deg, rgba(255,255,255,0.95), rgba(250,247,255,0.95))',
                      border: '1px solid rgba(232, 217, 255, 0.8)',
                      boxShadow: '0 14px 35px rgba(124, 43, 209, 0.06)',
                    }}
                  >
                    <div
                      className="text-[38px] font-serif h-[28px] leading-[28px] mb-1"
                      style={{ color: '#A968F0' }}
                    >
                      “
                    </div>
                  
                    <p
                      className="text-[17px] xl:text-[18px] italic leading-7"
                      style={{ color: '#34305E' }}
                    >
                      Small steps
                      <br />
                      every day lead to
                      <br />
                      big results.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* CENTER CHAT */}
            <div className="min-w-0 lg:h-full lg:min-h-0">
              <div className="bg-white rounded-[24px] shadow-sm border border-purple-100 flex flex-col overflow-hidden min-h-0 h-[650px] lg:h-full">
                {/* TODAY */}
                <div className="px-6 pt-4 pb-2 text-center flex-shrink-0">
                  <span
                    className="inline-flex px-5 py-1.5 rounded-full text-sm font-medium"
                    style={{
                      color: '#8B5FC5',
                      backgroundColor: '#F3EEFF',
                    }}
                  >
                    Today
                  </span>
                </div>

                {/* CHAT MESSAGES */}
                <div
                  className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6 chat-container"
                  id="chat-container"
                >
                  {chatMessages.length === 0 && (
                    <div className="h-full flex flex-col items-center justify-center text-center pb-10">
                      <img
                        src={robotAvatar}
                        alt="AI Assistant"
                        className="w-16 h-16 sm:w-20 sm:h-20 mb-6 rounded-full object-cover"
                        style={{
                          background:
                            'linear-gradient(135deg, #F3EEFF, #E8D9FF)',
                        }}
                      />

                      <h2
                        className="text-xl sm:text-2xl font-semibold mb-2"
                        style={{ color: '#17143D' }}
                      >
                        What would you like to plan today?
                      </h2>

                      <p
                        className="text-sm sm:text-base"
                        style={{ color: '#9B4DE3' }}
                      >
                        Create tasks, set reminders, or plan your schedule.
                      </p>
                    </div>
                  )}

                  {chatMessages.map((msg, index) => (
                    <div
                      key={index}
                      className={`flex mb-6 ${
                        msg.sender === 'user'
                          ? 'justify-end'
                          : 'justify-start'
                      }`}
                    >
                      {msg.sender === 'assistant' && (
                        <div className="flex-shrink-0 mr-3">
                          <img
                            src={logo}
                            alt="AI Assistant"
                            className="w-8 h-8 rounded-full object-cover"
                            style={{
                              background:
                                'linear-gradient(135deg, #F3EEFF, #E8D9FF)',
                            }}
                          />
                        </div>
                      )}

                      <div
                        className={`max-w-[85%] sm:max-w-[70%] ${
                          msg.sender === 'user'
                            ? 'max-w-[75%] sm:max-w-[60%]'
                            : ''
                        }`}
                      >
                        <div
                          className={`px-4 py-3 rounded-2xl ${
                            msg.sender === 'user'
                              ? 'text-white rounded-br-sm shadow-sm'
                              : 'rounded-bl-sm border'
                          }`}
                          style={
                            msg.sender === 'user'
                              ? {
                                  background:
                                    'linear-gradient(135deg, #7C2BD1, #9B4DE3)',
                                }
                              : {
                                  backgroundColor: '#F3EEFF',
                                  borderColor: '#E8D9FF',
                                  color: '#17143D',
                                }
                          }
                        >
                          <p className="text-sm leading-relaxed whitespace-pre-wrap">
                            {msg.message}
                          </p>
                        </div>

                        {msg.tasksCreated &&
                          msg.tasksCreated.length > 0 && (
                            <div
                              className="mt-2 text-xs flex items-center font-medium"
                              style={{ color: '#10B981' }}
                            >
                              <CheckCircle className="h-3 w-3 mr-1" />
                              Created {msg.tasksCreated.length} task(s)
                            </div>
                          )}
                      </div>
                    </div>
                  ))}

                  {/* TYPING INDICATOR */}
                  {showTypingIndicator && (
                    <div className="flex mb-6 justify-start">
                      <div className="flex-shrink-0 mr-3">
                        <img
                          src={logo}
                          alt="AI Assistant"
                          className="w-8 h-8 rounded-full object-cover"
                          style={{
                            background:
                              'linear-gradient(135deg, #F3EEFF, #E8D9FF)',
                          }}
                        />
                      </div>

                      <div
                        className="px-4 py-3 rounded-2xl rounded-bl-sm border"
                        style={{
                          backgroundColor: '#F3EEFF',
                          borderColor: '#E8D9FF',
                        }}
                      >
                        <div className="flex space-x-1">
                          <div
                            className="w-2 h-2 rounded-full animate-bounce"
                            style={{
                              backgroundColor: '#7C2BD1',
                              animationDelay: '0ms',
                            }}
                          ></div>

                          <div
                            className="w-2 h-2 rounded-full animate-bounce"
                            style={{
                              backgroundColor: '#7C2BD1',
                              animationDelay: '150ms',
                            }}
                          ></div>

                          <div
                            className="w-2 h-2 rounded-full animate-bounce"
                            style={{
                              backgroundColor: '#7C2BD1',
                              animationDelay: '300ms',
                            }}
                          ></div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* INPUT */}
                <div
                  className="border-t border-purple-100 p-4 flex-shrink-0"
                  style={{ backgroundColor: '#FAF8FF' }}
                >
                  <div className="flex space-x-3">
                    <input
                      type="text"
                      value={currentMessage}
                      onChange={(e) => setCurrentMessage(e.target.value)}
                      onKeyDown={(e) =>
                        e.key === 'Enter' && sendMessage()
                      }
                      placeholder="Type your message..."
                      className="flex-1 min-w-0 px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent bg-white shadow-sm"
                      style={{ borderColor: '#E8D9FF' }}
                      disabled={loading}
                    />

                    <button
                      onClick={sendMessage}
                      disabled={loading || !currentMessage.trim()}
                      className="px-4 sm:px-6 py-3 text-white rounded-xl disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2 shadow-sm transition-colors"
                      style={{ backgroundColor: '#7C2BD1' }}
                    >
                      <Send className="h-4 w-4" />
                      <span className="hidden sm:inline">Send</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* RIGHT */}
            <div className="hidden lg:block lg:h-full">
              <div className="h-full flex flex-col">
                <div className="space-y-4">
                  {/* SUGGESTIONS */}
                  <div className="bg-white rounded-xl p-5 shadow-sm border border-purple-100">
                    <h3
                      className="font-semibold mb-4"
                      style={{ color: '#17143D' }}
                    >
                      Try asking...
                    </h3>

                    <div className="space-y-3">
                      {[
                        'Remind me to call my supervisor tomorrow at 10am',
                        'Schedule a meeting with the team next Friday',
                        'I need to send an email today by 10am',
                      ].map((example, index) => (
                        <button
                          key={index}
                          onClick={() => setCurrentMessage(example)}
                          className="w-full px-4 py-3 rounded-lg text-left transition-colors flex items-center space-x-3"
                          style={{
                            backgroundColor: '#F3EEFF',
                            border: '1px solid #E8D9FF',
                          }}
                        >
                          <Sparkles
                            className="h-4 w-4 flex-shrink-0"
                            style={{ color: '#7C2BD1' }}
                          />

                          <span
                            className="text-sm"
                            style={{ color: '#17143D' }}
                          >
                            {example}
                          </span>

                          <ArrowRight
                            className="h-4 w-4 flex-shrink-0 ml-auto"
                            style={{ color: '#9B4DE3' }}
                          />
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* LARGE ROBOT IMAGE */}
                  <div className="flex justify-center pt-1">
                    <img
                      src={robot}
                      alt="AI Assistant"
                      className="w-full max-w-[285px] xl:max-w-[310px] h-auto object-contain"
                      style={{
                        filter:
                          'drop-shadow(0 16px 30px rgba(124, 43, 209, 0.08))',
                      }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TASKS */}
        {activeTab === 'tasks' && (
          <div className="space-y-4 h-full overflow-y-auto pb-6">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-2 sm:space-y-0">
              <h2
                className="text-xl font-semibold"
                style={{ color: '#17143D' }}
              >
                All Tasks
              </h2>

              <div
                className="text-sm"
                style={{ color: '#9B4DE3' }}
              >
                {tasks.filter((t) => t.status === 'completed').length} /{' '}
                {tasks.length} completed
              </div>
            </div>

            {tasks.length === 0 ? (
              <div className="text-center py-12 bg-white rounded-lg border border-purple-100">
                <CheckCircle
                  className="h-12 w-12 mx-auto mb-4"
                  style={{ color: '#9B4DE3' }}
                />

                <p style={{ color: '#9B4DE3' }}>
                  No tasks yet. Start by chatting with the assistant!
                </p>
              </div>
            ) : (
              tasks.map((task) => (
                <div
                  key={task.id}
                  className={`task-card ${getPriorityColor(
                    task.priority
                  )} ${
                    task.status === 'completed'
                      ? 'status-completed'
                      : ''
                  }`}
                >
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-3 sm:space-y-0">
                    <div className="flex-1">
                      <h3
                        className="font-medium"
                        style={{ color: '#17143D' }}
                      >
                        {task.title}
                      </h3>

                      {task.description && (
                        <p
                          className="text-sm mt-1"
                          style={{ color: '#9B4DE3' }}
                        >
                          {task.description}
                        </p>
                      )}

                      <div
                        className="flex flex-wrap items-center gap-2 sm:gap-4 mt-2 text-sm"
                        style={{ color: '#9B4DE3' }}
                      >
                        <span
                          className={`px-2 py-1 rounded-full text-xs font-medium ${
                            task.priority === 3
                              ? 'bg-purple-200 text-purple-900'
                              : task.priority === 2
                              ? 'bg-purple-100 text-purple-800'
                              : 'bg-purple-50 text-purple-700'
                          }`}
                        >
                          {getPriorityLabel(task.priority)} Priority
                        </span>

                        {task.is_recurring && (
                          <span
                            className="px-2 py-1 rounded-full text-xs font-medium"
                            style={{
                              backgroundColor: '#F3EEFF',
                              color: '#7C2BD1',
                            }}
                          >
                            {task.recurring_pattern || 'Recurring'}
                          </span>
                        )}

                        {task.deadline && (
                          <span className="flex items-center space-x-1">
                            <Calendar className="h-4 w-4" />
                            <span>
                              {format(
                                new Date(task.deadline),
                                'MMM d, yyyy'
                              )}
                            </span>
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

                    <div className="flex items-center space-x-2 sm:ml-4">
                      {task.status !== 'completed' && (
                        <button
                          onClick={() =>
                            updateTaskStatus(task.id, 'completed')
                          }
                          className="hover:opacity-80"
                          style={{ color: '#10B981' }}
                          title="Mark as complete"
                        >
                          <CheckCircle className="h-5 w-5" />
                        </button>
                      )}

                      <button
                        onClick={() => deleteTask(task.id)}
                        className="hover:opacity-80"
                        style={{ color: '#9B4DE3' }}
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

        {/* SCHEDULE */}
        {activeTab === 'schedule' && (
          <div className="space-y-6 h-full overflow-y-auto pb-6">
            <h2
              className="text-xl font-semibold"
              style={{ color: '#17143D' }}
            >
              Suggested Schedule
            </h2>

            {Object.entries(schedule).map(([period, periodTasks]) =>
              Array.isArray(periodTasks) &&
              periodTasks.length > 0 ? (
                <div
                  key={period}
                  className="bg-white rounded-lg border border-purple-100 p-4"
                >
                  <h3
                    className="font-medium mb-3 capitalize"
                    style={{ color: '#17143D' }}
                  >
                    {period.replace('_', ' ')} ({periodTasks.length}{' '}
                    tasks)
                  </h3>

                  <div className="space-y-2">
                    {periodTasks.map((task) => (
                      <div
                        key={task.id}
                        className={`task-card ${getPriorityColor(
                          task.priority
                        )}`}
                      >
                        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-1 sm:space-y-0">
                          <h4
                            className="font-medium"
                            style={{ color: '#17143D' }}
                          >
                            {task.title}
                          </h4>

                          {task.deadline && (
                            <span
                              className="text-sm"
                              style={{ color: '#9B4DE3' }}
                            >
                              {format(
                                new Date(task.deadline),
                                'MMM d, h:mm a'
                              )}
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
              (periodTasks) =>
                !Array.isArray(periodTasks) ||
                periodTasks.length === 0
            ) && (
              <div className="text-center py-12 bg-white rounded-lg border border-purple-100">
                <Calendar
                  className="h-12 w-12 mx-auto mb-4"
                  style={{ color: '#9B4DE3' }}
                />

                <p style={{ color: '#9B4DE3' }}>
                  No scheduled tasks. Add some tasks to see your
                  schedule!
                </p>
              </div>
            )}
          </div>
        )}

        {/* INSIGHTS */}
        {activeTab === 'insights' && (
          <div className="space-y-6 h-full overflow-y-auto pb-6">
            <h2
              className="text-xl font-semibold"
              style={{ color: '#17143D' }}
            >
              Productivity Insights
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="insight-card">
                <div className="flex items-center justify-between">
                  <div>
                    <p
                      className="text-sm"
                      style={{ color: '#9B4DE3' }}
                    >
                      Completion Rate
                    </p>

                    <p
                      className="text-2xl font-bold"
                      style={{ color: '#17143D' }}
                    >
                      {Math.round(
                        (insights.completion_rate || 0) * 100
                      )}
                      %
                    </p>
                  </div>

                  <CheckCircle
                    className="h-8 w-8"
                    style={{ color: '#10B981' }}
                  />
                </div>
              </div>

              <div className="insight-card">
                <div className="flex items-center justify-between">
                  <div>
                    <p
                      className="text-sm"
                      style={{ color: '#9B4DE3' }}
                    >
                      Avg Duration
                    </p>

                    <p
                      className="text-2xl font-bold"
                      style={{ color: '#17143D' }}
                    >
                      {insights.avg_task_duration
                        ? insights.avg_task_duration.toFixed(1)
                        : '0'}
                      h
                    </p>
                  </div>

                  <Clock
                    className="h-8 w-8"
                    style={{ color: '#7C2BD1' }}
                  />
                </div>
              </div>

              <div className="insight-card">
                <div className="flex items-center justify-between">
                  <div>
                    <p
                      className="text-sm"
                      style={{ color: '#9B4DE3' }}
                    >
                      Overdue Tasks
                    </p>

                    <p
                      className="text-2xl font-bold"
                      style={{ color: '#17143D' }}
                    >
                      {insights.overdue_count || 0}
                    </p>
                  </div>

                  <AlertTriangle
                    className="h-8 w-8"
                    style={{ color: '#7C2BD1' }}
                  />
                </div>
              </div>

              <div className="insight-card">
                <div className="flex items-center justify-between">
                  <div>
                    <p
                      className="text-sm"
                      style={{ color: '#9B4DE3' }}
                    >
                      Total Tasks
                    </p>

                    <p
                      className="text-2xl font-bold"
                      style={{ color: '#17143D' }}
                    >
                      {tasks.length}
                    </p>
                  </div>

                  <TrendingUp
                    className="h-8 w-8"
                    style={{ color: '#7C2BD1' }}
                  />
                </div>
              </div>
            </div>

            <div className="insight-card">
              <h3
                className="font-medium mb-4"
                style={{ color: '#17143D' }}
              >
                Priority Distribution
              </h3>

              <div className="space-y-2">
                {Object.entries(
                  insights.priority_distribution || {}
                ).map(([priority, count]) => (
                  <div
                    key={priority}
                    className="flex justify-between items-center"
                  >
                    <span
                      className={`px-2 py-1 rounded-full text-xs font-medium ${
                        priority == 3
                          ? 'bg-purple-200 text-purple-800'
                          : priority == 2
                          ? 'bg-purple-100 text-purple-700'
                          : 'bg-purple-50 text-purple-600'
                      }`}
                    >
                      {priority == 3
                        ? 'High'
                        : priority == 2
                        ? 'Medium'
                        : 'Low'}{' '}
                      Priority
                    </span>

                    <span
                      className="font-medium"
                      style={{ color: '#17143D' }}
                    >
                      {count} tasks
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {insights.upcoming_deadlines &&
              insights.upcoming_deadlines.length > 0 && (
                <div className="insight-card">
                  <h3
                    className="font-medium mb-4"
                    style={{ color: '#17143D' }}
                  >
                    Upcoming Deadlines
                  </h3>

                  <div className="space-y-2">
                    {insights.upcoming_deadlines.map((task) => (
                      <div
                        key={task.id}
                        className={`task-card ${getPriorityColor(
                          task.priority
                        )}`}
                      >
                        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-1 sm:space-y-0">
                          <h4
                            className="font-medium"
                            style={{ color: '#17143D' }}
                          >
                            {task.title}
                          </h4>

                          <span
                            className="text-sm font-medium"
                            style={{ color: '#7C2BD1' }}
                          >
                            {format(
                              new Date(task.deadline),
                              'MMM d, h:mm a'
                            )}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
          </div>
        )}

        {/* MEETING */}
        {activeTab === 'meeting' && (
          <div className="space-y-6 h-full overflow-y-auto pb-6">
            <h2
              className="text-xl font-semibold"
              style={{ color: '#17143D' }}
            >
              Meeting Scheduler
            </h2>

            <div className="bg-white rounded-lg border border-purple-100 p-6 space-y-4">
              <div>
                <label
                  className="block text-sm font-medium mb-2"
                  style={{ color: '#17143D' }}
                >
                  Meeting Title
                </label>

                <input
                  type="text"
                  value={meetingTitle}
                  onChange={(e) => setMeetingTitle(e.target.value)}
                  placeholder="e.g., Team Standup"
                  className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
                  style={{ borderColor: '#E8D9FF' }}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label
                    className="block text-sm font-medium mb-2"
                    style={{ color: '#17143D' }}
                  >
                    Duration (hours)
                  </label>

                  <select
                    value={meetingDuration}
                    onChange={(e) =>
                      setMeetingDuration(
                        parseFloat(e.target.value)
                      )
                    }
                    className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
                    style={{ borderColor: '#E8D9FF' }}
                  >
                    <option value="0.5">
                      0.5 hours (30 min)
                    </option>
                    <option value="1.0">1.0 hours</option>
                    <option value="1.5">1.5 hours</option>
                    <option value="2.0">2.0 hours</option>
                  </select>
                </div>

                <div>
                  <label
                    className="block text-sm font-medium mb-2"
                    style={{ color: '#17143D' }}
                  >
                    Urgency
                  </label>

                  <select
                    value={meetingUrgency}
                    onChange={(e) =>
                      setMeetingUrgency(e.target.value)
                    }
                    className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
                    style={{ borderColor: '#E8D9FF' }}
                  >
                    <option value="normal">
                      Normal (2 weeks)
                    </option>
                    <option value="urgent">
                      Urgent (3 days)
                    </option>
                    <option value="flexible">
                      Flexible (3 weeks)
                    </option>
                  </select>
                </div>
              </div>

              <button
                onClick={findBestMeetingTime}
                disabled={loading || !meetingTitle.trim()}
                className="w-full px-4 py-2 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
                style={{ backgroundColor: '#7C2BD1' }}
              >
                {loading
                  ? 'Finding best time...'
                  : 'Find Best Meeting Time'}
              </button>
            </div>

            {meetingSuggestions && (
              <div className="bg-white rounded-lg border border-purple-100 p-6">
                <h3
                  className="font-medium mb-4"
                  style={{ color: '#17143D' }}
                >
                  Recommended Meeting Time
                </h3>

                {meetingSuggestions.recommended ? (
                  <div className="space-y-4">
                    <div
                      className="rounded-lg p-4"
                      style={{
                        backgroundColor: '#F3EEFF',
                        border: '1px solid #E8D9FF',
                      }}
                    >
                      <div className="flex items-center space-x-2 mb-2">
                        <CheckCircle
                          className="h-5 w-5"
                          style={{ color: '#10B981' }}
                        />

                        <span
                          className="font-medium"
                          style={{ color: '#17143D' }}
                        >
                          {meetingSuggestions.title}
                        </span>
                      </div>

                      <div
                        className="text-sm space-y-1"
                        style={{ color: '#9B4DE3' }}
                      >
                        <p>
                          <strong>Date:</strong>{' '}
                          {new Date(
                            meetingSuggestions.date
                          ).toLocaleDateString()}
                        </p>

                        <p>
                          <strong>Start:</strong>{' '}
                          {new Date(
                            meetingSuggestions.start_time
                          ).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </p>

                        <p>
                          <strong>End:</strong>{' '}
                          {new Date(
                            meetingSuggestions.end_time
                          ).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </p>

                        <p>
                          <strong>Duration:</strong>{' '}
                          {meetingSuggestions.duration_hours} hours
                        </p>

                        <p>
                          <strong>Reasoning:</strong>{' '}
                          {meetingSuggestions.reasoning}
                        </p>
                      </div>

                      <button
                        onClick={scheduleMeeting}
                        disabled={loading}
                        className="mt-3 w-full px-4 py-2 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
                        style={{ backgroundColor: '#10B981' }}
                      >
                        {loading
                          ? 'Scheduling...'
                          : 'Schedule This Meeting'}
                      </button>
                    </div>

                    {meetingSuggestions.alternatives &&
                      meetingSuggestions.alternatives.length >
                        0 && (
                        <div>
                          <h4
                            className="font-medium mb-2"
                            style={{ color: '#17143D' }}
                          >
                            Alternative Options
                          </h4>

                          <div className="space-y-2">
                            {meetingSuggestions.alternatives.map(
                              (alt, idx) => (
                                <div
                                  key={idx}
                                  className="rounded-lg p-3"
                                  style={{
                                    backgroundColor:
                                      '#F3EEFF',
                                    border:
                                      '1px solid #E8D9FF',
                                  }}
                                >
                                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-2 sm:space-y-0">
                                    <div>
                                      <p
                                        className="text-sm font-medium"
                                        style={{
                                          color: '#17143D',
                                        }}
                                      >
                                        {new Date(
                                          alt.date
                                        ).toLocaleDateString()}{' '}
                                        at{' '}
                                        {new Date(
                                          alt.start_time
                                        ).toLocaleTimeString([], {
                                          hour: '2-digit',
                                          minute: '2-digit',
                                        })}
                                      </p>

                                      <p
                                        className="text-xs"
                                        style={{
                                          color: '#9B4DE3',
                                        }}
                                      >
                                        Score: {alt.score}
                                      </p>
                                    </div>

                                    <button
                                      onClick={() =>
                                        scheduleAlternativeMeeting(
                                          alt
                                        )
                                      }
                                      disabled={loading}
                                      className="px-3 py-1 text-white text-sm rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
                                      style={{
                                        backgroundColor:
                                          '#7C2BD1',
                                      }}
                                    >
                                      Schedule
                                    </button>
                                  </div>
                                </div>
                              )
                            )}
                          </div>
                        </div>
                      )}
                  </div>
                ) : (
                  <div
                    className="rounded-lg p-4"
                    style={{
                      backgroundColor: '#FEF3C7',
                      border: '1px solid #FCD34D',
                    }}
                  >
                    <p style={{ color: '#92400E' }}>
                      {meetingSuggestions.reasoning}
                    </p>
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