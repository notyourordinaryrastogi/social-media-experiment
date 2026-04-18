from flask import Flask, render_template, request, redirect, session
import uuid
import pandas as pd
import random
import csv
import os
from datetime import datetime
import requests
import threading
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycby6EsgOeZqvINDbrEgTncpAoWKI5t6F9InMWa39l-UBob4HbW2yRav-Q6WWKQb7unoovA/exec"

app = Flask(__name__)
app.secret_key = "secret123"

def send_to_google_sheets_async(data):
    def task():
        try:
            requests.post(GOOGLE_SCRIPT_URL, json=data)
        except:
            pass
    threading.Thread(target=task).start()

# ---------- LOAD CSV ----------
def load_posts():
    df = pd.read_csv("posts.csv", encoding="latin1")
    posts = df.to_dict(orient="records")

    for post in posts:   # ✅ THIS LOOP WAS MISSING

        comments_list = post["comments"].split("|")

        parsed_comments = []
        for c in comments_list:
            if "::" in c:
                user, text = c.split("::", 1)
            else:
                user = "user"
                text = c

            parsed_comments.append({
                "user": user.strip(),
                "text": text.strip()
            })

        post["comments"] = parsed_comments

    return posts


# ---------- SAVE DATA ----------
def save_data(row):

    file_exists = os.path.isfile("data.csv")

    fieldnames = [
        "participant_id",
        "trial_number",
        "timestamp",
        "session_start_time",
        "total_time_elapsed_ms",
        "device_type",
        "username",
        "condition",
        "post_id",
        "condition_tag",
        "rating",
        "dwell_time_ms",
        "reaction_time_ms"
    ]

    with open("data.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)


# ---------- HOME ----------
@app.route("/")
def home():
    return redirect("/consent")

@app.route("/consent", methods=["GET", "POST"])
def consent():

    if request.method == "POST":

        consent = request.form.get("consent")

        if consent == "agree":
            session["consent"] = 1
            return redirect("/login")
        else:
            return "<h2>You must provide consent to participate.</h2>"

    return render_template("consent.html")


# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if "consent" not in session:
        return redirect("/consent")

    if request.method == "GET":
        condition = random.choice(["real", "pseudo", "anonymous"])
        session["condition"] = condition
        return render_template("login.html", condition=condition)

    if request.method == "POST":
        username = request.form.get("username")
        participant_id = str(uuid.uuid4())

        session["username"] = username
        session["participant_id"] = participant_id
        session["session_start_time"] = datetime.utcnow().isoformat()
        session["session_start_epoch"] = int(datetime.utcnow().timestamp() * 1000)

        # device detection
        user_agent = request.headers.get("User-Agent", "").lower()
        if "mobile" in user_agent:
            device_type = "mobile"
        else:
            device_type = "desktop"

        session["device_type"] = device_type

        # shuffle posts
        posts = load_posts()
        order = list(range(len(posts)))
        random.shuffle(order)

        session["order"] = order
        session["index"] = 0

        return redirect("/feed")


# ---------- FEED ----------
@app.route("/feed", methods=["GET", "POST"])
def feed():

    if "order" not in session:
        return redirect("/login")

    index = session.get("index", 0)
    order = session.get("order")
    posts = load_posts()

    # experiment end
    if index >= len(order):
        return redirect("/transition")

    current_post_index = order[index]
    current_post = posts[current_post_index]

    if request.method == "POST":

        rating = request.form.get("rating")
        dwell_time = request.form.get("dwell_time")
        reaction_time = request.form.get("reaction_time")
        post_id = request.form.get("post_id")
        condition_tag = request.form.get("condition_tag")

        participant_id = session.get("participant_id")
        username = session.get("username")
        condition = session.get("condition")
        device_type = session.get("device_type")
        session_start_time = session.get("session_start_time")
        session_start_epoch = session.get("session_start_epoch")

        trial_number = index + 1

        timestamp = datetime.utcnow().isoformat()
        current_epoch = int(datetime.utcnow().timestamp() * 1000)

        total_time_elapsed = current_epoch - session_start_epoch

        # clean values
        try:
            dwell_time = int(dwell_time)
        except:
            dwell_time = 0

        try:
            reaction_time = int(reaction_time)
        except:
            reaction_time = 0

        try:
            rating = int(rating)
        except:
            rating = None

        data_row = {
            "participant_id": participant_id,
            "trial_number": trial_number,
            "timestamp": timestamp,
            "session_start_time": session_start_time,
            "total_time_elapsed_ms": total_time_elapsed,
            "device_type": device_type,
            "username": username,
            "condition": condition,
            "post_id": post_id,
            "condition_tag": condition_tag,
            "rating": rating,
            "dwell_time_ms": dwell_time,
            "reaction_time_ms": reaction_time
        }

        # ✅ correctly inside POST block
        data_row["type"] = "experiment"
        send_to_google_sheets_async(data_row)

        session["index"] = index + 1
        return redirect("/feed")

    return render_template(
        "feed.html",
        post=current_post,
        index=index,
        username=session.get("username"),
        condition=session.get("condition")
    )

@app.route("/transition")
def transition():
    return render_template("transition.html")

@app.route("/survey", methods=["GET", "POST"])
def survey():

    if "participant_id" not in session:
        return redirect("/login")

    # ---------- GET ----------
    if request.method == "GET":
        return render_template("survey.html")

    # ---------- POST ----------
    if request.method == "POST":

        participant_id = session.get("participant_id")
        condition = session.get("condition")

        # DEMOGRAPHICS
        age = request.form.get("age")
        gender = request.form.get("gender")

        # USAGE
        weekday_use = request.form.get("weekday_use")
        weekend_use = request.form.get("weekend_use")

        sm_thinking = request.form.get("sm_thinking")
        sm_urge = request.form.get("sm_urge")
        sm_escape = request.form.get("sm_escape")
        sm_control = request.form.get("sm_control")
        sm_restless = request.form.get("sm_restless")
        sm_negative = request.form.get("sm_negative")

        # PLATFORM
        realism = request.form.get("realism")
        similarity = request.form.get("similarity")
        moral_posts = request.form.get("moral_posts")
        moral_comments = request.form.get("moral_comments")

        # IDENTITY
        anon1 = request.form.get("anon1")
        anon2 = request.form.get("anon2")
        anon3 = request.form.get("anon3")
        anon4 = request.form.get("anon4")
        anon5 = request.form.get("anon5")

        # ATTENTION
        attention_check = request.form.get("attention_check")

        #IRI
        ec1 = request.form.get("ec1")
        ec2 = request.form.get("ec2")
        ec3 = request.form.get("ec3")
        ec4 = request.form.get("ec4")

        pt1 = request.form.get("pt1")
        pt2 = request.form.get("pt2")
        pt3 = request.form.get("pt3")
        pt4 = request.form.get("pt4")

        attention_check2 = request.form.get("attention_check2")
        

        # FINAL ROW
        row = {
            "type": "survey",
            "participant_id": participant_id,
            "condition": condition,
            "completion_status": 1,

            "age": age,
            "gender": gender,

            "weekday_use": weekday_use,
            "weekend_use": weekend_use,

            "sm_thinking": sm_thinking,
            "sm_urge": sm_urge,
            "sm_escape": sm_escape,
            "sm_control": sm_control,
            "sm_restless": sm_restless,
            "sm_negative": sm_negative,

            "realism": realism,
            "similarity": similarity,
            "moral_posts": moral_posts,
            "moral_comments": moral_comments,

            "anon1": anon1,
            "anon2": anon2,
            "anon3": anon3,
            "anon4": anon4,
            "anon5": anon5,

            "attention_check": attention_check,

            "ec1": ec1,
            "ec2": ec2,
            "ec3": ec3,
            "ec4": ec4,
            "pt1": pt1,
            "pt2": pt2,
            "pt3": pt3,
            "pt4": pt4,

            "attention_check2": attention_check2,
             
        }

        # SAVE LOCAL
        file_exists = os.path.isfile("survey_data.csv")
        with open("survey_data.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

        # SEND TO GOOGLE SHEETS (ONLY HERE)
        row["type"] = "survey"
        send_to_google_sheets_async(row)

        return "<h2>Thank you for completing the study.</h2>"

    # For GET request, show the survey page
    return render_template("survey.html")

if __name__ == "__main__":
    app.run()