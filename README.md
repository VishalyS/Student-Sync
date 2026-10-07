# How to Run the Project

This project includes a Tailwind CSS-based web page with animations and a Python (Flask)  Follow the steps below to set up and run the project locally.

## Prerequisites
Make sure you have the following installed:

- Node.js (for managing Tailwind CSS)
- Python (for the Flask backend)
- Flask (Python web framework)
- Tailwind CLI (for compiling the Tailwind CSS)

## Steps to Run the Project

### 1. Clone the Repository
```bash
git clone https://github.com/Madhisha/ACPNS.git
cd ACPNS
```
### 2. Set Up the Frontend (Tailwind CSS)

Install Node.js dependencies and run the Tailwind CSS build:

```bash
# Install Node.js dependencies
npm install

# Run the Tailwind CSS build process
npx tailwindcss -i ./input.css -o ./dist/output.css --watch
```

This will compile your Tailwind CSS styles and watch for changes.

### 3. Set Up the Backend (Python & Flask)

Ensure that Flask is installed. If not, install Flask using `pip`:

```bash
# Install Flask
pip install flask
```

Once Flask is installed, navigate to the backend folder and start the Flask server:

```bash
# Navigate to the backend folder
cd backend

# Run the Flask server
python pyserver.py
```

### 4. Open the Web Page

After the Flask server is running, open your browser and navigate to the following URL:

```
http://localhost:5000
```

You should see the web page with the Tailwind CSS-based styles and animations.

### 5. Modifications

If you want to modify the CSS, edit the `index.css` file and Tailwind will automatically recompile your changes. For backend changes, modify `pyserver.py` or other Python files as needed.

## Additional Information

- Ensure both the frontend (CSS) and backend (Flask) are running simultaneously for the project to function correctly.
- You can also serve static files through Flask by adjusting the configuration in `pyserver.py`.

### Example Flask Setup (pyserver.py):

```python
from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
```

With this setup, Flask will serve the web page and handle requests.
## Troubleshooting

- Ensure you have both `npm` and `pip` installed.
- If Tailwind CSS isn't compiling, try re-running `npx tailwindcss -i ./input.css -o ./dist/output.css --watch`.
- For Python issues, make sure you are using a supported version of Python (3.6+).
