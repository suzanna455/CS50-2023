from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
from functools import wraps
from time import gmtime, strftime
import urllib.request
import os
import cs50

# configure application
app = Flask(__name__)

# configure root path
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///facerate.db")

# check if logged in
def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function


# homepage
@app.route("/")
@login_required
def index():

    users = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])
    events = db.execute("SELECT * FROM newsfeed ORDER BY id DESC")

    return render_template("index.html", user = users[0], events = events)


# register user
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        if not request.form.get("username"):
            return render_template("error.html", say = "Please provide username.")

        elif not request.form.get("email"):
            return render_template("error.html", say = "Please provide email.")

        elif not request.form.get("password"):
            return render_template("error.html", say = "Please provide password.")

        elif not request.form.get("confirm_password"):
            return render_template("error.html", say = "Please confirm password.")

        elif request.form.get("password") != request.form.get("confirm_password"):
            return render_template("error.html", say = "Passwords don't match.")

        hash_pw = pwd_context.hash(request.form.get("password"))

        insert = db.execute("INSERT INTO users (username, password, contact) VALUES(:username, :password, :contact)",
            username = request.form.get("username"), password = hash_pw, contact = request.form.get("email"))

        if not insert:
            return render_template("error.html", say = "Username already exists.")
        else:
            user = db.execute("SELECT * FROM users WHERE username = :username", username = request.form.get("username"))
            session["user_id"] = user[0]["id"]
            return redirect(url_for("profile_set"))

    else:
        return render_template("register.html")


# login
@app.route("/login", methods=["GET", "POST"])
def login():

    session.clear()

    if request.method == "POST":

        if not request.form.get("username"):
            return render_template("error.html", say = "Please provide username.")

        if not request.form.get("password"):
            return render_template("error.html", say = "Please provide password.")

        user = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        if len(user) != 1 or not pwd_context.verify(request.form.get("password"), user[0]["password"]):
            return render_template("error.html", say = "Invalid username and/or password.")

        session["user_id"] = user[0]["id"]

        if user[0]["is_set"] == 1:
            return redirect(url_for("index"))
        else:
            return redirect(url_for("profile_set"))

    else:
        return render_template("login.html")


# set profile after register
@app.route("/profile_set", methods=["GET", "POST"])
def profile_set():

    users = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])

    if request.method == "POST":

        db.execute("UPDATE users SET firstname = :firstname, lastname = :lastname, age = :age, status = :status, gender = :gender, country = :country, about = :about, is_set = :is_set WHERE id = :id",
            firstname = request.form.get("firstname"),
            lastname = request.form.get("lastname"),
            age = request.form.get("age"),
            gender = request.form.get("gender"),
            status = request.form.get("status"),
            country = request.form.get("country"),
            about = request.form.get("about"),
            is_set = 1,
            id = session["user_id"])

        db.execute("INSERT INTO newsfeed (event, event_type, username, image, time) VALUES (:event, :event_type, :username, :image, :time)",
            event = "...has joined FaceRate",
            event_type = "joined",
            username = users[0]["username"],
            image = users[0]["image"],
            time = strftime("%H:%M %d.%m.%Y", gmtime()))

        return redirect(url_for("index"))

    else:
        return render_template("profile_set.html", user = users[0], image_profile = "profile_blank.png")


# upload profile picture
@app.route("/upload", methods=["POST"])
def upload():

    users = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])

    target = os.path.join(APP_ROOT, "static/")
    if not os.path.isdir(target):
        os.mkdir(target)

    for file in request.files.getlist("file"):
        filename = file.filename
        destination = "/".join([target, str(users[0]["username"]) + ".jpg"])
        file.save(destination)

    db.execute("UPDATE users SET image = :image WHERE id = :id", image = str(users[0]["username"]) + ".jpg", id = session["user_id"])

    return render_template("profile_set.html", image_profile = str(users[0]["username"]) + ".jpg", user = users[0])


# show profile
@app.route("/profile")
def profile():

    users = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])
    events = db.execute("SELECT * FROM newsfeed WHERE username = :username ORDER BY id DESC LIMIT 5", username = users[0]["username"])

    return render_template("my_profile.html",
        user = users[0],
        image_profile = users[0]["image"],
        message = "Do you like this person?",
        events = events)


# record likes
@app.route("/like/<username>", methods=["POST"])
def like(username):

    users = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])
    user_target = db.execute("SELECT * FROM users WHERE username = :username", username = username)
    db.execute("UPDATE users SET popularity = :popularity WHERE username = :username", popularity = user_target[0]["popularity"] + 1, username = user_target[0]["username"])

    db.execute("INSERT INTO newsfeed (event, event_type, target, username, image, time) VALUES (:event, :event_type, :target, :username, :image, :time)",
        event = "...likes " + user_target[0]["username"],
        event_type = "vote",
        target = user_target[0]["username"],
        username = users[0]["username"],
        image = users[0]["image"],
        time = strftime("%H:%M %d.%m.%Y", gmtime()))

    events = db.execute("SELECT * FROM newsfeed WHERE username = :username ORDER BY id DESC LIMIT 5", username = user_target[0]["username"])

    return render_template("show_profile.html",
        user = users[0],
        user_target = user_target[0],
        events = events,
        message = "You like this person :)")


# record disslikes
@app.route("/dislike/<username>", methods=["POST"])
def dislike(username):

    users = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])
    user_target = db.execute("SELECT * FROM users WHERE username = :username", username = username)
    db.execute("UPDATE users SET popularity = :popularity WHERE username = :username", popularity = user_target[0]["popularity"] - 1, username = user_target[0]["username"])

    db.execute("INSERT INTO newsfeed (event, event_type, target, username, image, time) VALUES (:event, :event_type, :target, :username, :image, :time)",
        event = "...dislikes " + user_target[0]["username"],
        event_type = "vote",
        target = user_target[0]["username"],
        username = users[0]["username"],
        image = users[0]["image"],
        time = strftime("%H:%M %d.%m.%Y", gmtime()))

    events = db.execute("SELECT * FROM newsfeed WHERE username = :username ORDER BY id DESC LIMIT 5", username = user_target[0]["username"])

    return render_template("show_profile.html",
        user = users[0],
        user_target = user_target[0],
        events = events,
        message = "You dislike this person :(")


# make post
@app.route("/make_post", methods=["POST"])
def make_post():

    users = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])

    db.execute("INSERT INTO newsfeed (event, event_type, username, image, time) VALUES (:event, :event_type, :username, :image, :time)",
        event = request.form.get("wall"),
        event_type = "post",
        username = users[0]["username"],
        image = users[0]["image"],
        time = strftime("%H:%M %d.%m.%Y", gmtime()))

    events = db.execute("SELECT * FROM newsfeed ORDER BY id DESC")

    return render_template("index.html", user = users[0], events = events)


# show by popularity
@app.route("/user_popularity", methods=["POST", "GET"])
def user_popularity():

    users = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])

    users_popularity = db.execute("SELECT * FROM users ORDER BY popularity DESC")

    return render_template("all_users.html", user = users[0], users = users_popularity)


# show by username
@app.route("/user_username", methods=["POST", "GET"])
def user_username():

    users = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])

    users_username = db.execute("SELECT * FROM users ORDER BY username ASC")

    return render_template("all_users.html", user = users[0], users = users_username)


# show by fullname
@app.route("/user_fullname", methods=["POST", "GET"])
def user_fullname():

    users = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])

    users_fullname = db.execute("SELECT * FROM users ORDER BY firstname ASC")

    return render_template("all_users.html", user = users[0], users = users_fullname)


# show by age
@app.route("/user_age", methods=["POST", "GET"])
def user_age():

    users = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])

    users_age = db.execute("SELECT * FROM users ORDER BY age ASC")

    return render_template("all_users.html", user = users[0], users = users_age)


# show by country
@app.route("/user_country", methods=["POST", "GET"])
def user_country():

    users = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])

    users_country = db.execute("SELECT * FROM users ORDER BY country ASC")

    return render_template("all_users.html", user = users[0], users = users_country)


# show wall posts
@app.route("/wall_posts")
def wall_posts():

    users = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])
    events = db.execute("SELECT * FROM newsfeed WHERE event_type = :event_type ORDER BY id DESC", event_type = "post")

    return render_template("index.html", user = users[0], events = events)


# show votes posts
@app.route("/wall_votes")
def wall_votes():

    users = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])
    events = db.execute("SELECT * FROM newsfeed WHERE event_type = :event_type ORDER BY id DESC", event_type = "vote")

    return render_template("index.html", user = users[0], events = events)


# show wall joins
@app.route("/wall_joins")
def wall_joins():

    users = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])
    events = db.execute("SELECT * FROM newsfeed WHERE event_type = :event_type ORDER BY id DESC", event_type = "joined")

    return render_template("index.html", user = users[0], events = events)


# search for user
@app.route("/search_user", methods=["POST"])
def search_user():

    users = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])
    user_list = db.execute("SELECT * FROM users WHERE username LIKE :search_input OR firstname LIKE :search_input OR lastname LIKE :search_input",
        search_input = request.form.get("search") + '%')

    count = 0

    for user in user_list:
        count += 1

    return render_template("search_users.html",
        user = users[0],
        users = user_list,
        count = count)


@app.route("/show_profile/<username>")
def show_profile(username):

    users = db.execute("SELECT * FROM users WHERE id= :id", id = session["user_id"])
    user_target = db.execute("SELECT * FROM users WHERE username = :username", username = username)
    events = db.execute("SELECT * FROM newsfeed WHERE username = :username ORDER BY id DESC LIMIT 5", username = user_target[0]["username"])

    return render_template("show_profile.html",
        user = users[0],
        user_target = user_target[0],
        message = "Do you like this person?",
        events = events)

# logout
@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))