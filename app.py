from flask import Flask, render_template, request

app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        return render_template("hello.html", name=request.form.get("name", "world"))
    return render_template("index.html")