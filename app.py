from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
import secrets
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Database configuration
db_config = {
    'user': 'root',
    'password': 'root',
    'host': '127.0.0.1',
    'database': 'library',
    'auth_plugin': 'mysql_native_password'
}

# Database connection
def get_db_connection():
    return mysql.connector.connect(**db_config)

@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

def fetch_book_details(isbn):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT title, author, publisher, year, genre, quantity FROM books WHERE isbn = %s", (isbn,))
    book = cursor.fetchone()
    cursor.close()
    conn.close()
    return book

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    user = {
        "username": session.get('username'),
        "address": "Venice Bungalows",
        "city": "Ahmedabd",
        "state": "Gujarat",
        "zip": "380015",
        "country": "India",
        "phone": "8549607124",
        "email": "codecrusaders@gmail.com"
    }

    borrowed_books = []
    pending_amount = 0

    if 'user_id' in session:
        user_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute('SELECT b.title, br.borrow_date, br.return_date, br.late_fee FROM borrows br JOIN books b ON br.isbn = b.isbn WHERE br.user_id = %s AND br.return_date IS NULL', (user_id,))
        borrowed_books_info = cursor.fetchall()

        for borrowed_book_info in borrowed_books_info:
            borrowed_books.append({
                'title': borrowed_book_info['title'],
                'borrow_date': borrowed_book_info['borrow_date'],
                'return_date': borrowed_book_info['return_date'],
                'late_fee': borrowed_book_info['late_fee']
            })
            if borrowed_book_info['late_fee'] is not None:
                pending_amount += borrowed_book_info['late_fee']

        cursor.close()
        conn.close()

    book = None
    if request.method == 'POST':
        isbn = request.form['isbn']
        book = fetch_book_details(isbn)
        if not book:
            flash('No book found with the given ISBN.')

    return render_template('dashboard.html', user=user, book=book, borrowed_books=borrowed_books, pending_amount=pending_amount)


@app.route('/add_book', methods=['GET', 'POST'])
def add_book():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        isbn = request.form['isbn']
        title = request.form['title']
        author = request.form['author']
        publisher = request.form['publisher']
        year = request.form['year']
        genre = request.form['genre']
        quantity = request.form['quantity']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute('SELECT * FROM books WHERE isbn = %s', (isbn,))
        book = cursor.fetchone()

        if book:
            flash('A book with this ISBN already exists.')
        else:
            cursor.execute(
                'INSERT INTO books (isbn, title, author, publisher, year, genre, quantity) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                (isbn, title, author, publisher, year, genre, quantity)
            )
            conn.commit()
            flash('Book added successfully')

        cursor.close()
        conn.close()
        return redirect(url_for('view_books'))

    return render_template('add_book.html')

@app.route('/view_books')
def view_books():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute('SELECT * FROM books')
    books = cursor.fetchall()

    cursor.execute('SELECT b.isbn, b.title, b.author, br.borrow_date, br.return_date, br.late_fee FROM borrows br JOIN books b ON br.isbn = b.isbn WHERE br.user_id = %s', (user_id,))
    borrowed_books = cursor.fetchall()

    cursor.execute('SELECT b.isbn, b.title, b.author, br.borrow_date, br.return_date, br.late_fee FROM borrows br JOIN books b ON br.isbn = b.isbn WHERE br.user_id = %s AND br.return_date IS NOT NULL', (user_id,))
    returned_books = cursor.fetchall()

    total_bill = sum(book['late_fee'] for book in borrowed_books if book['late_fee'] is not None)

    cursor.close()
    conn.close()

    return render_template('view_books.html', books=books, borrowed_books=borrowed_books, returned_books=returned_books, total_bill=total_bill)

def calculate_bill(borrow_date, return_date):
    if return_date is None:
        return 0

    late_days = (return_date - borrow_date).days
    if late_days <= 0:
        return 0

    return late_days * 10

@app.route('/borrow_book', methods=['GET', 'POST'])
def borrow_book():
    if 'user_id' not in session or session['role'] != 'user':
        return redirect(url_for('login'))

    message = None
    if request.method == 'POST':
        user_id = session['user_id']  # Use the user ID from the session
        isbn = request.form['isbn']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if the book exists
        cursor.execute('SELECT * FROM books WHERE isbn = %s', (isbn,))
        book = cursor.fetchone()

        if not book:
            message = "Invalid ISBN."
        else:
            cursor.execute('INSERT INTO borrows (user_id, isbn, borrow_date) VALUES (%s, %s, NOW())', (user_id, isbn))
            conn.commit()
            message = "Book borrowed successfully."

        cursor.close()
        conn.close()

    return render_template('borrow_book.html', message=message)


@app.route('/return_book', methods=['GET', 'POST'])
def return_book():
    if 'user_id' not in session or session['role'] != 'user':
        return redirect(url_for('login'))

    if request.method == 'POST':
        user_id = session['user_id']
        isbn = request.form['isbn']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute('SELECT borrow_date, return_date FROM borrows WHERE user_id = %s AND isbn = %s AND return_date IS NULL', (user_id, isbn))
        borrow_info = cursor.fetchone()

        if borrow_info:
            borrow_date = borrow_info['borrow_date']
            return_date = datetime.now()

            if return_date > borrow_date + timedelta(days=90):
                late_fee = calculate_bill(borrow_date, return_date)
            else:
                late_fee = 0

            cursor.execute('UPDATE borrows SET return_date = NOW(), late_fee = %s WHERE user_id = %s AND isbn = %s AND return_date IS NULL', (late_fee, user_id, isbn))
            conn.commit()
            flash('Book returned successfully. Total late fee: {} rs.'.format(late_fee))
        else:
            flash('Invalid return request.')

        cursor.close()
        conn.close()

    return render_template('return_book.html')

@app.route('/search_book', methods=['POST'])
def search_book():
    isbn = request.form['isbn']
    book = fetch_book_details(isbn)

    if book:
        return render_template('dashboard.html', user=session.get('username'), book=book)
    else:
        flash('No book found with the given ISBN.')
        return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
