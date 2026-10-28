from app import create_app

app = create_app()

# Demo at /api

if __name__ == '__main__':
    app.run(debug=True, port=5000)