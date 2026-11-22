const chatWidget = document.getElementById('chatWidget');
const chatBody = document.getElementById('chatBody');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const openChatBtn = document.getElementById('openChat');
const closeChatBtn = document.getElementById('closeChat');
const startChatInline = document.getElementById('startChatInline');
const chatEmpty = document.getElementById('chatEmpty');

function nowTime(){
  try{
    return new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
  }catch{ return '' }
}

function addBubble(text, role){
  const b = document.createElement('div');
  b.className = `bubble ${role === 'user' ? 'bubble--user' : 'bubble--bot'}`;
  b.textContent = text;

  const meta = document.createElement('div');
  meta.className = 'bubble__meta';
  meta.textContent = role === 'user' ? `You • ${nowTime()}` : `Assistant • ${nowTime()}`;
  b.appendChild(meta);

  chatBody.appendChild(b);
  chatBody.scrollTop = chatBody.scrollHeight;
}

function normalize(s){
  return (s || '').toLowerCase();
}

function botReply(userText){
  const msg = normalize(userText);
  if(!msg) return "Type something to start.";

  if(msg.includes('attendance')){
    return "Attendance (demo): Check your attendance percent per semester and subjects. Typically, 70%+ is needed for PASS.";
  }
  if(msg.includes('result') || msg.includes('marks') || msg.includes('score') || msg.includes('grade')){
    return "Results (demo): Semester results are published at the end of each semester. You can also view subject-wise marks.";
  }
  if(msg.includes('timetable') || msg.includes('schedule') || msg.includes('class')){
    return "Timetable (demo): Timetable varies by department and semester. Try asking for 'today' to get the current-day schedule.";
  }
  if(msg.includes('cgpa') || msg.includes('sgpa')){
    return "CGPA/SGPA (demo): CGPA is based on your overall performance; SGPA is calculated per semester.";
  }
  if(msg.includes('placement') || msg.includes('company') || msg.includes('package')){
    return "Placements (demo): View placement companies and packages for your department. You can also ask for 'status' if available.";
  }
  if(msg.includes('department') || msg.includes('admin') || msg.includes('analytics')){
    return "Department (demo): Departments can view analytics, backlogs, subject performance, and manage schedules.";
  }

  return "I can help with attendance, results, timetable, CGPA/SGPA, and placements (demo). Try: 'attendance', 'result', or 'timetable'.";
}

function openChat(){
  chatWidget.hidden = false;
  chatEmpty.style.display = 'none';
  setTimeout(() => chatInput.focus(), 50);
}

function closeChat(){
  chatWidget.hidden = true;
  chatEmpty.style.display = 'flex';
}

function seedIfEmpty(){
  if(chatBody.children.length > 0) return;
  addBubble("Hi! Ask me about attendance, results, timetable, CGPA/SGPA, or placements. (Demo widget)", 'bot');
}

openChatBtn?.addEventListener('click', () => { openChat(); seedIfEmpty(); });
startChatInline?.addEventListener('click', () => { openChat(); seedIfEmpty(); });
closeChatBtn?.addEventListener('click', closeChat);

chatForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const text = chatInput.value;
  if(!text || !text.trim()) return;

  addBubble(text, 'user');
  chatInput.value = '';

  const reply = botReply(text);
  // small typing delay
  const typing = document.createElement('div');
  typing.className = 'bubble bubble--bot';
  typing.textContent = 'Typing...';
  chatBody.appendChild(typing);
  chatBody.scrollTop = chatBody.scrollHeight;

  setTimeout(() => {
    typing.remove();
    addBubble(reply, 'bot');
  }, 400);
});

