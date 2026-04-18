from flask import Flask, render_template, request, redirect, session
import uuid
import pandas as pd
import random
import csv
import os
from datetime import datetime
import requests

GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxBI9xhTo48QtNaCbpzKy3lbKqaibYPr8j7fvHLQFp1LmDNhdtSRVAWKBSOCrUESX1h5Q/exec"

app = Flask(__name__)
app.secret_key = "secret123"


# ---------- LOAD POSTS ----------
def load_posts():
    df = pd.read_csv("posts.csv", encoding="latin1")
    posts = df.to_dict(orient="records")

    for post in posts:
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


# ---------- HOME ----------
@app.route("/")
def home():
    return redirect("/consent")


# ---------- CONSENT ----------
@app.route("/consent", methods=["GET", "POST"])
def consent():

    if request.method == "POST":
        consent = request.form.get("consent")

        if consent == "agree":
            session["consent"] = 1
            return redirect("/login")
        else:
            return "<h2>You must provide consent.</h2>"

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

        session["username"] = request.form.get("username")
        session["participant_id"] = str(uuid.uuid4())

        session["session_start_time"] = datetime.utcnow().isoformat()
        session["session_start_epoch"] = int(datetime.utcnow().timestamp() * 1000)

        user_agent = request.headers.get("User-Agent", "").lower()
        session["device_type"] = "mobile" if "mobile" in user_agent else "desktop"

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

    if index >= len(order):
        return redirect("/transition")

    current_post = posts[order[index]]

    if request.method == "POST":

        # ---------- GET FORM ----------
        rating = request.form.get("rating")
        dwell_time = request.form.get("dwell_time")
        reaction_time = request.form.get("reaction_time")
        post_id = request.form.get("post_id")
        condition_tag = request.form.get("condition_tag")

        # ---------- SESSION ----------
        participant_id = session.get("participant_id")
        username = session.get("username")
        condition = session.get("condition")
        device_type = session.get("device_type")

        session_start_time = session.get("session_start_time")
        session_start_epoch = session.get("session_start_epoch")

        # ---------- TIMING ----------
        trial_number = index + 1
        timestamp = datetime.utcnow().isoformat()
        current_epoch = int(datetime.utcnow().timestamp() * 1000)
        total_time_elapsed = current_epoch - session_start_epoch

        # ---------- CLEAN ----------
        try: rating = int(rating)
        except: rating = None

        try: dwell_time = int(dwell_time)
        except: dwell_time = 0

        try: reaction_time = int(reaction_time)
        except: reaction_time = 0

        # ---------- FINAL ROW ----------
        data_row = {
            "type": "experiment",
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

        # ---------- DEBUG ----------
        print("==== EXPERIMENT ====")
        print(data_row)

        # ---------- SEND (SYNC - FIX) ----------
        try:
            res = requests.post(GOOGLE_SCRIPT_URL, json=data_row, timeout=5)
            print("STATUS:", res.status_code)
            print("RESPONSE:", res.text)
        except Exception as e:
            print("ERROR:", str(e))

        # ---------- NEXT ----------
        session["index"] = index + 1
        return redirect("/feed")

    return render_template(
        "feed.html",
        post=current_post,
        index=index,
        username=session.get("username"),
        condition=session.get("condition")
    )


# ---------- TRANSITION ----------
@app.route("/transition")
def transition():
    return render_template("transition.html")


# ---------- SURVEY ----------
@app.route("/survey", methods=["GET", "POST"])
def survey():

    if "participant_id" not in session:
        return redirect("/login")

    if request.method == "GET":
        return render_template("survey.html")

    if request.method == "POST":

        row = dict(request.form)
        row["type"] = "survey"
        row["participant_id"] = session.get("participant_id")
        row["condition"] = session.get("condition")

        print("==== SURVEY ====")
        print(row)

        try:
            requests.post(GOOGLE_SCRIPT_URL, json=row, timeout=5)
        except:
            pass

        return "<h2>Thank you for completing the study.</h2>"

    return render_template("survey.html")


if __name__ == "__main__":
    app.run()