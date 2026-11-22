# Campus Assistant

A web-based campus assistant with a chatbot for students and departments. It answers questions about academics, attendance, exams, placements and scholarships, and gives each user a dashboard.

## Features

- Student login and registration
- Student dashboard: attendance, timetable, exams, results, placements
- Department portal: manage attendance, marks, subjects, timetable, exams and placements
- Chatbots for students and departments
- Knowledge base of college information (JSON files)
- Dark theme

## Tech Stack

- Backend: Python, Flask
- Database: SQLite
- Frontend: HTML, CSS, JavaScript
- Chatbot: intent classifier with a JSON knowledge base

## Project Structure

- chatbot_core/ : chatbot logic (intent classifier, router, answerer)
- database/ : database creation and setup scripts
- knowledge/ : JSON knowledge base (FAQ, placements, etc.)
- data/ : campus data and generator scripts
- templates/ : HTML pages
- static/ : CSS, JS, images
- requirements.txt : Python dependencies

## How to Run

1. Clone the repository
   git clone https://github.com/LavishaPereiraaa/campus-assistant.git

2. Go into the project folder
   cd campus-assistant

3. Install dependencies
   pip install -r requirements.txt

4. Create the database
   python database/create_db.py
   python database/init_db.py

5. Start the app
   python student_chatbot.py

6. Open http://127.0.0.1:5000 in your browser

## Author

Lavisha Pereira
GitHub: https://github.com/LavishaPereiraaa
