from flask import Flask, render_template, g, request, redirect, url_for, jsonify
import sqlite3
from datetime import datetime
import os.path

app = Flask(__name__)
app.config['DEBUG'] = True
app.secret_key = 'SECRET'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "food_log.db")

def connect_db():
    sql = sqlite3.connect(db_path)
    sql.row_factory = sqlite3.Row # return dictionary instead of tuple
    return sql

def get_db():
    if not hasattr(g, 'sqlite3'):
        g.sqlite_db = connect_db()
    return g.sqlite_db

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    db = get_db()
    if request.method == 'POST':
        date = request.form['date']
        dt = datetime.strptime(date, '%Y-%m-%d')
        database_date = datetime.strftime(dt, '%Y%m%d')
        db.execute('insert into log_date (entry_date) values (?)', [database_date])
        db.commit()
        return redirect(url_for('index')) # stopping form submission on page refresh
    
    cur = db.execute('''SELECT log_date.entry_date, 
                        SUM(food.protein) as protein,
                        SUM(food.carbohydrates) as carbohydrates,
                        SUM(food.fat) as fat, sum(food.calories) as calories
                        FROM log_date 
                        LEFT JOIN food_date on food_date.log_date_id = log_date.id 
                        LEFT JOIN food on food.id = food_date.food_id 
                        GROUP BY log_date.id 
                        ORDER BY log_date.entry_date desc''')
    results = cur.fetchall()
    date_results = []
    for i in results:
        single_date = {}
        single_date['entry_date'] = i['entry_date']
        single_date['protein'] = i['protein']
        single_date['carbohydrates'] = i['carbohydrates']
        single_date['fat'] = i['fat']
        single_date['calories'] = i['calories']
        d = datetime.strptime(str(i['entry_date']), '%Y%m%d')
        single_date['pretty_date'] = datetime.strftime(d, '%B %d, %Y')
        date_results.append(single_date)
    return render_template('home.html', results=date_results)

@app.route('/view/<date>', methods=['GET', 'POST'])
def view(date):
    db = get_db()
    cur = db.execute('SELECT id, entry_date FROM log_date WHERE entry_date = ?', [date])
    date_result = cur.fetchone()
    if request.method == 'POST':
        if request.form.get('remove') == 'Remove':
            db.execute('DELETE FROM log_date WHERE entry_date = ?', [date_result['entry_date']])
            db.commit()
            return redirect(url_for('index'))
        elif request.form.get('delete') == 'Delete':
            db.execute('delete from food_date where food_id = ? and log_date_id = ?', [request.form['food-select'], date_result['id']])
            db.commit()
        else:
            db.execute('INSERT OR IGNORE INTO food_date (food_id, log_date_id) VALUES (?, ?)', [request.form['food-select'], date_result['id']])
            db.commit()
    try:
        d = datetime.strptime(str(date_result['entry_date']), '%Y%m%d')
        pretty_date = datetime.strftime(d, '%B %d, %Y')
        food_cur = db.execute('SELECT id, name FROM food')
        food_results = food_cur.fetchall()

        log_cur = db.execute('SELECT food.name, food.protein, food.carbohydrates, food.fat, food.calories FROM log_date JOIN food_date ON food_date.log_date_id = log_date.id JOIN food ON food.id = food_date.food_id WHERE log_date.entry_date = ?', [date])
        log_results = log_cur.fetchall()
        totals = {}
        totals['protein'] = 0
        totals['carbohydrates'] = 0
        totals['fat'] = 0
        totals['calories'] = 0
        for food in log_results:
            totals['protein'] += food['protein']
            totals['carbohydrates'] += food['carbohydrates']
            totals['fat'] += food['fat']
            totals['calories'] += food['calories']

        return render_template('day.html', entry_date=date_result['entry_date'], pretty_date=pretty_date, food_results=food_results, log_results=log_results, totals=totals)
    except TypeError as err:
        return f"No available informations for date: {date}. Error: {err.args[0]}"

@app.route('/food', methods=['GET', 'POST'])
def food():
    db = get_db()
    if request.method == 'POST':
        name = request.form['food-name'].capitalize()
        protein = request.form['protein']
        carbohydrates = request.form['carbohydrates']
        fat = request.form['fat']
        calories = int(protein) * 4 + int(carbohydrates) * 4 + int(fat) * 9
        db.execute('insert OR IGNORE into food (name, protein, carbohydrates, fat, calories) values (?, ?, ?, ?, ?)', \
                   [name, protein, carbohydrates, fat, calories])
        db.commit()
        return redirect(url_for('food')) # stopping form submission on page refresh
    cur = db.execute('select name, protein, carbohydrates, fat, calories from food')
    food_results = cur.fetchall()
    return render_template('add_food.html', food_results=food_results)

@app.route('/details', methods=['GET', 'POST'])
def details():
    db = get_db()
    cur = db.execute('select name, protein, carbohydrates, fat, calories from food')
    food_results = cur.fetchall()
    if len(food_results) == 0:
        return render_template('details.html', message='No food registred')
    return render_template('details.html', food_results=food_results)

@app.route('/details/<name>', methods=['GET', 'POST'])
def food_item(name):
    name = name.capitalize()
    db = get_db()
    if request.method == 'POST':
        if request.form.get('delete') == 'Delete':
            db.execute('DELETE FROM food WHERE name = ?', [name])
            db.commit()
            return redirect(url_for('details'))
        elif request.form.get('update') == 'Update':
            protein = request.form['protein']
            carbohydrates = request.form['carbohydrates']
            fat = request.form['fat']
            calories = int(protein) * 4 + int(carbohydrates) * 4 + int(fat) * 9
            db.execute('UPDATE food set protein=?, carbohydrates=?, fat=?, calories=? where name = ?', [protein, carbohydrates, fat, calories, name])
            db.commit()
            return redirect(url_for('details')) # stopping form submission on page refresh
        
    cur = db.execute('SELECT name, protein, carbohydrates, fat, calories FROM food WHERE name = ?', [name])
    food_details = cur.fetchone()
    if food_details is None:
        return render_template('details.html', message='Not registered food')
    return render_template('food_item.html', name=name, food_details=food_details)

@app.route('/api')
def api():
    api_data = {
        'api_version': '1.0',
        'infos': 'Not yet implemented'
    }
    return jsonify(api_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
