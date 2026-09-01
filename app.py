from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "DoubtBot is running!"

if __name__ == "__main":
    app.run(dobug=True)