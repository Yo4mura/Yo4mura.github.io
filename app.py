from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask import jsonify 
import psycopg2
import psycopg2.extras
from psycopg2.extras import RealDictCursor
from flask_bcrypt import Bcrypt
from flask_cors import CORS
import traceback
from pytz import timezone, utc
import pytz
from datetime import datetime
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
import os
import re

app = Flask(__name__)
app.secret_key = "Alkun_2103"
bcrypt = Bcrypt(app)
CORS(app, supports_credentials=True)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'  
app.config['MAIL_PORT'] = 587  
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'aliakbarbeken@gmail.com'  
app.config['MAIL_PASSWORD'] = 'yqpq vqch mpud qvds'  
app.config['MAIL_DEFAULT_SENDER'] = 'your-email@gmail.com'

mail = Mail(app)
s = URLSafeTimedSerializer(os.environ.get('SECRET_KEY', 'a_random_secret_key'))

conn = psycopg2.connect(
    dbname="test_db_1",
    user="postgres",
    password="123",
    host="localhost",
    port="5432",
    cursor_factory=RealDictCursor,
)

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/main")
def main():
    if "user_full_name" in session and "role" in session:
        if session["role"] == "teacher":
            return render_template("teacher/main.html", user_full_name=session["user_full_name"])
        elif session["role"] == "student":
            return render_template("student/main2.html", user_full_name=session["user_full_name"])
    return redirect(url_for("login"))

@app.route("/register-page")
def register_page():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            print("Форма содержит:", request.form)

            first_name = request.form.get("first_name").strip()
            last_name = request.form.get("last_name").strip()
            email = request.form.get("email").strip().lower()
            password = request.form.get("password").strip()
            role = request.form.get("role")
            group_id = request.form.get("group_id")
            subject = request.form.get("subject")

            print("Полученные данные:", first_name, last_name, email, role, group_id, subject)

            # Проверка пароля на длину и сложность
            password_regex = r'^(?=.*[A-Z])(?=.*\d)(?=.*[!@#%^&*()~]).{8,}$'
            if not re.match(password_regex, password):
                flash("Пароль должен содержать не менее 8 символов, включая заглавную букву, цифры и специальные символы (!, @, #, %, ^, &, *, (, ), ~).")
                return render_template("index.html")

            if not first_name or not last_name or not email or not password:
                flash("Все поля обязательны для заполнения!")
                return render_template("index.html")

            cur = conn.cursor()

            # Проверка роли и сохранение данных пользователя
            if role == "student":
                if not group_id:
                    flash("Студент должен выбрать группу!")
                    return render_template("index.html")

                cur.execute(""" 
                    INSERT INTO users (first_name, last_name, email, password, role, group_id, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'pending') RETURNING id;
                """, (first_name, last_name, email, bcrypt.generate_password_hash(password).decode("utf-8"), role, group_id))
                result = cur.fetchone()

                if result and "id" in result:
                    student_id = result['id']
                    print(f"ID студента: {student_id}")
                else:
                    raise Exception("Ошибка: результат запроса пуст или не содержит данных.")

                cur.execute("""
                    INSERT INTO user_groups (user_id, group_id)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id, group_id) DO NOTHING;
                """, (student_id, group_id))
                print(f"Студент добавлен в группу с ID: {group_id} или уже состоит в ней.")

                # cur.execute(""""
                #     INSERT INTO results (user_id, question_id, selected_option_id, is_correct, completed_at)
                #     VALUES (%s, %s, %s, %s, NOW())""",
                #     (user_id, question_id, selected_option_id, is_correct, completed_at))


            elif role == "teacher":
                if not subject:
                    flash("Учитель должен указать предмет!")
                    return render_template("index.html")

                cur.execute(""" 
                    INSERT INTO users (first_name, last_name, email, password, role, subject, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'pending') RETURNING id;
                """, (first_name, last_name, email, bcrypt.generate_password_hash(password).decode("utf-8"), role, subject))
                result = cur.fetchone()

                if result and "id" in result:
                    teacher_id = result['id']
                    print(f"ID учителя: {teacher_id}")
                else:
                    raise Exception("Ошибка: результат запроса пуст.")
                cur.execute("SELECT add_teacher_to_all_groups(%s);", (teacher_id,))
                print(f"Учитель добавлен во все группы: ID {teacher_id}")
            token = s.dumps(email, salt='email-confirmation')
            confirm_url = url_for('confirm_email', token=token, _external=True)
            msg = Message("Подтвердите ваш email", recipients=[email])
            msg.body = f"Пройдите по ссылке для подтверждения email: {confirm_url}"
            mail.send(msg)
            conn.commit()
            cur.close()
            flash("Вы успешно зарегистрировались! Проверьте свою почту для подтверждения.")
            return redirect(url_for("login"))
        except Exception as e:
            conn.rollback()
            print(f"Ошибка: {str(e)}")
            traceback.print_exc()
            flash(f"Произошла ошибка: {str(e)}")

    return render_template("index.html")

@app.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = s.loads(token, salt='email-confirmation', max_age=3600)  # Token expires after 1 hour
        cur = conn.cursor()
        cur.execute("UPDATE users SET status = 'active' WHERE email = %s", (email,))
        conn.commit()
        cur.close()
        flash("Ваша почта успешно подтверждена!")
        return redirect(url_for("login"))
    except Exception as e:
        flash("Неверная или устаревшая ссылка для подтверждения!")
        return redirect(url_for("home"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        if user and bcrypt.check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            print(f"Установлен user_id в сессии: {session['user_id']}")
            session["user_full_name"] = f"{user['first_name']} {user['last_name']}"
            session["role"] = user["role"]
            return redirect(url_for("main"))
        else:
            flash("Неверный email или пароль!")
    return render_template("login.html")

@app.route("/create_test", methods=["GET", "POST"]) 
def create_test(): 
    if "user_id" not in session: 
        return redirect(url_for("login")) 
    if request.method == "POST":
        try:
            data = request.get_json()
            test_name = data.get("test_name")
            questions = data.get("questions", [])
            if not test_name:
                return jsonify({"error": "Название теста не может быть пустым"}), 400
            if not questions:
                return jsonify({"error": "Тест должен содержать хотя бы один вопрос"}), 400
            cur = conn.cursor()
            cur.execute("INSERT INTO tests (name, user_id) VALUES (%s, %s) RETURNING id",
                        (test_name, session["user_id"]))
            test_id = cur.fetchone()["id"]

            for i in questions:
                question_text = i.get('text')
                options = i.get('options')
                correct_id = i.get('correct_answer_id')
                print(question_text)
                print(options)
                print(options[correct_id])

                if not question_text or not options or correct_id is None:
                    return jsonify({"error": "Все поля должны быть заполнены"}), 400
                cur.execute("INSERT INTO questions (test_id, question_text) VALUES (%s, %s) RETURNING id",
                            (test_id, question_text))
                question_id = cur.fetchone()["id"]
                for index, option_text in enumerate(options):
                    is_correct = index == int(correct_id)
                    cur.execute("INSERT INTO options (question_id, option_text, is_correct) VALUES (%s, %s, %s)",
                                (question_id, option_text, is_correct))

            conn.commit()
            cur.close()
            return jsonify({"message": "Тест успешно создан!"}), 200
        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500
    return render_template("teacher/create_test.html")

@app.route('/api/tests')
def get_tests():
    try:
        user_id = session.get('user_id')  
        if user_id is None:
            return jsonify({'error': 'Необходимо войти в систему'}), 401
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM tests WHERE user_id = %s", (user_id,))
        tests = cur.fetchall()
        cur.close()
        test_list = [{'id': test['id'], 'name': test['name']} for test in tests]
        return jsonify(test_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_groups')
def get_groups():
    try:
        user_id = session.get('user_id')
        if user_id is None:
            print("Пользователь не авторизован.")  
            return jsonify({'error': 'Необходимо войти в систему'}), 401
        print(f"Получен user_id: {user_id}") 
        cur = conn.cursor()
        cur.execute("""
            SELECT g.id, g.name 
            FROM user_groups ug
            JOIN groups g ON ug.group_id = g.id
            WHERE ug.user_id = %s
        """, (user_id,))
        groups = cur.fetchall()
        cur.close()
        if not groups:
            print("Для пользователя группы не найдены.")
        groups_list = [{'id': group['id'], 'name': group['name']} for group in groups]
        print(f"Группы найдены: {groups_list}")  
        return jsonify(groups_list)

    except Exception as e:
        import traceback
        print(f"Error: {str(e)}")
        print("Stack trace:", traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/assign-test', methods=['POST'])
def assign_test():
    try:
        data = request.json
        print(f"Received data: {data}")  
        test_id = data['test_id']
        group_id = data['group_id']
        due_date = data['due_date']
        print(f"Assigning test with ID {test_id} to group {group_id}, due date {due_date}")  
        query_upsert = """
        INSERT INTO test_assignments (test_id, group_id, due_date)
        VALUES (%s, %s, %s)
        ON CONFLICT (test_id, group_id) 
        DO UPDATE SET due_date = EXCLUDED.due_date
        """
        
        cur = conn.cursor()
        cur.execute(query_upsert, (test_id, group_id, due_date))
        conn.commit()
        cur.close()
        print("Тест успешно назначен!")  
        return jsonify({'message': 'Тест успешно назначен!'}), 201
    except Exception as e:
        conn.rollback()
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/assigned-tests', methods=['GET'])
def get_assigned_tests():
    try:
        print(f"Session content: {session}")
        print(f"Request args: {request.args}")
        student_id = request.args.get('user_id') or session.get('user_id')
        print(f"Проверяем student_id: {student_id}")

        if not student_id:
            print("student_id не найден в сессии")
            return jsonify({'error': 'Не указан student_id'}), 400

        cur = conn.cursor()
        cur.execute("""
            SELECT g.id
            FROM user_groups ug
            JOIN groups g ON ug.group_id = g.id
            WHERE ug.user_id = %s
        """, (student_id,))
        rows = cur.fetchall()

        if not rows:
            print("Группы по данному идентификатору учащегося не найдены.")
            return jsonify([])

        group_ids = [row['id'] for row in rows]
        print(f"Идентификаторы групп найдены для Student_id {student_id}: {group_ids}")

        cur.execute("""
            SELECT t.id, t.name, ta.due_date
            FROM test_assignments ta
            JOIN tests t ON ta.test_id = t.id
            WHERE ta.group_id = ANY(%s)
        """, (group_ids,))
        results = cur.fetchall()

        if not results:
            print("Для данных идентификаторов групп не найдено назначенных тестов.")
            return jsonify([])

        assigned_tests = [{'id': row['id'], 'name': row['name'], 'due_date': row['due_date'].strftime('%Y-%m-%d %H:%M:%S')} for row in results]
        cur.close()

        return jsonify(assigned_tests)
    
    except Exception as e:
        import traceback
        print(f"Ошибка при получении назначенных тестов: {e}")
        print("Stack trace:", traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route("/pass_test/<int:test_id>", methods=["GET", "POST"])
def pass_test(test_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    student_id = session["user_id"]
    cur = conn.cursor()
    cur.execute("""
        SELECT 1
        FROM test_assignments ta
        JOIN user_groups ug ON ta.group_id = ug.group_id
        WHERE ta.test_id = %s AND ug.user_id = %s
    """, (test_id, student_id))
    test_assigned = cur.fetchone()
    if not test_assigned:
        cur.close()
        return jsonify({'error': 'Тест не назначен для данного студента'}), 403

    if request.method == "POST":
        submitted_answers = request.form
        user_id = session["user_id"]
        cur = conn.cursor()
        cur.execute("""
            SELECT questions.id AS question_id, options.id AS correct_option_id
            FROM questions
            JOIN options ON questions.id = options.question_id
            WHERE questions.test_id = %s AND options.is_correct = true
        """, (test_id,))
        correct_answers = {row['question_id']: row['correct_option_id'] for row in cur.fetchall()}

        total_questions = len(correct_answers)
        correct_count = 0
        detailed_results = []
        utc_timezone = pytz.utc
        completed_at = datetime.now(utc_timezone)

        for question_id, correct_option_id in correct_answers.items():
            user_answer = submitted_answers.get(str(question_id))
            selected_option_id = int(user_answer) if user_answer else None
            is_correct = selected_option_id == correct_option_id if selected_option_id else False
            if is_correct:
                correct_count += 1

            detailed_results.append({
                "question_id": question_id,
                "correct_option_id": correct_option_id,
                "selected_option_id": selected_option_id,
                "is_correct": is_correct
            })
            cur.execute("""
                INSERT INTO results (user_id, test_id, question_id, selected_option_id, is_correct, completed_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, test_id, question_id, selected_option_id, is_correct, completed_at))
        conn.commit()
        cur.close()
        score = f"{correct_count}/{total_questions}"
        return render_template("student/results.html", score=score, detailed_results=detailed_results)

    cur = conn.cursor()
    cur.execute("""
        SELECT questions.id AS question_id, 
                questions.question_text, 
                options.id AS option_id, 
                options.option_text
        FROM questions
        JOIN options ON questions.id = options.question_id
        WHERE questions.test_id = %s
    """, (test_id,))
    rows = cur.fetchall()
    cur.close()
    questions = {}
    for row in rows:
        question_id = row['question_id']
        question_text = row['question_text']
        option_id = row['option_id']
        option_text = row['option_text']
        if question_id not in questions:
            questions[question_id] = {
                "text": question_text,
                "options": []
            }
        questions[question_id]["options"].append({
            "id": option_id,
            "text": option_text
        })
    return render_template("student/pass_test.html", test_id=test_id, questions=questions)

@app.route("/view_test_answers/<int:test_id>", methods=["GET"])
def view_test_answers(test_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    user_id = session["user_id"]
    cur = conn.cursor()
    cur.execute("""
        SELECT questions.question_text, options.option_text AS selected_answer, 
            CASE WHEN options.is_correct THEN 'Correct' ELSE 'Incorrect' END AS correctness
        FROM results
        JOIN questions ON results.question_id = questions.id
        JOIN options ON results.selected_option_id = options.id
        WHERE results.test_id = %s AND results.user_id = %s
    """, (test_id, user_id))
    answers = cur.fetchall()
    cur.close()
    return render_template("view_answers.html", answers=answers)

@app.route('/api/test-results', methods=['GET'])
def get_test_results():
    test_id = request.args.get('test_id')
    try:
        print(f"Подключение")
        conn = psycopg2.connect(
            dbname="test_db",
            user="postgres",
            password='21032007A',
            host='localhost', 
            port=5432  
        )
        print(f"Соединение с базой данных установлено.")  
        cursor = conn.cursor()  
        cursor.execute("""
            SELECT u.first_name || ' ' || u.last_name AS student_name, 
                g.name AS group_name, 
                SUM(CASE WHEN r.is_correct THEN 1 ELSE 0 END) AS score,  -- Подсчет только правильных ответов
                (SELECT COUNT(*) FROM questions WHERE test_id = %s) AS total,
                r.completed_at
            FROM results r
            JOIN users u ON r.user_id = u.id
            JOIN groups g ON u.group_id = g.id
            WHERE r.test_id = %s
            GROUP BY u.id, g.id, r.completed_at
        """, (test_id, test_id))
        
        results = cursor.fetchall()
        print(f"Результаты получены: {results}")  
        
        cursor.close()
        conn.close()
        print("Закрыть подключение.") 
        local_tz = timezone('Asia/Qyzylorda') 
        result_list = []
        for row in results:
            print(f"Обработка строки: {row}")  
            student_name = row[0]
            group_name = row[1]
            score = row[2]
            total = row[3]
            utc_time = row[4]  
            if utc_time is not None:
                if utc_time.tzinfo is None:
                    utc_time = pytz.utc.localize(utc_time)
                local_time = utc_time.astimezone(local_tz)
                formatted_time = local_time.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
            else:
                formatted_time = None  
            result_list.append({
                'student_name': student_name,
                'group_name': group_name,
                'score': score,
                'total': total,
                'completed_at': formatted_time
            })
        
        print(f"Вернуть результаты: {result_list}") 
        return jsonify(result_list)
    except Exception as e:
        print(f"Ошибка при получении результатов теста: {e}")
        return jsonify({'error': f'Не удалось получить результаты теста: {str(e)}'}), 500

@app.route('/teacher') 
def teacher(): 
    return render_template('teacher/teacher.html')

@app.route('/check_test') 
def check_test(): 
    return render_template('teacher/check_test.html')

@app.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)