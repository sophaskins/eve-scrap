from flask import request
from flask import render_template
from flask import Flask
import evepaste
from evescrap import appraise


app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        items_to_appraise = evepaste.parse(request.form['raw_textarea'])[1]
        appraisals = appraise(items_to_appraise)
    else:
        appraisals = None

    return render_template('index.html', appraisals=appraisals)


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=9999)
