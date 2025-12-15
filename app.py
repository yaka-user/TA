from random import random, choice

from flask import Flask, render_template, request, redirect, flash
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from flask_migrate import Migrate
from models import db, Task, User

import calendar
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import desc, asc

# =====================
# Flask app
# =====================
app = Flask(__name__)

# =====================
# Config
# =====================
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "deadpork"

# =====================
# DB init
# =====================
db.init_app(app)
migrate = Migrate(app, db)

# Render / gunicorn 対策
@app.before_first_request
def create_tables():
    db.create_all()

# =====================
# Login
# =====================
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

# =====================
# Routes
# =====================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "GET":
        return render_template('register.html', title="ユーザー登録")

    if (
        request.form["id"] == "" or
        request.form["password"] == "" or
        request.form["lastname"] == "" or
        request.form["firstname"] == ""
    ):
        flash("すべての項目を入力してください")
        return render_template('register.html', title="ユーザー登録")

    if User.query.get(request.form["id"]) is not None:
        flash("ユーザを登録できません")
        return render_template('register.html', title="ユーザー登録")

    user = User(
        id=request.form["id"],
        password=request.form["password"],
        lastname=request.form["lastname"],
        firstname=request.form["firstname"]
    )
    db.session.add(user)
    db.session.commit()
    return redirect('/')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect('/')

    if request.method == "GET":
        return render_template('login.html', title="ログイン")

    user = User.query.get(request.form['id'])
    if user and user.verify_password(request.form['password']):
        login_user(user)
        return redirect('/')

    flash("ログインに失敗しました")
    return redirect('/login')

@app.route('/logout')
def logout():
    logout_user()
    return redirect('/login')

@app.route('/user/update', methods=['POST'])
@login_required
def update_user():
    new_id = request.form.get('id')
    if new_id and new_id != current_user.id:
        if User.query.get(new_id) is not None:
            flash("そのユーザーIDは既に使用されています")
            return redirect(request.referrer or '/')
        current_user.id = new_id

    current_user.lastname = request.form['lastname']
    current_user.firstname = request.form['firstname']
    
    new_password = request.form.get('password')
    if new_password:
        current_user.password = new_password
        
    try:
        db.session.commit()
        flash("ユーザー情報を更新しました")
    except Exception as e:
        db.session.rollback()
        flash(f"更新に失敗しました: {e}")

    return redirect(request.referrer or '/')

def _render_calendar(tasks, year, month):
    """
    タスクリストを受け取り，カレンダー形式のHTMLを返すヘルパー関数
    """
    # JSTの設定
    JST = ZoneInfo("Asia/Tokyo")
    now = datetime.now(JST)

    # カレンダーインスタンスの作成
    cal = calendar.Calendar()
    # 月曜始まり(0)〜日曜終わり(6)のリストを取得
    try:
        month_days = cal.monthdatescalendar(year, month)
    except ValueError:
        # 無効な月が指定された場合のフォールバック
        return "無効な日付が指定されました。"

    # 期限が今月のタスクを辞書に整理 
    tasks_by_date = {}
    for task in tasks:
        # DBのdatetimeがnaive(タイムゾーンなし)の場合
        dt = task.deadline
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)
        else:
            dt = dt.astimezone(JST)
            
        task_date = dt.date()
        
        # 指定月のタスクのみ抽出
        if task_date.year == year and task_date.month == month:
            tasks_by_date.setdefault(task_date, []).append(task)
    
    # 前月
    prev_month = month - 1
    prev_year = year
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1

    # 来月
    next_month = month + 1
    next_year = year
    if next_month == 13:
        next_month = 1
        next_year += 1

    # HTML生成

    # ページングリンクを作成
    prev_link = f'/calendar?year={prev_year}&month={prev_month}'
    next_link = f'/calendar?year={next_year}&month={next_month}'
    
    # タイトル部分に移動ボタンを追加
    html = f'''
    <div class="calendar-nav d-flex justify-content-between align-items-center mb-2">
        <a href="{prev_link}" class="btn btn-sm btn-outline-secondary">← 前月</a>
        <h3> {year}年{month}月</h3>
        <a href="{next_link}" class="btn btn-sm btn-outline-secondary">来月 →</a>
    </div>'''

    html += '<div class="table-responsive">'
    html += '<table class="table table-bordered text-center" style="table-layout: fixed;">'
    html += '<thead class="table-light"><tr><th>月</th><th>火</th><th>水</th><th>木</th><th>金</th><th class="text-primary">土</th><th class="text-danger">日</th></tr></thead>'
    html += '<tbody>'

    for week in month_days:
        html += '<tr>'
        for day in week:
            # 今月以外の日付はグレーアウト
            is_current_month = (day.month == month)
            bg_class = '' if is_current_month else 'bg-light text-muted'
            
            # 土日の文字色
            day_text_class = ''
            if day.weekday() == 5: # 土曜日
                day_text_class = 'text-primary'
            elif day.weekday() == 6: # 日曜日
                day_text_class = 'text-danger'

            # カレンダーセルの中身
            cell_content = f'<div class="day-number {day_text_class} {bg_class}" style="text-align: right; font-weight: bold;">{day.day}</div>'
            
            # タスクの挿入
            if is_current_month and day in tasks_by_date:
                task_list_html = '<ul class="list-unstyled mb-0" style="font-size: 0.75rem; text-align: left;">'
                for task in tasks_by_date[day]:
                    # 期限切れチェック
                    is_expired = False
                    t_dl = task.deadline
                    if t_dl.tzinfo is None: t_dl = t_dl.replace(tzinfo=JST)
                    else: t_dl = t_dl.astimezone(JST)
                    
                    if t_dl < now and not task.is_completed:
                        is_expired = True

                    # 表示スタイル
                    if task.is_completed:
                        style_class = "text-muted text-decoration-line-through"
                        icon = "✓"
                    elif is_expired:
                        style_class = "text-danger fw-bold"
                        icon = "!!"
                    else:
                        style_class = "text-primary"
                        icon = "・"
                    
                    # 長すぎる名前の省略
                    display_name = (task.name[:8] + '..') if len(task.name) > 8 else task.name
                    
                    task_list_html += f'<li class="{style_class}" title="{task.name}">{icon}{display_name}</li>'
                task_list_html += '</ul>'
                cell_content += task_list_html

            html += f'<td class="align-top p-1" style="height: 100px; vertical-align: top;">{cell_content}</td>'
        html += '</tr>'

    html += '</tbody></table></div>'
    
    return html

@app.route('/')
@login_required
def index():
    now = datetime.now(ZoneInfo("Asia/Tokyo"))

    # === ソート機能の追加 12月8日(月) === #
    sort_by = request.args.get('sort', 'deadline') # デフォルトの並びはdeadline順
    sort_order = request.args.get('order', 'asc') # 昇順、降順の選択

    # ソート項目の決定
    if sort_by == 'name':           # タスク名順
        sort_column = Task.name
    elif sort_by == 'created_at':   # 作成日順
        sort_column = Task.created_at
    else:                           # デフォルト: 締め切り日時順
        sort_column = Task.deadline  
    
    # 昇順、降順の決定
    if sort_order == 'desc': 
        order_rule = desc(sort_column) # 降順
    else:
        order_rule = asc(sort_column) # 昇順


    # URLクエリパラメータから年と月を取得。未指定の場合は現在月を使用
    try:
        year = int(request.args.get('year', now.year))
        month = int(request.args.get('month', now.month))
    except (ValueError, TypeError):
        year = now.year
        month = now.month

    my_active_tasks = Task.query.filter(
        Task.user_id == current_user.id,
        Task.deadline >= now,
        Task.is_completed == False
    ).order_by(order_rule).all() # ソートの種類により変更

    my_completed_tasks = Task.query.filter(
        Task.user_id == current_user.id,
        Task.is_completed == True
    ).order_by(Task.deadline).all()

    shared_active_tasks = Task.query.join(Task.shared_with).filter(
        User.id == current_user.id,
        Task.deadline >= now,
        Task.is_completed == False
    ).order_by(order_rule).all() # ソートの種類により変更

    shared_completed_tasks = Task.query.join(Task.shared_with).filter(
        User.id == current_user.id,
        Task.is_completed == True
    ).order_by(Task.deadline).all()

    # カレンダーに表示するすべてのタスク
    all_active_tasks = my_active_tasks + shared_active_tasks

    # カレンダーHTMLを生成
    calendar_html = _render_calendar(all_active_tasks, year, month)

    return render_template(
        'index.html',
        title="ホーム",
        my_active_tasks=my_active_tasks,
        my_completed_tasks=my_completed_tasks,
        shared_active_tasks=shared_active_tasks,
        shared_completed_tasks=shared_completed_tasks,
        followees=current_user.followees,
        calendar_html=calendar_html, # カレンダーHTMLを追加
        current_sort=sort_by,    # プルダウンを入力したソートの記録
        current_order=sort_order # プルダウンを入力したソートの記録
    )

@app.route('/calendar')
@login_required
def calendar_view():
    now = datetime.now(ZoneInfo("Asia/Tokyo"))

    # URLクエリパラメータから年と月を取得
    try:
        year = int(request.args.get('year', now.year))
        month = int(request.args.get('month', now.month))
    except (ValueError, TypeError):
        year = now.year
        month = now.month

    # カレンダーには「自分の未完了」「自分の完了」「共有の未完了」「共有の完了」すべてを表示するため取得
    # (index関数と同様のクエリですが、カレンダー用には全て結合します)
    
    my_tasks = Task.query.filter(
        Task.user_id == current_user.id
    ).all()

    shared_tasks = Task.query.join(Task.shared_with).filter(
        User.id == current_user.id
    ).all()

    # 全タスクを結合
    all_tasks = my_tasks + shared_tasks

    # カレンダーHTMLを生成
    calendar_html = _render_calendar(all_tasks, year, month)

    return render_template(
        'calendar.html', # 新しいテンプレートを指定
        title="カレンダー",
        calendar_html=calendar_html,
        followees=current_user.followees # モーダルで使うため渡す
    )

@app.route('/create', methods=['POST'])
@login_required
def create():
    task = Task(
        user=current_user,
        name=request.form['name'],
        deadline=request.form['deadline'],
        is_shared=False,
    )

    share_with_ids = request.form.getlist('share_with')
    followee_ids = {u.id for u in current_user.followees}
    for uid in share_with_ids:
        if uid in followee_ids:
            u = User.query.get(uid)
            if u:
                task.shared_with.append(u)
    task.is_shared = len(task.shared_with) > 0

    db.session.add(task)
    db.session.commit()
    return redirect('/')

@app.route('/expired')
@login_required
def expired():
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    expired_tasks = Task.query.filter(
        Task.user_id == current_user.id,
        Task.deadline < now,
        Task.is_completed == False
    ).order_by(Task.deadline).all()

    shared_expired_tasks = Task.query.join(Task.shared_with).filter(
        User.id == current_user.id,
        Task.deadline < now,
        Task.is_completed == False
    ).order_by(Task.deadline).all()
    
    return render_template('expired.html', expired_tasks=expired_tasks, shared_expired_tasks=shared_expired_tasks, title="期限切れタスク", followees=current_user.followees)

@app.route('/update/<int:task_id>', methods=['POST'])
@login_required
def update(task_id):
    task = Task.query.get(task_id)

    if task is None or task.user != current_user:
        flash("存在しないタスクです")
        return redirect('/')
    
    task.name = request.form['name']
    task.deadline = request.form['deadline']

    share_with_ids = request.form.getlist('share_with')
    followee_ids = {u.id for u in current_user.followees}
    new_shared_users = []
    for uid in share_with_ids:
        if uid in followee_ids:
            u = User.query.get(uid)
            if u:
                new_shared_users.append(u)
    task.shared_with = new_shared_users
    task.is_shared = len(task.shared_with) > 0
    
    db.session.commit()
    next_url = request.form.get('next') or request.referrer or '/'
    return redirect(next_url)


@app.route('/delete/<int:task_id>', methods=['POST'])
@login_required
def delete(task_id):
    task = Task.query.get(task_id)

    if task is None or task.user != current_user:
        flash("存在しないタスクです")
        return redirect('/')

    db.session.delete(task)
    db.session.commit()
    next_url = request.form.get('next') or request.referrer or '/'
    return redirect(next_url)

@app.route('/complete/<int:task_id>', methods=['POST'])
@login_required
def complete(task_id):
    task = Task.query.get(task_id)

    if task is None or task.user != current_user:
        flash("存在しないタスクです")
        return redirect('/')

    task.is_completed = True
    task.completed_at = datetime.now(ZoneInfo("Asia/Tokyo"))
    db.session.commit()
    next_url = request.form.get('next') or request.referrer or '/'
    return redirect(next_url)

@app.route("/users")
@login_required
def users():
    users = User.query.all()
    users.remove(current_user)
    return render_template("users.html", users=users)

@app.route("/follow/<string:user_id>")
@login_required
def follow(user_id):
    user = User.query.get(user_id)
    if current_user not in user.followers:
        user.followers.append(current_user)
        db.session.commit()
    else:
        flash("すでにフォローしています")
    return redirect('/users')

@app.route("/unfollow/<string:user_id>")
@login_required
def unfollow(user_id):
    user = User.query.get(user_id)
    if current_user in user.followers:
        user.followers.remove(current_user)
        db.session.commit()
    else:
        flash("フォローしていません")
    return redirect('/users')


@app.route('/rand')
def rand():
    r = random()

    if r < 0.3:
        return f"{r=:.3f} smaller"
    elif r <= 0.7:
        return f"{r=:.3f} medium"
    else:
        return f"{r=:.3f} larger"

@app.route('/template')
def template():
    return render_template('template.html', greeting="Hello", title="あいさつ")

@app.route('/template_list')
def template_list():
    students = []
    for n in range(1, 101):
        students.append(f"2xG2{n:03d}")

    return render_template('template_list.html', students=students, title="学生番号リスト")

@app.route('/template_dict')
def template_dict():
    students = {}
    for n in range(1, 101):
        students[f"2xG2{n:03d}"] = choice(['A', 'B', 'C'])

    return render_template('template_dict.html', students=students, title="学生ごとのクラス分け")

#期日までの残り日数
@app.template_filter('remaining_days')
def calculate_remaining_days(deadline):
    JST = ZoneInfo("Asia/Tokyo")
    now = datetime.now(JST)
    
    # deadlineにタイムゾーン情報がない場合(Naive)、強制的にJSTを付与
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=JST)

    # 既に期限切れの場合
    if deadline < now:
        return '<span class="badge text-bg-danger">期限切れ</span>'

    # 日数差
    delta = deadline - now
    remaining_days = delta.days
    
    # 時間単位で残り時間を計算 (残り48時間未満の判定に使用)
    remaining_hours = delta.total_seconds() / 3600
    
    # --- 修正ロジック ---
    
    # 1. 残り48時間未満 (残り1日 + 時間表示まで含む) -> 赤色 (danger)
    # これにより、残り1日と数時間の場合も赤くなります。
    if remaining_hours < 48:
        
        # 残り24時間未満の場合 (時間表示)
        if remaining_days == 0:
            hours = int(delta.seconds / 3600)
            if hours > 0:
                return f'<span class="badge text-bg-danger">あと {hours} 時間</span>'
            else:
                return '<span class="badge text-bg-danger">締切間近</span>'
        
        # 残り24時間以上48時間未満の場合 (残り1日表示)
        elif remaining_days == 1:
            return f'<span class="badge text-bg-danger">あと 1 日</span>'

    # 2. 残り7日未満 (残り2日〜6日) -> 黄色 (warning)
    # 48時間以上のタスクで、かつ残りの日数が7日未満の場合がここに該当します。
    if remaining_days < 7:
        return f'<span class="badge text-bg-warning">残り {remaining_days} 日</span>'
        
    # 3. それ以外 (7日以上) -> 青色 (primary)
    return f'<span class="badge text-bg-primary">残り {remaining_days} 日</span>'
