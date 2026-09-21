import requests
from flask import Flask, flash, render_template, request

from . import classifier
from .config import ConfigError, config


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.FLASK_SECRET_KEY

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/")
    def classify():
        text = request.form.get("text", "").strip()
        if not text:
            flash("Escribe una descripción del lugar antes de continuar.", "error")
            return render_template("index.html", text=text), 400

        try:
            result = classifier.classify_text(text)
        except ConfigError as exc:
            flash(str(exc), "error")
            return render_template("index.html", text=text), 500
        except requests.exceptions.RequestException as exc:
            flash(f"Error consultando una API externa: {exc}", "error")
            return render_template("index.html", text=text), 502

        return render_template("result.html", text=text, result=result)

    return app


app = create_app()


def main():
    app.run(debug=config.FLASK_DEBUG, port=config.FLASK_PORT)


if __name__ == "__main__":
    main()
