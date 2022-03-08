from flask import Flask
import logging

app = Flask(__name__)

@staticmethod
@app.route('/health')
def api_process():
    return "UP"


if __name__ == '__main__':

    logger = logging.getLogger('werkzeug')
    logger.setLevel(logging.ERROR)
    #self.health.add_check(self.process_running_check)
    app.run(host='0.0.0.0', port=8080)
